import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def run_firewall():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    commands = [
        ("UFW Status", "ufw status verbose"),
        ("Allowing ports 8000 & 8082 in UFW", "ufw allow 8000/tcp; ufw allow 8082/tcp; ufw reload || true"),
        ("Checking iptables docker rules", "iptables -L INPUT -n --line-numbers | head -n 20")
    ]

    for title, cmd in commands:
        print(f"=== {title} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode('utf-8', errors='replace').strip())
        print("\n")

    ssh.close()

if __name__ == "__main__":
    run_firewall()
