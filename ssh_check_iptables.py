import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def run_check():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    commands = [
        ("Checking iptables rules", "iptables -L -n -v | head -n 40"),
        ("Checking iptables DOCKER-USER chain", "iptables -L DOCKER-USER -n -v 2>/dev/null || true"),
        ("Checking iptables FORWARD chain", "iptables -L FORWARD -n -v 2>/dev/null || true"),
        ("Checking listening ports on 0.0.0.0", "netstat -tulpn | grep -E '(8000|8082)' || ss -tulpn | grep -E '(8000|8082)'"),
        ("Allowing port 8000 & 8082 in iptables INPUT & DOCKER-USER", "iptables -I INPUT -p tcp --dport 8000 -j ACCEPT; iptables -I INPUT -p tcp --dport 8082 -j ACCEPT; iptables -I DOCKER-USER -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true; iptables -I DOCKER-USER -p tcp --dport 8082 -j ACCEPT 2>/dev/null || true")
    ]

    for title, cmd in commands:
        print(f"=== {title} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if out:
            print(f"[STDOUT]\n{out}")
        if err:
            print(f"[STDERR]\n{err}")
        print("\n")

    ssh.close()

if __name__ == "__main__":
    run_check()
