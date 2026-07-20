import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "23.95.48.191"
USER = "root"
PASS = "C0x1C3xrdG0t0W1YTk"

def run_fix():
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

    # Kill apt locks
    exec_cmd("kill -9 $(pgrep apt) 2>/dev/null || true; rm -f /var/lib/apt/lists/lock /var/lib/dpkg/lock*")

    # Install dependencies
    exec_cmd("apt-get update -y && apt-get install -y tar wget curl net-tools")

    # Download 3X-UI release directly and install
    print("\n--- Downloading and installing 3X-UI v3 ---")
    exec_cmd("cd /root && wget -O x-ui-linux-amd6.tar.gz https://github.com/mhsanaei/3x-ui/releases/latest/download/x-ui-linux-amd6.tar.gz")
    exec_cmd("rm -rf /usr/local/x-ui && tar zxvf /root/x-ui-linux-amd6.tar.gz -C /usr/local/")
    exec_cmd("cd /usr/local/x-ui && chmod +x x-ui bin/xray-linux-amd6 && ./x-ui setting -username admin -password admin -port 2053 && ./x-ui run &")
    
    # Install x-ui service
    exec_cmd("cp -f /usr/local/x-ui/x-ui.service /etc/systemd/system/x-ui.service || true; systemctl daemon-reload; systemctl enable x-ui; systemctl start x-ui")

    # Verify status
    print("\n--- Verification ---")
    exec_cmd("systemctl status x-ui | head -n 15")
    exec_cmd("ss -tulpn | grep -E '(53|2053)'")

    ssh.close()

if __name__ == "__main__":
    run_fix()
