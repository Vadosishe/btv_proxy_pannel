import paramiko

HOST = "5.129.229.25"
USER = "root"
PASSWORD = "x_8,,_CJMuvhwj"

MIGRATION_PY = r'''
import os
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://vpn_user:vpn_password_secret@postgres:5432/b2b_vpn")
# Parse
parts = DB_URL.replace("postgresql://", "").split("@")
user_pass = parts[0].split(":")
host_db = parts[1].split("/")
host_port = host_db[0].split(":")

conn = psycopg2.connect(
    host=host_port[0], port=int(host_port[1]),
    user=user_pass[0], password=user_pass[1],
    database=host_db[1]
)
conn.autocommit = True
c = conn.cursor()

# Create templates table
c.execute("""
CREATE TABLE IF NOT EXISTS templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
)
""")
print("Created templates table")

# Create template_nodes m2m
c.execute("""
CREATE TABLE IF NOT EXISTS template_nodes (
    template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    PRIMARY KEY (template_id, node_id)
)
""")
print("Created template_nodes table")

# Create employees table
c.execute("""
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    agency_id INTEGER NOT NULL REFERENCES agencies(id),
    secret_uuid VARCHAR UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
)
""")
print("Created employees table")

# Add template_id to agencies
try:
    c.execute("ALTER TABLE agencies ADD COLUMN template_id INTEGER REFERENCES templates(id)")
    print("Added template_id to agencies")
except Exception as e:
    print(f"agencies.template_id: {e}")

# Add employee_id to client_keys
try:
    c.execute("ALTER TABLE client_keys ADD COLUMN employee_id INTEGER REFERENCES employees(id)")
    print("Added employee_id to client_keys")
except Exception as e:
    print(f"client_keys.employee_id: {e}")

# Verify
c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
print("Tables:", [r[0] for r in c.fetchall()])

c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='agencies' ORDER BY ordinal_position")
print("Agencies cols:", [r[0] for r in c.fetchall()])

c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='employees' ORDER BY ordinal_position")
print("Employees cols:", [r[0] for r in c.fetchall()])

c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='client_keys' ORDER BY ordinal_position")
print("ClientKeys cols:", [r[0] for r in c.fetchall()])

conn.close()
print("Migration complete!")
'''

def run():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD)
    
    escaped = MIGRATION_PY.replace("'", "'\\''")
    cmd = f"docker exec b2b-vpn-backend python -c '{escaped}'"
    
    print("Running PostgreSQL migration inside docker container...")
    stdin, stdout, stderr = c.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"stderr: {err}")
    
    c.close()

if __name__ == "__main__":
    run()
