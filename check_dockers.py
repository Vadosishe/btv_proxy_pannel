import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('23.95.48.191', username='root', password='C0x1C3xrdG0t0W1YTk')

_, stdout, _ = ssh.exec_command('docker info 2>&1')
print("=== DOCKER INFO ===")
print(stdout.read().decode('utf-8', errors='replace')[:500])

ssh.close()
