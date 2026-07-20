import paramiko, json

# 1. Clean up Racknerd server (23.95.48.191)
print("[1] Cleaning Racknerd VPS (23.95.48.191)...")
ssh_rn = paramiko.SSHClient()
ssh_rn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_rn.connect('23.95.48.191', username='root', password='C0x1C3xrdG0t0W1YTk')

def rn_exec(cmd):
    _, stdout, stderr = ssh_rn.exec_command(cmd)
    return stdout.read().decode().strip()

rn_exec("docker rm -f $(docker ps -aq) 2>/dev/null || true")
rn_exec("rm -rf /opt/amnezia")
print("Racknerd containers and /opt/amnezia purged!")
ssh_rn.close()

# 2. Clean up Master server (5.129.229.25)
print("\n[2] Deleting Racknerd server record from Amnezia MySQL & ScaleBoX Postgres...")
ssh_m = paramiko.SSHClient()
ssh_m.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_m.connect('5.129.229.25', username='root', password='x_8,,_CJMuvhwj')

# MySQL delete
ssh_m.exec_command('docker exec amnezia-panel-db mysql -u amnezia -pamnezia amnezia_panel -e "DELETE FROM server_metrics WHERE server_id = 3; DELETE FROM server_protocols WHERE server_id = 3; DELETE FROM vpn_servers WHERE id = 3;"')

# Postgres delete Node id 4
ssh_m.exec_command('docker exec b2b-vpn-db psql -U postgres -d b2b_vpn -c "DELETE FROM client_keys WHERE node_id = 4; DELETE FROM nodes WHERE id = 4;"')

print("Deleted server 3 from MySQL and node 4 from Postgres!")

# Restart containers
ssh_m.exec_command("docker restart amnezia-panel-web b2b-vpn-backend")
print("Restarted amnezia-panel-web and b2b-vpn-backend!")

ssh_m.close()
