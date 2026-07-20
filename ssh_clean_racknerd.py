import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "23.95.48.191"
USER = "root"
PASS = "C0x1C3xrdG0t0W1YTk"

def run_clean():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[*] Connecting to RackNerd VPS {HOST}...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)
    print("[+] Connected!")

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

    # 1. Audit existing running items
    print("\n--- Current Docker status ---")
    exec_cmd("docker ps -a 2>/dev/null || true")

    print("\n--- Current /opt & /srv directories ---")
    exec_cmd("ls -la /opt; ls -la /srv 2>/dev/null || true")

    # 2. Stop and remove all docker containers, networks, volumes
    print("\n--- Stopping & Removing Docker Containers and Networks ---")
    exec_cmd("docker stop $(docker ps -aq) 2>/dev/null || true")
    exec_cmd("docker rm $(docker ps -aq) 2>/dev/null || true")
    exec_cmd("docker system prune -a --volumes -f 2>/dev/null || true")

    # 3. Clean up leftover directories
    print("\n--- Cleaning up leftover folders ---")
    exec_cmd("rm -rf /opt/amnezia /opt/amneziavpnphp /opt/btv_proxy_pannel /srv/docker 2>/dev/null || true")

    # 4. Flush iptables rules
    print("\n--- Resetting iptables ---")
    exec_cmd("iptables -F; iptables -X; iptables -t nat -F; iptables -t nat -X; iptables -P INPUT ACCEPT; iptables -P FORWARD ACCEPT; iptables -P OUTPUT ACCEPT")

    # 5. Verify clean state
    print("\n--- Verification ---")
    exec_cmd("docker ps -a 2>/dev/null || true")
    exec_cmd("ls -la /opt")

    ssh.close()
    print("\n[+] RackNerd VPS is clean!")

if __name__ == "__main__":
    run_clean()
