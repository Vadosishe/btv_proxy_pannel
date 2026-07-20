import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "23.95.48.191"
USER = "root"
PASS = "C0x1C3xrdG0t0W1YTk"

def run_local_setup():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15)

    with open("scripts/setup-node.sh", "r", encoding="utf-8") as f:
        script_content = f.read()

    sftp = ssh.open_sftp()
    with sftp.file("/tmp/setup-node.sh", "w") as remote_file:
        remote_file.write(script_content)
    sftp.close()

    print("\n--- Executing uploaded setup-node.sh ---")
    stdin, stdout, stderr = ssh.exec_command("chmod +x /tmp/setup-node.sh && /tmp/setup-node.sh")
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        print(f"[STDOUT]\n{out}")
    if err:
        print(f"[STDERR]\n{err}")

    print("\n--- Verifying Docker containers & listening ports ---")
    stdin, stdout, stderr = ssh.exec_command("docker ps -a; echo '---'; ss -tulpn | grep -E '(53|2053|2096|443)'")
    print(stdout.read().decode('utf-8', errors='replace').strip())

    ssh.close()

if __name__ == "__main__":
    run_local_setup()
