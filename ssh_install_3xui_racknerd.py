import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "23.95.48.191"
USER = "root"
PASS = "C0x1C3xrdG0t0W1YTk"

def run_install():
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

    # Kill leftover apt processes
    exec_cmd("killall apt apt-get dpkg 2>/dev/null || true")

    # Install 3X-UI non-interactively
    print("\n--- Installing 3X-UI v3 Node ---")
    exec_cmd("printf 'y\n2053\nadmin\nadmin\n' | bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)")

    # Apply iptables security rules
    print("\n--- Applying Anti-Abuse Firewall rules ---")
    exec_cmd("iptables -t nat -A PREROUTING -p udp --dport 53 -j REDIRECT --to-ports 53 || true")
    exec_cmd("iptables -t nat -A PREROUTING -p tcp --dport 53 -j REDIRECT --to-ports 53 || true")
    exec_cmd("iptables -A OUTPUT -p tcp --dport 25 -j DROP || true")
    exec_cmd("iptables -A OUTPUT -p tcp --dport 465 -j DROP || true")
    exec_cmd("iptables -A OUTPUT -p tcp --dport 587 -j DROP || true")

    # Verification
    print("\n--- Verifying Docker containers & 3X-UI status ---")
    exec_cmd("docker ps; x-ui status 2>/dev/null || true")
    exec_cmd("ss -tulpn | grep -E '(53|2053)'")

    ssh.close()

if __name__ == "__main__":
    run_install()
