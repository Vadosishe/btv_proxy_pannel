import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('23.95.48.191', username='root', password='C0x1C3xrdG0t0W1YTk')

_, stdout, _ = ssh.exec_command('docker inspect trusting_hofstadter --format "{{.Path}} {{.Args}} | Exit: {{.State.ExitCode}}"')
print("=== INSPECT CONTAINER ===")
print(stdout.read().decode())

ssh.close()
