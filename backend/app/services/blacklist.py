import paramiko, logging, asyncio
from sqlalchemy.orm import Session
from app.models import Node, Agency, BlacklistProfile, BlacklistRule, EntryType

logger = logging.getLogger("blacklist_service")

def sync_node_blacklist(node_id: int, db: Session) -> dict:
    """Synchronize all active blacklist rules for a specific node via SSH."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        return {"status": "error", "message": f"Node #{node_id} not found"}

    # Determine node IP/host from amnezia_url or xui_url or SSH default
    server_ip = "5.129.229.25"  # Primary server IP default
    if node.amnezia_url and "://" in node.amnezia_url:
        server_ip = node.amnezia_url.split("://")[1].split(":")[0]
    elif node.xui_url and "://" in node.xui_url:
        server_ip = node.xui_url.split("://")[1].split(":")[0]

    # 1. Collect Global Profile rules
    global_profile = db.query(BlacklistProfile).filter(BlacklistProfile.is_global == True).first()
    global_ips = set()
    global_domains = set()

    if global_profile:
        for r in global_profile.rules:
            if r.is_active:
                if r.entry_type == EntryType.IP:
                    global_ips.add(r.target_value.strip())
                elif r.entry_type == EntryType.DOMAIN:
                    global_domains.add(r.target_value.strip())

    # 2. Collect Node-specific Profile rules
    if node.blacklist_profile_id:
        n_profile = db.query(BlacklistProfile).filter(BlacklistProfile.id == node.blacklist_profile_id).first()
        if n_profile:
            for r in n_profile.rules:
                if r.is_active:
                    if r.entry_type == EntryType.IP:
                        global_ips.add(r.target_value.strip())
                    elif r.entry_type == EntryType.DOMAIN:
                        global_domains.add(r.target_value.strip())

    # 3. Collect Company-specific Profile rules
    agencies_map = {}  # agency_id -> {ips: set(), domains: set()}
    agencies = db.query(Agency).filter(Agency.blacklist_profile_id.isnot(None)).all()
    for ag in agencies:
        ag_profile = db.query(BlacklistProfile).filter(BlacklistProfile.id == ag.blacklist_profile_id).first()
        if ag_profile:
            ag_ips = set()
            ag_domains = set()
            for r in ag_profile.rules:
                if r.is_active:
                    if r.entry_type == EntryType.IP:
                        ag_ips.add(r.target_value.strip())
                    elif r.entry_type == EntryType.DOMAIN:
                        ag_domains.add(r.target_value.strip())
            if ag_ips or ag_domains:
                agencies_map[ag.id] = {"ips": ag_ips, "domains": ag_domains}

    # Generate SSH commands for ipset & iptables & dnsmasq
    cmd_script = "#!/bin/bash\n"
    cmd_script += "set -e\n"

    # Global IPSET
    cmd_script += "ipset create b2b_global_block hash:net -exist\n"
    cmd_script += "ipset flush b2b_global_block\n"
    for ip in global_ips:
        cmd_script += f"ipset add b2b_global_block {ip} -exist\n"
    cmd_script += "iptables -C FORWARD -m set --match-set b2b_global_block dst -j DROP 2>/dev/null || iptables -I FORWARD -m set --match-set b2b_global_block dst -j DROP\n"

    # Per-Company IPSET (Subnet 10.8.X.0/24 or 10.8.1.X)
    for ag_id, data in agencies_map.items():
        set_name = f"b2b_ag_{ag_id}_block"
        cmd_script += f"ipset create {set_name} hash:net -exist\n"
        cmd_script += f"ipset flush {set_name}\n"
        for ip in data["ips"]:
            cmd_script += f"ipset add {set_name} {ip} -exist\n"
        # Company internal subnet source filter
        cmd_script += f"iptables -C FORWARD -s 10.8.{ag_id}.0/24 -m set --match-set {set_name} dst -j DROP 2>/dev/null || iptables -I FORWARD -s 10.8.{ag_id}.0/24 -m set --match-set {set_name} dst -j DROP\n"

    # DNS Domain rules (inside Amnezia DNS container or local dnsmasq)
    dns_rules_content = ""
    for d in global_domains:
        dns_rules_content += f"address=/{d}/0.0.0.0\n"

    for ag_id, data in agencies_map.items():
        for d in data["domains"]:
            dns_rules_content += f"address=/{d}/0.0.0.0\n"

    # Try applying via SSH
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # Use primary SSH key or credentials
        ssh.connect(server_ip, username="root", password="x_8,,_CJMuvhwj", timeout=10)
        
        # Apply IP rules
        stdin, stdout, stderr = ssh.exec_command(f"cat << 'EOF' > /tmp/sync_b2b_rules.sh\n{cmd_script}\nEOF\nbash /tmp/sync_b2b_rules.sh")
        out = stdout.read().decode("utf-8")
        err = stderr.read().decode("utf-8")

        # Apply DNS domain rules if container amnezia-dns exists
        if dns_rules_content:
            dns_cmd = f"docker exec -i amnezia-dns sh -c \"cat << 'EOF' > /etc/dnsmasq.d/b2b_rules.conf\n{dns_rules_content}\nEOF\nkillall -HUP dnsmasq\" 2>/dev/null || true"
            ssh.exec_command(dns_cmd)

        ssh.close()
        return {"status": "ok", "global_ips": len(global_ips), "global_domains": len(global_domains), "out": out, "err": err}
    except Exception as e:
        logger.error(f"SSH sync error on node #{node_id} ({server_ip}): {e}")
        return {"status": "error", "message": str(e)}
