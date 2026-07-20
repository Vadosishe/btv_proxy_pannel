import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def run_deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[*] Connecting to {HOST}...")
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

    # 1. Continue amneziavpnphp setup
    print("\n--- Starting amneziavpnphp containers ---")
    exec_cmd("cd /opt/amneziavpnphp && docker compose up -d")

    # 2. Deploy btv_proxy_pannel on port 8000
    print("\n--- Deploying btv_proxy_pannel B2B Orchestrator ---")
    exec_cmd("mkdir -p /opt/btv_proxy_pannel && cd /opt && [ ! -d /opt/btv_proxy_pannel/.git ] && git clone https://github.com/Vadosishe/btv_proxy_pannel.git /opt/btv_proxy_pannel || (cd /opt/btv_proxy_pannel && git pull)")
    exec_cmd("cd /opt/btv_proxy_pannel && docker compose up -d --build")

    # 3. Final verification
    print("\n--- Verifying Running Containers ---")
    exec_cmd("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")

    print("\n--- Verifying Listening Ports ---")
    exec_cmd("ss -tulpn | grep -E '(8000|8082|2096|443)'")

    ssh.close()
    print("\n[+] All services deployed successfully!")

if __name__ == "__main__":
    run_deploy()
