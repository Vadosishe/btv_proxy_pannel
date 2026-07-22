import paramiko, logging, socket
from sqlalchemy.orm import Session
from app.models import Node, Agency, BlacklistProfile, BlacklistRule, EntryType

logger = logging.getLogger("blacklist_service")

def resolve_domain_ips(domain: str) -> set:
    """Resolve domain and subdomains to a set of IP addresses."""
    ips = set()
    clean_domain = domain.strip().lower()
    if clean_domain.startswith("*."):
        clean_domain = clean_domain[2:]
    try:
        _, _, ip_list = socket.gethostbyname_ex(clean_domain)
        for ip in ip_list:
            ips.add(ip)
    except Exception:
        pass
    try:
        _, _, www_ip_list = socket.gethostbyname_ex("www." + clean_domain)
        for ip in www_ip_list:
            ips.add(ip)
    except Exception:
        pass
    return ips


def sync_node_blacklist(node_id: int, db: Session) -> dict:
    """Synchronize all active blacklist rules for a specific node via SSH."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        return {"status": "error", "message": f"Node #{node_id} not found"}

    server_ip = "5.129.229.25"  # Primary server IP default
    if node.amnezia_url and "://" in node.amnezia_url:
        server_ip = node.amnezia_url.split("://")[1].split(":")[0]
    elif node.xui_url and "://" in node.xui_url:
        server_ip = node.xui_url.split("://")[1].split(":")[0]

    # 1. Collect Global Profile rules
    global_profile = db.query(BlacklistProfile).filter(BlacklistProfile.is_global == True).first()
    global_ips = set()

    if global_profile:
        for r in global_profile.rules:
            if r.is_active:
                if r.entry_type == EntryType.IP:
                    global_ips.add(r.target_value.strip())
                elif r.entry_type == EntryType.DOMAIN:
                    resolved = resolve_domain_ips(r.target_value.strip())
                    global_ips.update(resolved)

    # 2. Collect Node-specific Profile rules
    if node.blacklist_profile_id:
        n_profile = db.query(BlacklistProfile).filter(BlacklistProfile.id == node.blacklist_profile_id).first()
        if n_profile:
            for r in n_profile.rules:
                if r.is_active:
                    if r.entry_type == EntryType.IP:
                        global_ips.add(r.target_value.strip())
                    elif r.entry_type == EntryType.DOMAIN:
                        resolved = resolve_domain_ips(r.target_value.strip())
                        global_ips.update(resolved)

    # 3. Collect Company-specific Profile rules
    agencies_map = {}  # agency_id -> {ips: set()}
    agencies = db.query(Agency).filter(Agency.blacklist_profile_id.isnot(None)).all()
    for ag in agencies:
        ag_profile = db.query(BlacklistProfile).filter(BlacklistProfile.id == ag.blacklist_profile_id).first()
        if ag_profile:
            ag_ips = set()
            for r in ag_profile.rules:
                if r.is_active:
                    if r.entry_type == EntryType.IP:
                        ag_ips.add(r.target_value.strip())
                    elif r.entry_type == EntryType.DOMAIN:
                        resolved = resolve_domain_ips(r.target_value.strip())
                        ag_ips.update(resolved)
            if ag_ips:
                agencies_map[ag.id] = {"ips": ag_ips}

    # Generate SSH commands for ipset & iptables
    cmd_script = "#!/bin/bash\n"
    cmd_script += "which ipset >/dev/null 2>&1 || (apt-get update -y && apt-get install -y ipset) || true\n"

    # Global IPSET
    cmd_script += "if which ipset >/dev/null 2>&1; then\n"
    cmd_script += "  ipset create b2b_global_block hash:net -exist\n"
    cmd_script += "  ipset flush b2b_global_block\n"
    for ip in global_ips:
        cmd_script += f"  ipset add b2b_global_block {ip} -exist\n"
    cmd_script += "  iptables -C FORWARD -m set --match-set b2b_global_block dst -j DROP 2>/dev/null || iptables -I FORWARD -m set --match-set b2b_global_block dst -j DROP\n"
    cmd_script += "fi\n"

    # Direct fallback iptables rules for each IP
    for ip in global_ips:
        cmd_script += f"iptables -C FORWARD -d {ip} -j DROP 2>/dev/null || iptables -I FORWARD -d {ip} -j DROP\n"

    # Per-Company IPSET
    for ag_id, data in agencies_map.items():
        set_name = f"b2b_ag_{ag_id}_block"
        cmd_script += "if which ipset >/dev/null 2>&1; then\n"
        cmd_script += f"  ipset create {set_name} hash:net -exist\n"
        cmd_script += f"  ipset flush {set_name}\n"
        for ip in data["ips"]:
            cmd_script += f"  ipset add {set_name} {ip} -exist\n"
        cmd_script += f"  iptables -C FORWARD -m set --match-set {set_name} dst -j DROP 2>/dev/null || iptables -I FORWARD -m set --match-set {set_name} dst -j DROP\n"
        cmd_script += "fi\n"
        # Direct fallback iptables rules
        for ip in data["ips"]:
            cmd_script += f"iptables -C FORWARD -d {ip} -j DROP 2>/dev/null || iptables -I FORWARD -d {ip} -j DROP\n"

    # Try applying via SSH
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server_ip, username="root", password="x_8,,_CJMuvhwj", timeout=10)
        
        stdin, stdout, stderr = ssh.exec_command(f"cat << 'EOF' > /tmp/sync_b2b_rules.sh\n{cmd_script}\nEOF\nbash /tmp/sync_b2b_rules.sh")
        out = stdout.read().decode("utf-8")
        err = stderr.read().decode("utf-8")

        ssh.close()
        return {"status": "ok", "global_ips": len(global_ips), "agencies_count": len(agencies_map), "out": out, "err": err}
    except Exception as e:
        logger.error(f"SSH sync error on node #{node_id} ({server_ip}): {e}")
        return {"status": "error", "message": str(e)}

