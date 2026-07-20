import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def check_laravel_logs():
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

    exec_cmd("docker exec amnezia-panel-web tail -n 50 storage/logs/laravel.log 2>/dev/null || docker exec amnezia-panel-web cat storage/logs/laravel.log 2>/dev/null || true")

    ssh.close()

if __name__ == "__main__":
    check_laravel_logs()
