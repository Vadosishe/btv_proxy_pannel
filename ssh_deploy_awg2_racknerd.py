import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "23.95.48.191"
USER = "root"
PASS = "C0x1C3xrdG0t0W1YTk"

def deploy_awg2():
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

    print("\n--- Pulling amneziavpn/amnezia-wg ---")
    exec_cmd("docker pull amneziavpn/amnezia-wg:latest || true")
    exec_cmd("docker tag amneziavpn/amnezia-wg:latest amnezia-awg2:latest || true")

    exec_cmd("docker ps -a")

    ssh.close()

if __name__ == "__main__":
    deploy_awg2()
