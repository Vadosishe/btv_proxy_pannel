#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " Corporate VPN Node Setup & Anti-Abuse Hardening Script"
echo "=========================================================="

# 1. Update & Install Dependencies
apt-get update -y
apt-get install -y ca-certificates curl gnupg lsb-release iptables ufw docker.io docker-compose || apt-get install -y docker-compose-v2 || true

# Disable systemd-resolved DNS stub listener to free port 53 for AdGuard Home
sed -i 's/#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf || true
systemctl restart systemd-resolved || true

# 2. Install AdGuard Home for DNS Filtering (Gambling & Abuse Protection)
mkdir -p /opt/adguardhome/work /opt/adguardhome/conf


cat <<'EOF' > /opt/adguardhome/conf/AdGuardHome.yaml
dns:
  bind_hosts:
    - 127.0.0.1
  port: 53
  upstream_dns:
    - https://dns.quad9.net/dns-query
    - 1.1.1.1
  filters:
    - enabled: true
      url: https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/gambling.txt
      name: Hagezi Gambling Blocklist
    - enabled: true
      url: https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts
      name: StevenBlack Unified (Gambling & Fake)
EOF

docker run -d \
  --name adguardhome \
  --restart always \
  --net host \
  -v /opt/adguardhome/work:/opt/adguardhome/work \
  -v /opt/adguardhome/conf:/opt/adguardhome/conf \
  adguard/adguardhome

# 3. Apply Anti-Abuse iptables Firewall Rules
echo "[+] Applying iptables security rules..."

# Redirect all outgoing DNS traffic from clients to local AdGuard Home (port 53)
iptables -t nat -A PREROUTING -p udp --dport 53 -j REDIRECT --to-ports 53
iptables -t nat -A PREROUTING -p tcp --dport 53 -j REDIRECT --to-ports 53

# Block outgoing SMTP ports (prevent spam bans)
iptables -A OUTPUT -p tcp --dport 25 -j DROP
iptables -A OUTPUT -p tcp --dport 465 -j DROP
iptables -A OUTPUT -p tcp --dport 587 -j DROP

# Save iptables rules persistent across reboots
apt-get install -y iptables-persistent || true
netfilter-persistent save || true

# 4. Install 3X-UI Node Engine for VLESS / Reality
echo "[+] Installing 3X-UI Node Engine..."
printf "y\n2053\nadmin\nadmin\n" | bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh) || true


echo "=========================================================="
echo " SUCCESS: Node is hardened and ready for AmneziaWG + 3X-UI!"
echo "=========================================================="
