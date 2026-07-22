import paramiko, logging, socket
from sqlalchemy.orm import Session
from app.models import Node, Agency, BlacklistProfile, BlacklistRule, EntryType

logger = logging.getLogger("blacklist_service")

def resolve_domain_ips(domain: str) -> tuple:
    """Resolve domain and subdomains to sets of IPv4 and IPv6 addresses."""
    ipv4s = set()
    ipv6s = set()
    clean_domain = domain.strip().lower()
    if clean_domain.startswith("*."):
        clean_domain = clean_domain[2:]

    for host in [clean_domain, "www." + clean_domain]:
        try:
            infos = socket.getaddrinfo(host, None)
            for family, _, _, _, sockaddr in infos:
                ip = sockaddr[0]
                if family == socket.AF_INET:
                    ipv4s.add(ip)
                elif family == socket.AF_INET6:
                    ipv6s.add(ip)
        except Exception:
            pass

    return ipv4s, ipv6s


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
    global_ipv4s = set()
    global_ipv6s = set()

    if global_profile:
        for r in global_profile.rules:
            if r.is_active:
                if r.entry_type == EntryType.IP:
                    val = r.target_value.strip()
                    if ":" in val:
                        global_ipv6s.add(val)
                    else:
                        global_ipv4s.add(val)
                elif r.entry_type == EntryType.DOMAIN:
                    v4, v6 = resolve_domain_ips(r.target_value.strip())
                    global_ipv4s.update(v4)
                    global_ipv6s.update(v6)

    # 2. Collect Node-specific Profile rules
    if node.blacklist_profile_id:
        n_profile = db.query(BlacklistProfile).filter(BlacklistProfile.id == node.blacklist_profile_id).first()
        if n_profile:
            for r in n_profile.rules:
                if r.is_active:
                    if r.entry_type == EntryType.IP:
                        val = r.target_value.strip()
                        if ":" in val:
                            global_ipv6s.add(val)
                        else:
                            global_ipv4s.add(val)
                    elif r.entry_type == EntryType.DOMAIN:
                        v4, v6 = resolve_domain_ips(r.target_value.strip())
                        global_ipv4s.update(v4)
                        global_ipv6s.update(v6)

    # 3. Collect Company-specific Profile rules
    agencies_map = {}  # agency_id -> {v4: set(), v6: set()}
    agencies = db.query(Agency).filter(Agency.blacklist_profile_id.isnot(None)).all()
    for ag in agencies:
        ag_profile = db.query(BlacklistProfile).filter(BlacklistProfile.id == ag.blacklist_profile_id).first()
        if ag_profile:
            ag_v4 = set()
            ag_v6 = set()
            for r in ag_profile.rules:
                if r.is_active:
                    if r.entry_type == EntryType.IP:
                        val = r.target_value.strip()
                        if ":" in val:
                            ag_v6.add(val)
                        else:
                            ag_v4.add(val)
                    elif r.entry_type == EntryType.DOMAIN:
                        v4, v6 = resolve_domain_ips(r.target_value.strip())
                        ag_v4.update(v4)
                        ag_v6.update(v6)
            if ag_v4 or ag_v6:
                agencies_map[ag.id] = {"v4": ag_v4, "v6": ag_v6}

    # Generate SSH commands for ipset & iptables / ip6tables
    cmd_script = "#!/bin/bash\n"
    cmd_script += "which ipset >/dev/null 2>&1 || (apt-get update -y && apt-get install -y ipset) || true\n"

    # Global IPSET & direct iptables rules
    cmd_script += "if which ipset >/dev/null 2>&1; then\n"
    cmd_script += "  ipset create b2b_global_block hash:net -exist\n"
    cmd_script += "  ipset flush b2b_global_block\n"
    for ip in global_ipv4s:
        cmd_script += f"  ipset add b2b_global_block {ip} -exist\n"
    cmd_script += "  iptables -C DOCKER-USER -m set --match-set b2b_global_block dst -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -m set --match-set b2b_global_block dst -j DROP\n"
    cmd_script += "  iptables -C FORWARD -m set --match-set b2b_global_block dst -j DROP 2>/dev/null || iptables -I FORWARD 1 -m set --match-set b2b_global_block dst -j DROP\n"
    cmd_script += "fi\n"

    for ip in global_ipv4s:
        cmd_script += f"iptables -C DOCKER-USER -d {ip} -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -d {ip} -j DROP\n"
        cmd_script += f"iptables -C FORWARD -d {ip} -j DROP 2>/dev/null || iptables -I FORWARD 1 -d {ip} -j DROP\n"
        cmd_script += f"iptables -C INPUT -d {ip} -j DROP 2>/dev/null || iptables -I INPUT 1 -d {ip} -j DROP\n"
    for ip in global_ipv6s:
        cmd_script += f"ip6tables -C FORWARD -d {ip} -j DROP 2>/dev/null || ip6tables -I FORWARD 1 -d {ip} -j DROP\n"
        cmd_script += f"ip6tables -C INPUT -d {ip} -j DROP 2>/dev/null || ip6tables -I INPUT 1 -d {ip} -j DROP\n"

    # Per-Company IPSET & direct rules
    for ag_id, data in agencies_map.items():
        set_name = f"b2b_ag_{ag_id}_block"
        cmd_script += "if which ipset >/dev/null 2>&1; then\n"
        cmd_script += f"  ipset create {set_name} hash:net -exist\n"
        cmd_script += f"  ipset flush {set_name}\n"
        for ip in data["v4"]:
            cmd_script += f"  ipset add {set_name} {ip} -exist\n"
        cmd_script += f"  iptables -C DOCKER-USER -m set --match-set {set_name} dst -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -m set --match-set {set_name} dst -j DROP\n"
        cmd_script += f"  iptables -C FORWARD -m set --match-set {set_name} dst -j DROP 2>/dev/null || iptables -I FORWARD 1 -m set --match-set {set_name} dst -j DROP\n"
        cmd_script += f"  iptables -C INPUT -m set --match-set {set_name} dst -j DROP 2>/dev/null || iptables -I INPUT 1 -m set --match-set {set_name} dst -j DROP\n"
        cmd_script += "fi\n"
        for ip in data["v4"]:
            cmd_script += f"iptables -C DOCKER-USER -d {ip} -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -d {ip} -j DROP\n"
            cmd_script += f"iptables -C FORWARD -d {ip} -j DROP 2>/dev/null || iptables -I FORWARD 1 -d {ip} -j DROP\n"
            cmd_script += f"iptables -C INPUT -d {ip} -j DROP 2>/dev/null || iptables -I INPUT 1 -d {ip} -j DROP\n"
        for ip in data["v6"]:
            cmd_script += f"ip6tables -C FORWARD -d {ip} -j DROP 2>/dev/null || ip6tables -I FORWARD 1 -d {ip} -j DROP\n"
            cmd_script += f"ip6tables -C INPUT -d {ip} -j DROP 2>/dev/null || ip6tables -I INPUT 1 -d {ip} -j DROP\n"

    # Try applying via SSH
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server_ip, username="root", password="x_8,,_CJMuvhwj", timeout=10)
        
        stdin, stdout, stderr = ssh.exec_command(f"cat << 'EOF' > /tmp/sync_b2b_rules.sh\n{cmd_script}\nEOF\nbash /tmp/sync_b2b_rules.sh")
        out = stdout.read().decode("utf-8")
        err = stderr.read().decode("utf-8")

        ssh.close()
        return {"status": "ok", "global_v4": len(global_ipv4s), "global_v6": len(global_ipv6s), "agencies_count": len(agencies_map), "out": out, "err": err}
    except Exception as e:
        logger.error(f"SSH sync error on node #{node_id} ({server_ip}): {e}")
        return {"status": "error", "message": str(e)}


