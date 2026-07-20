import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def run_rebuild():
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

    print("\n--- Pulling latest code and rebuilding btv_proxy_pannel ---")
    exec_cmd("cd /opt/btv_proxy_pannel && git pull && docker compose up -d --build")

    print("\n--- Seeding SuperAdmin user ---")
    seed_cmd = """docker exec -i b2b-vpn-backend python -c "
from app.database import SessionLocal
from app.models import User, UserRole
from app.routers.auth import get_password_hash

db = SessionLocal()
user = db.query(User).filter(User.email == 'admin@b2b.com').first()
if not user:
    admin = User(
        email='admin@b2b.com',
        password_hash=get_password_hash('admin123'),
        role=UserRole.SUPERADMIN
    )
    db.add(admin)
    db.commit()
    print('SuperAdmin created: admin@b2b.com / admin123')
else:
    print('SuperAdmin already exists.')
db.close()
" """
    exec_cmd(seed_cmd)

    print("\n--- Verifying Docker PS ---")
    exec_cmd("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'")

    ssh.close()

if __name__ == "__main__":
    run_rebuild()
