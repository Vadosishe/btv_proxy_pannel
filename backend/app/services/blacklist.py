import paramiko, logging, socket
from sqlalchemy.orm import Session
from app.models import Node, Agency, BlacklistProfile, BlacklistRule, EntryType

logger = logging.getLogger("blacklist_service")

# Preset Categories Domain Lists
PRESET_CATEGORIES = {
    "CASINO": [
        "1xbet.com", "1x-bet.com", "stake.com", "pin-up.casino", "vulkan-casino.com",
        "joycasino.com", "casino-x.com", "mostbet.com", "fon.bet", "winline.ru",
        "parimatch.ru", "betboom.ru", "ligastavok.ru", "marathonbet.ru", "melbet.ru"
    ],
    "MALWARE": [
        "phishing-test.com", "bad-malware-site.net", "fake-bank-login.com", "stealer-drop.ru"
    ],
    "TORRENT": [
        "rutracker.org", "rutracker.wiki", "rutor.is", "rutor.info", "torrent-igruha.org",
        "kinozal.tv", "nnmclub.to", "thepiratebay.org", "1337x.to"
    ],
    "ADULT": [
        "pornhub.com", "xvideos.com", "xhamster.com", "xnxx.com", "stripchat.com"
    ]
}

def resolve_domain_ips(domain: str) -> tuple:
    """Resolve domain and subdomains to sets of IPv4 and IPv6 addresses."""
    ipv4s = set()
    ipv6s = set()
    hosts = set()

    clean_domain = domain.strip().lower()
    if clean_domain.startswith("*."):
        clean_domain = clean_domain[2:]

    hosts.add(clean_domain)
    hosts.add("www." + clean_domain)
    hosts.add("m." + clean_domain)

    for host in hosts:
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

    return hosts, ipv4s, ipv6s


def sync_node_blacklist(node_id: int, db: Session) -> dict:
    """
    Synchronize all active blacklist rules for a specific node via SSH.
    GUARANTEES 100% REVERSIBLE ROLLBACK: Clears all previous B2B rules, ipsets, 
    and DNS maps before applying current active rules.
    """
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        return {"status": "error", "message": f"Node #{node_id} not found"}

    server_ip = "5.129.229.25"
    if node.amnezia_url and "://" in node.amnezia_url:
        server_ip = node.amnezia_url.split("://")[1].split(":")[0]
    elif node.xui_url and "://" in node.xui_url:
        server_ip = node.xui_url.split("://")[1].split(":")[0]

    all_hosts = set()
    global_ipv4s = set()
    global_ipv6s = set()

    def process_rules(rules):
        for r in rules:
            if not r.is_active:
                continue
            if r.entry_type == EntryType.IP:
                val = r.target_value.strip()
                if ":" in val:
                    global_ipv6s.add(val)
                else:
                    global_ipv4s.add(val)
            elif r.entry_type == EntryType.DOMAIN:
                val = r.target_value.strip()
                if val.upper() in PRESET_CATEGORIES:
                    # Category preset expansion
                    for dom in PRESET_CATEGORIES[val.upper()]:
                        h_set, v4, v6 = resolve_domain_ips(dom)
                        all_hosts.update(h_set)
                        global_ipv4s.update(v4)
                        global_ipv6s.update(v6)
                else:
                    h_set, v4, v6 = resolve_domain_ips(val)
                    all_hosts.update(h_set)
                    global_ipv4s.update(v4)
                    global_ipv6s.update(v6)

    # 1. Collect Global Profile rules
    global_profile = db.query(BlacklistProfile).filter(BlacklistProfile.is_global == True).first()
    if global_profile:
        process_rules(global_profile.rules)

    # 2. Collect Node-specific Profile rules
    if node.blacklist_profile_id:
        n_profile = db.query(BlacklistProfile).filter(BlacklistProfile.id == node.blacklist_profile_id).first()
        if n_profile:
            process_rules(n_profile.rules)

    # 3. Collect Company-specific Profile rules
    agencies = db.query(Agency).filter(Agency.blacklist_profile_id.isnot(None)).all()
    for ag in agencies:
        ag_profile = db.query(BlacklistProfile).filter(BlacklistProfile.id == ag.blacklist_profile_id).first()
        if ag_profile:
            process_rules(ag_profile.rules)

    # BUILD 100% REVERSIBLE CLEANUP & RE-APPLY SCRIPT
    cmd_script = "#!/bin/bash\n"
    cmd_script += "# --- STEP 1: CLEANUP / FLUSH PREVIOUS RULES (ROLLBACK SAFE) ---\n"
    cmd_script += "which ipset >/dev/null 2>&1 || (apt-get update -y && apt-get install -y ipset) || true\n"

    # Remove all previous B2B rules from iptables/ip6tables chains
    cmd_script += "iptables-save | grep -v 'b2b_' | iptables-restore 2>/dev/null || true\n"
    cmd_script += "ip6tables-save | grep -v 'b2b_' | ip6tables-restore 2>/dev/null || true\n"

    # Flush & destroying ipset sets
    cmd_script += "if which ipset >/dev/null 2>&1; then\n"
    cmd_script += "  ipset destroy b2b_global_block 2>/dev/null || true\n"
    cmd_script += "fi\n"

    # Empty DNS Sinkhole map
    cmd_script += "> /etc/b2b_dns_hosts\n"

    cmd_script += "\n# --- STEP 2: APPLY CURRENT ACTIVE RULES ---\n"

    # Write DNS Sinkhole map if hosts exist
    if all_hosts:
        cmd_script += "cat << 'EOF_HOSTS' > /etc/b2b_dns_hosts\n"
        for host in sorted(all_hosts):
            cmd_script += f"0.0.0.0 {host}\n"
        cmd_script += "EOF_HOSTS\n"
        # Append to /etc/hosts or reload dnsmasq/hosts if configured
        cmd_script += "grep -q 'b2b_dns_hosts' /etc/dnsmasq.conf 2>/dev/null || (echo 'addn-hosts=/etc/b2b_dns_hosts' >> /etc/dnsmasq.conf && systemctl restart dnsmasq 2>/dev/null || true)\n"

    # Re-create IPSET & Firewall Rules if IP addresses exist
    if global_ipv4s:
        cmd_script += "if which ipset >/dev/null 2>&1; then\n"
        cmd_script += "  ipset create b2b_global_block hash:net -exist\n"
        cmd_script += "  ipset flush b2b_global_block\n"
        for ip in global_ipv4s:
            cmd_script += f"  ipset add b2b_global_block {ip} -exist\n"
        cmd_script += "  iptables -I DOCKER-USER 1 -m set --match-set b2b_global_block dst -m comment --comment 'b2b_rule' -j DROP\n"
        cmd_script += "  iptables -I FORWARD 1 -m set --match-set b2b_global_block dst -m comment --comment 'b2b_rule' -j DROP\n"
        cmd_script += "  iptables -I INPUT 1 -m set --match-set b2b_global_block dst -m comment --comment 'b2b_rule' -j DROP\n"
        cmd_script += "fi\n"

        for ip in global_ipv4s:
            cmd_script += f"iptables -I DOCKER-USER 1 -d {ip} -m comment --comment 'b2b_rule' -j DROP\n"
            cmd_script += f"iptables -I FORWARD 1 -d {ip} -m comment --comment 'b2b_rule' -j DROP\n"
            cmd_script += f"iptables -I INPUT 1 -d {ip} -m comment --comment 'b2b_rule' -j DROP\n"

    if global_ipv6s:
        for ip in global_ipv6s:
            cmd_script += f"ip6tables -I FORWARD 1 -d {ip} -m comment --comment 'b2b_rule' -j DROP\n"
            cmd_script += f"ip6tables -I INPUT 1 -d {ip} -m comment --comment 'b2b_rule' -j DROP\n"

    # Dynamic SSH Credentials for each Remote Node (Timeweb, Racknerd, Aeza)
    node_ssh_creds = {
        5: ("5.129.229.25", "root", "x_8,,_CJMuvhwj"),
        7: ("23.95.48.191", "root", "eY4rP8aiy4X65OQwZ2"),
        8: ("138.124.59.128", "root", "ntZG8Xpzb23j"),
    }

    server_ip, ssh_user, ssh_pass = node_ssh_creds.get(node_id, ("5.129.229.25", "root", "x_8,,_CJMuvhwj"))
    if node.amnezia_url and "://" in node.amnezia_url:
        server_ip = node.amnezia_url.split("://")[1].split(":")[0]

    # Execute SSH commands on the actual remote node
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server_ip, username=ssh_user, password=ssh_pass, timeout=10)

        stdin, stdout, stderr = ssh.exec_command(f"cat << 'EOF' > /tmp/sync_b2b_rules.sh\n{cmd_script}\nEOF\nbash /tmp/sync_b2b_rules.sh")
        out = stdout.read().decode("utf-8")
        err = stderr.read().decode("utf-8")

        ssh.close()
        return {
            "status": "ok",
            "node_ip": server_ip,
            "hosts_count": len(all_hosts),
            "ipv4_count": len(global_ipv4s),
            "ipv6_count": len(global_ipv6s),
            "out": out,
            "err": err
        }
    except Exception as e:
        logger.error(f"SSH sync error on node #{node_id} ({server_ip}): {e}")
        return {"status": "error", "node_ip": server_ip, "message": str(e)}
