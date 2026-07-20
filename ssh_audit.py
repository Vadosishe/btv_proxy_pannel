import paramiko

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def run_remote():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)
    print("Connected successfully!\n")

    commands = [
        ("System Info", "uname -a; cat /etc/os-release | grep PRETTY_NAME"),
        ("Memory & Disk", "free -h; echo '---'; df -h"),
        ("Running Docker Containers", "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"),
        ("Active Listening Ports", "ss -tulpn | grep LISTEN"),
        ("Directories in /opt and /srv", "ls -la /opt; echo '---'; ls -la /srv 2>/dev/null || true"),
        ("Running Systemd Services", "systemctl list-units --type=service --state=running | head -n 30")
    ]

    for title, cmd in commands:
        print(f"=== {title} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        if out:
            print(out.strip())
        if err:
            print(f"[STDERR]\n{err.strip()}")
        print("\n")

    ssh.close()

if __name__ == "__main__":
    run_remote()
