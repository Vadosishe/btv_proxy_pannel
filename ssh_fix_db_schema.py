import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

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

    print("\n--- Backend Error Logs ---")
    exec_cmd("docker logs --tail 30 b2b-vpn-backend")

    print("\n--- Migrating Postgres Database Columns ---")
    migration_sql = """
    ALTER TABLE nodes ADD COLUMN IF NOT EXISTS node_type VARCHAR DEFAULT 'xui';
    ALTER TABLE nodes ADD COLUMN IF NOT EXISTS xui_api_token VARCHAR;
    ALTER TABLE nodes ADD COLUMN IF NOT EXISTS amnezia_url VARCHAR;
    """

    exec_cmd(f"""docker exec -i b2b-vpn-db psql -U vpn_user -d b2b_vpn -c "{migration_sql}" """)

    print("\n--- Restarting b2b-vpn-backend ---")
    exec_cmd("docker restart b2b-vpn-backend")

    ssh.close()

if __name__ == "__main__":
    run_fix()
