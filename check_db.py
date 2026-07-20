import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.129.229.25', username='root', password='x_8,,_CJMuvhwj')

def exec_sql(sql):
    cmd = f'docker exec amnezia-panel-db mysql -u amnezia -pamnezia amnezia_panel -e "{sql}"'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()

print("=== DELETING SERVER 4 (Aeza fin) FROM DATABASE ===")
exec_sql("DELETE FROM server_metrics WHERE server_id = 4;")
exec_sql("DELETE FROM server_protocols WHERE server_id = 4;")
exec_sql("DELETE FROM vpn_servers WHERE id = 4;")

out_after, _ = exec_sql("SELECT id, name, host, status FROM vpn_servers;")
print("=== REMAINING SERVERS IN DB ===")
print(out_after)

# Kill hanging SSH processes and restart panel container
ssh.exec_command("docker exec amnezia-panel-web killall -9 ssh sshpass 2>/dev/null || true; docker restart amnezia-panel-web")
print("=== RESTARTED AMNEZIA-PANEL-WEB ===")
ssh.close()
