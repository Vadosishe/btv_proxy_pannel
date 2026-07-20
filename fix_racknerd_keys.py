import paramiko, json

# 1. SSH into Racknerd (23.95.48.191) to generate WireGuard / AmneziaWG keys
ssh_rn = paramiko.SSHClient()
ssh_rn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_rn.connect('23.95.48.191', username='root', password='C0x1C3xrdG0t0W1YTk')

def rn_exec(cmd):
    _, stdout, stderr = ssh_rn.exec_command(cmd)
    return stdout.read().decode().strip()

# Stop and recreate container with proper start script & parameters
rn_exec("docker rm -f amnezia-awg2 2>/dev/null || true")
rn_exec("mkdir -p /opt/amnezia/awg")

# Generate keys using docker container or openssl/wg
priv_key = rn_exec("docker run --rm amneziavpn/amnezia-wg:latest wg genkey")
pub_key = rn_exec(f"echo '{priv_key}' | docker run -i --rm amneziavpn/amnezia-wg:latest wg pubkey")
psk_key = rn_exec("docker run --rm amneziavpn/amnezia-wg:latest wg genpsk")

print(f"Generated Keys for Racknerd:")
print(f"PrivKey: {priv_key}")
print(f"PubKey:  {pub_key}")
print(f"PSKKey:  {psk_key}")

# Prepare wg0.conf on Racknerd
awg_params = {
    "H1": 1155587185, "H2": 905802652, "H3": 749941050, "H4": 74677149,
    "Jc": 3, "Jmin": 10, "Jmax": 50,
    "S1": 228, "S2": 193, "S3": 30, "S4": 15
}

wg_conf = f"""[Interface]
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

# iptables rules
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {{print $5}}') -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o $(ip route show default | awk '/default/ {{print $5}}') -j MASQUERADE
"""

sftp = ssh_rn.open_sftp()
with sftp.file('/opt/amnezia/awg/wg0.conf', 'w') as f:
    f.write(wg_conf)
sftp.close()

# Start amnezia-awg2 container properly using wg-quick up wg0
rn_exec("docker run -d --name amnezia-awg2 --restart always --cap-add=NET_ADMIN --cap-add=SYS_MODULE -v /opt/amnezia/awg:/opt/amnezia -p 59515:59515/udp amneziavpn/amnezia-wg:latest wg-quick up /opt/amnezia/wg0.conf")
print("AWG2 Container started on Racknerd!")

ssh_rn.close()

# 2. Update MySQL database in amnezia-panel-db on Master Server (5.129.229.25)
ssh_m = paramiko.SSHClient()
ssh_m.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_m.connect('5.129.229.25', username='root', password='x_8,,_CJMuvhwj')

awg_json = json.dumps(awg_params).replace('"', '\\"')

sql_update = f"""UPDATE vpn_servers SET server_public_key = '{pub_key}', preshared_key = '{psk_key}', awg_params = '{awg_json}', status = 'active', error_message = NULL WHERE id = 3;"""
cmd_db = f'docker exec amnezia-panel-db mysql -u amnezia -pamnezia amnezia_panel -e "{sql_update}"'
_, stdout, stderr = ssh_m.exec_command(cmd_db)
print("DB Update result:", stdout.read().decode(), stderr.read().decode())

# Check updated record
_, stdout_check, _ = ssh_m.exec_command('docker exec amnezia-panel-db mysql -u amnezia -pamnezia amnezia_panel -e "SELECT id, name, host, status, server_public_key FROM vpn_servers WHERE id = 3;"')
print("Updated record:\n", stdout_check.read().decode())

ssh_m.close()
