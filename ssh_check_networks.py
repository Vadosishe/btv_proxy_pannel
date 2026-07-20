import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def check_networks():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    def exec_cmd(cmd):
        print(f"\n[RUN] {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        if out:
            print(f"[STDOUT]\n{out}")
        if err:
            print(f"[STDERR]\n{err}")
        return out

    exec_cmd("docker network ls")
    exec_cmd("docker inspect amnezia-panel-web | grep -i IPAddress")
    exec_cmd("docker inspect b2b-vpn-backend | grep -i IPAddress")

    # Connect b2b-vpn-backend to amneziavpnphp network
    exec_cmd("docker network connect amneziavpnphp_default b2b-vpn-backend 2>/dev/null || true")

    # Test curl from b2b-vpn-backend to amnezia-panel-web
    exec_cmd("docker exec b2b-vpn-backend curl -I http://amnezia-panel-web:80")

    ssh.close()

if __name__ == "__main__":
    check_networks()
