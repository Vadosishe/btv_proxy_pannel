import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "5.129.229.25"
USER = "root"
PASS = "x_8,,_CJMuvhwj"

def debug_nodes():
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

    print("\n--- Current Nodes in DB ---")
    exec_cmd("""docker exec -i b2b-vpn-backend python -c "
from app.database import SessionLocal
from app.models import Node

db = SessionLocal()
nodes = db.query(Node).all()
for n in nodes:
    print(f'ID: {n.id} | Name: {n.name} | Type: {n.node_type} | URL: {n.xui_url} | Token: {n.xui_api_token} | User: {n.xui_username} | Pass: {n.xui_password} | InboundID: {n.xui_inbound_id} | AmneziaServerID: {n.amnezia_server_id}')
db.close()
" """)

    print("\n--- Running Node Test for all Nodes ---")
    exec_cmd("""docker exec -i b2b-vpn-backend python -c "
import asyncio
from app.database import SessionLocal
from app.models import Node
from app.services.xui import XUIClient
from app.services.amnezia import AmneziaClient
from app.config import settings

async def test_all():
    db = SessionLocal()
    nodes = db.query(Node).all()
    for n in nodes:
        print(f'Testing Node {n.id} ({n.name})...')
        if n.node_type == 'xui':
            print(f'Attempting 3X-UI connection to {n.xui_url}...')
            try:
                xui = XUIClient(n.xui_url, username=n.xui_username, password=n.xui_password, api_token=n.xui_api_token)
                res = await xui.login()
                print(f'3X-UI Login Result: {res}')
            except Exception as e:
                print(f'3X-UI Login Error: {e}')
        else:
            print(f'Attempting Amnezia connection to master {settings.AMNEZIA_API_URL} for Server ID {n.amnezia_server_id}...')
            try:
                amnezia = AmneziaClient(settings.AMNEZIA_API_URL, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
                res = await amnezia.login()
                print(f'Amnezia Login Result: {res}')
            except Exception as e:
                print(f'Amnezia Login Error: {e}')
    db.close()

asyncio.run(test_all())
" """)

    ssh.close()

if __name__ == "__main__":
    debug_nodes()
