import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('23.95.48.191', username='root', password='C0x1C3xrdG0t0W1YTk')

_, stdout, _ = ssh.exec_command('docker exec amnezia-awg2 which wg amnezia-wg awg 2>&1')
print("=== WHICH WG IN CONTAINER ===")
print(stdout.read().decode())

_, stdout_path, _ = ssh.exec_command('docker exec amnezia-awg2 find / -name "*wg*" 2>/dev/null')
print("=== WG PATHS IN CONTAINER ===")
print(stdout_path.read().decode())

ssh.close()
