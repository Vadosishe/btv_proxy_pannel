import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('23.95.48.191', username='root', password='C0x1C3xrdG0t0W1YTk')

def run(cmd):
    print(f"\n[RUN] {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print("[STDOUT]\n", out)
    if err: print("[STDERR]\n", err)
    return out

# Ensure directory exists
run("mkdir -p /opt/amnezia/awg")

# Run amnezia-awg2 container if not running
run("docker run -d --name amnezia-awg2 --restart always --cap-add=NET_ADMIN --cap-add=SYS_MODULE -v /opt/amnezia/awg:/opt/amnezia -p 59515:59515/udp amneziavpn/amnezia-wg:latest")

run("docker ps")

ssh.close()
