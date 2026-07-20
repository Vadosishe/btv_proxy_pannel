import httpx

MASTER_URL = "http://5.129.229.25:8000"

def add_node_to_master():
    # 1. Login as SuperAdmin
    print("[*] Logging into Master Orchestrator...")
    resp = httpx.post(f"{MASTER_URL}/api/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
    if resp.status_code != 200:
        print(f"[!] Login failed: {resp.text}")
        return

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Add RackNerd USA Node
    node_payload = {
        "name": "США (Чикаго)",
        "location": "US",
        "xui_url": "http://23.95.48.191:2053",
        "xui_username": "admin",
        "xui_password": "admin",
        "xui_inbound_id": 1,
        "amnezia_server_id": 1
    }

    print("[*] Registering RackNerd USA Node in Master Orchestrator...")
    node_resp = httpx.post(f"{MASTER_URL}/api/admin/nodes", json=node_payload, headers=headers)
    if node_resp.status_code == 200:
        print("[+] RackNerd USA Node successfully added to Master Orchestrator!")
        print("Node details:", node_resp.json())
    else:
        print(f"[!] Failed to add node: {node_resp.text}")

if __name__ == "__main__":
    add_node_to_master()
