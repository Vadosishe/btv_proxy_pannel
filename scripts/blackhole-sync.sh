#!/usr/bin/env bash
set -euo pipefail

# Blackhole Sync Script: Downloads domain/IP blocklists from Master Orchestrator and updates AdGuard Home & ipset

ORCHESTRATOR_API_URL="${ORCHESTRATOR_API_URL:-http://localhost:8000/api/admin/blackhole}"

echo "[+] Syncing Blackhole blocklists from ${ORCHESTRATOR_API_URL}..."

TMP_DOMAINS="/tmp/blocked_domains.txt"
TMP_IPS="/tmp/blocked_ips.txt"

# Fetch list from Orchestrator API
curl -s "${ORCHESTRATOR_API_URL}" | grep -o '"value":"[^"]*"' | cut -d'"' -f4 > /tmp/raw_blackhole.txt || true

# 1. Update AdGuard Home custom blackhole rules for domains
if [ -f /opt/adguardhome/conf/AdGuardHome.yaml ]; then
    echo "[+] Updating AdGuard Home DNS blackhole..."
    grep -E '^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' /tmp/raw_blackhole.txt > "${TMP_DOMAINS}" || true
    
    # Format for AdGuard Home user rules: ||domain.com^$dnsrewrite=0.0.0.0
    sed -i 's/^/||/' "${TMP_DOMAINS}"
    sed -i 's/$/\^$dnsrewrite=0.0.0.0/' "${TMP_DOMAINS}"
    
    cat "${TMP_DOMAINS}" > /opt/adguardhome/work/userfilters.txt || true
    docker restart adguardhome || true
fi

# 2. Update iptables / ipset for direct IP drops
echo "[+] Updating iptables IP blackhole..."
grep -E '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$' /tmp/raw_blackhole.txt > "${TMP_IPS}" || true

ipset create -exist blackhole_ips hash:ip
ipset flush blackhole_ips

while read -r ip; do
    if [ -n "$ip" ]; then
        ipset add blackhole_ips "$ip"
    fi
done < "${TMP_IPS}"

iptables -C OUTPUT -m set --match-set blackhole_ips dst -j DROP 2>/dev/null || \
iptables -A OUTPUT -m set --match-set blackhole_ips dst -j DROP

echo "[+] Blackhole sync complete."
