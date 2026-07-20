import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "23.95.48.191"
USER = "root"
PASS = "C0x1C3xrdG0t0W1YTk"

def run_setup():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[*] Connecting to RackNerd VPS {HOST} to setup Node...")
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

    # Fetch setup-node.sh script from raw GitHub and execute
    setup_script_url = "https://raw.githubusercontent.com/Vadosishe/btv_proxy_pannel/main/scripts/setup-node.sh"
    exec_cmd(f"curl -sSL {setup_script_url} | bash || true")

    # Check status of AdGuard Home container and open listening ports
    exec_cmd("docker ps")
    exec_cmd("ss -tulpn | grep -E '(53|2053|2096|443)'")

    ssh.close()
    print("\n[+] Node setup completed on RackNerd VPS!")

if __name__ == "__main__":
    run_setup()
