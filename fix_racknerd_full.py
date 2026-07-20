import paramiko, json

# 1. SSH into Racknerd (23.95.48.191)
ssh_rn = paramiko.SSHClient()
ssh_rn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_rn.connect('23.95.48.191', username='root', password='C0x1C3xrdG0t0W1YTk')

def rn_exec(cmd):
    _, stdout, stderr = ssh_rn.exec_command(cmd)
    return stdout.read().decode().strip()

print("[1] Removing stale amnezia-awg2 on Racknerd...")
rn_exec("docker rm -f amnezia-awg2 2>/dev/null || true")
rn_exec("mkdir -p /opt/amnezia/awg")

priv_key = rn_exec("docker run --rm amneziavpn/amnezia-wg:latest wg genkey")
pub_key = rn_exec(f"echo '{priv_key}' | docker run -i --rm amneziavpn/amnezia-wg:latest wg pubkey")
psk_key = rn_exec("docker run --rm amneziavpn/amnezia-wg:latest wg genpsk")

print(f"Generated Keys: PubKey={pub_key}")

awg_params = {
    "H1": 1155587185, "H2": 905802652, "H3": 749941050, "H4": 74677149,
    "Jc": 3, "Jmin": 10, "Jmax": 50,
    "S1": 228, "S2": 193, "S3": 30, "S4": 15
}

awg0_conf = f"""[Interface]
Address = 10.8.1.1/24
ListenPort = 59515
PrivateKey = {priv_key}
Jc = {awg_params['Jc']}
Jmin = {awg_params['Jmin']}
Jmax = {awg_params['Jmax']}
S1 = {awg_params['S1']}
S2 = {awg_params['S2']}
S3 = {awg_params['S3']}
S4 = {awg_params['S4']}
H1 = {awg_params['H1']}
H2 = {awg_params['H2']}
H3 = {awg_params['H3']}
H4 = {awg_params['H4']}

"""

start_sh = """#!/bin/bash
awg-quick down /opt/amnezia/awg/awg0.conf 2>/dev/null || true
if [ -f /opt/amnezia/awg/awg0.conf ]; then awg-quick up /opt/amnezia/awg/awg0.conf; fi
iptables -A INPUT -i awg0 -j ACCEPT 2>/dev/null || true
iptables -A FORWARD -i awg0 -j ACCEPT 2>/dev/null || true
iptables -A OUTPUT -o awg0 -j ACCEPT 2>/dev/null || true
iptables -t nat -A POSTROUTING -s 10.8.1.0/24 -j MASQUERADE 2>/dev/null || true
tail -f /dev/null
"""

sftp = ssh_rn.open_sftp()
with sftp.file('/opt/amnezia/awg/awg0.conf', 'w') as f:
    f.write(awg0_conf)
with sftp.file('/opt/amnezia/start.sh', 'w') as f:
    f.write(start_sh)
sftp.close()

rn_exec("chmod +x /opt/amnezia/start.sh")

# Run container amnezia-awg2 using image amneziavpn/amnezia-wg:latest with entrypoint /opt/amnezia/start.sh
rn_exec("docker run -d --name amnezia-awg2 --restart always --cap-add=NET_ADMIN --cap-add=SYS_MODULE -v /opt/amnezia:/opt/amnezia -p 59515:59515/udp --entrypoint /opt/amnezia/start.sh amneziavpn/amnezia-wg:latest")

ps_out = rn_exec("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")
print("Container PS on Racknerd:\n", ps_out)

ssh_rn.close()

# 2. Update MySQL DB on master server
ssh_m = paramiko.SSHClient()
ssh_m.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_m.connect('5.129.229.25', username='root', password='x_8,,_CJMuvhwj')

awg_json = json.dumps(awg_params).replace('"', '\\"')

sql_update = f"""UPDATE vpn_servers SET server_public_key = '{pub_key}', preshared_key = '{psk_key}', awg_params = '{awg_json}', status = 'active', error_message = NULL WHERE id = 3;"""
cmd_db = f'docker exec amnezia-panel-db mysql -u amnezia -pamnezia amnezia_panel -e "{sql_update}"'
_, stdout, stderr = ssh_m.exec_command(cmd_db)
print("DB Update result:", stdout.read().decode())

ssh_m.close()
