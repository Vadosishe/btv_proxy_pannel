import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def run_logs():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    commands = [
        ("Docker PS", "docker ps -a"),
        ("Backend Logs", "docker logs --tail 50 b2b-vpn-backend"),
        ("DB Logs", "docker logs --tail 20 b2b-vpn-db"),
        ("Curl from inside server", "curl -v http://127.0.0.1:8000 || true")
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
    run_logs()
