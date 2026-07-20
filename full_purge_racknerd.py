import paramiko

# 1. Clean Racknerd VPS (23.95.48.191)
print("[1] Purging Racknerd VPS (23.95.48.191)...")
ssh_rn = paramiko.SSHClient()
ssh_rn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_rn.connect('23.95.48.191', username='root', password='C0x1C3xrdG0t0W1YTk')

def rn_exec(cmd):
    _, stdout, stderr = ssh_rn.exec_command(cmd)
    return stdout.read().decode().strip()

rn_exec("docker rm -f $(docker ps -aq) 2>/dev/null || true")
rn_exec("docker system prune -af 2>/dev/null || true")
rn_exec("rm -rf /opt/amnezia")
print("Racknerd VPS completely clean!")
ssh_rn.close()

# 2. Clean Master server databases (5.129.229.25)
print("\n[2] Purging Racknerd records from Amnezia MySQL & ScaleBoX Postgres...")
ssh_m = paramiko.SSHClient()
ssh_m.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_m.connect('5.129.229.25', username='root', password='x_8,,_CJMuvhwj')

def m_exec(cmd):
    _, stdout, stderr = ssh_m.exec_command(cmd)
    return stdout.read().decode().strip()

# Delete server records matching host '23.95.48.191' or name Racknerd
m_exec('docker exec amnezia-panel-db mysql -u amnezia -pamnezia amnezia_panel -e "DELETE FROM server_metrics WHERE server_id IN (SELECT id FROM vpn_servers WHERE host=\'23.95.48.191\' OR name LIKE \'%rack%\'); DELETE FROM server_protocols WHERE server_id IN (SELECT id FROM vpn_servers WHERE host=\'23.95.48.191\' OR name LIKE \'%rack%\'); DELETE FROM vpn_servers WHERE host=\'23.95.48.191\' OR name LIKE \'%rack%\';"')

# Postgres delete nodes and keys
m_exec('docker exec b2b-vpn-db psql -U postgres -d b2b_vpn -c "DELETE FROM client_keys WHERE node_id IN (SELECT id FROM nodes WHERE name LIKE \'%Racknerd%\'); DELETE FROM nodes WHERE name LIKE \'%Racknerd%\';"')

# Restart panel containers
m_exec("docker restart amnezia-panel-web b2b-vpn-backend")
print("Restarted amnezia-panel-web and b2b-vpn-backend!")

ssh_m.close()
