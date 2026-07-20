import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('5.129.229.25', username='root', password='x_8,,_CJMuvhwj')

_, stdout, _ = ssh.exec_command('docker inspect amnezia-awg2 --format "{{.Path}} {{.Args}} | HostConfig: {{.HostConfig.CapAdd}} {{.HostConfig.Privileged}}"')
print("=== MASTER AWG2 CONTAINER CONFIG ===")
print(stdout.read().decode())

ssh.close()
