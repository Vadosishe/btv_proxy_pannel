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

    # 1. Fix dpkg
    exec_cmd("dpkg --configure -a")

    # 2. Download correct tarball x-ui-linux-amd64.tar.gz
    print("\n--- Downloading 3X-UI v3.5.0 ---")
    exec_cmd("cd /root && wget -q -O x-ui-linux-amd64.tar.gz https://github.com/mhsanaei/3x-ui/releases/download/v3.5.0/x-ui-linux-amd64.tar.gz")
    
    # 3. Extract and configure
    exec_cmd("rm -rf /usr/local/x-ui && tar zxf /root/x-ui-linux-amd64.tar.gz -C /usr/local/")
    exec_cmd("cp -f /usr/local/x-ui/x-ui.service /etc/systemd/system/x-ui.service || cp -f /usr/local/x-ui/x-ui.service.debian /etc/systemd/system/x-ui.service")
    
    exec_cmd("cd /usr/local/x-ui && chmod +x x-ui bin/xray-linux-amd64 && ./x-ui setting -username admin -password admin -port 2053")
    
    # 4. Enable and start service
    exec_cmd("systemctl daemon-reload && systemctl enable x-ui && systemctl restart x-ui")

    # 5. Verification
    print("\n--- Verifying 3X-UI Status ---")
    exec_cmd("systemctl status x-ui | head -n 15")
    exec_cmd("ss -tulpn | grep -E '(53|2053)'")

    ssh.close()

if __name__ == "__main__":
    run_fix()
