import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "23.95.48.191"
USER = "root"
PASS = "C0x1C3xrdG0t0W1YTk"

def run_awg_container():
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

    exec_cmd("docker rm -f amnezia-awg2 2>/dev/null || true")
    exec_cmd("docker run -d --name amnezia-awg2 --privileged --cap-add=NET_ADMIN --restart=always -p 47111:47111/udp amneziavpn/amnezia-wg:latest")
    exec_cmd("docker ps")

    ssh.close()

if __name__ == "__main__":
    run_awg_container()
