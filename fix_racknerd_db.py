import paramiko, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.129.229.25', username='root', password='x_8,,_CJMuvhwj')

def exec_sql(sql):
    cmd = f'docker exec amnezia-panel-db mysql -u amnezia -pamnezia amnezia_panel -e "{sql}"'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode()

print("=== SERVER 3 IN MYSQL ===")
out = exec_sql("SELECT id, name, host, status, server_public_key, preshared_key, error_message FROM vpn_servers WHERE id = 3;")
print(out)

ssh.close()
