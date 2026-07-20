import paramiko

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def run_remote():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)

    commands = [
        ("Amnezia Opt Dir", "ls -la /opt/amnezia"),
        ("Srv Docker Dir", "ls -la /srv/docker; find /srv/docker -maxdepth 3"),
        ("Systemd 3xui bot service content", "cat /etc/systemd/system/3xui-central-bot.service 2>/dev/null || cat /lib/systemd/system/3xui-central-bot.service 2>/dev/null"),
        ("Checking if amneziavpnphp exists", "docker ps -a | grep amnezia; find / -name 'amneziavpnphp' 2>/dev/null")
    ]

    for title, cmd in commands:
        print(f"=== {title} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode('utf-8', errors='replace').strip())
        print("\n")

    ssh.close()

if __name__ == "__main__":
    run_remote()
