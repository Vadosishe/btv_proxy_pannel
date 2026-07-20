import httpx

API_BASE = "http://5.129.229.25:8000/api"

def test_add_nodes():
    print("[1] Logging into SuperAdmin...")
    login_res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("[2] Adding AmneziaWG Node (Server ID: 2 - BTV)...")
    amnezia_node_payload = {
        "name": "BTV Финляндия (AmneziaWG)",
        "location": "FI",
        "node_type": "amnezia",
        "amnezia_server_id": 2
    }
    res_amnezia = httpx.post(f"{API_BASE}/admin/nodes", json=amnezia_node_payload, headers=headers)
    print("Amnezia Node Add Result:", res_amnezia.status_code, res_amnezia.json())

    print("[3] Adding 3X-UI Node (RackNerd Chicago)...")
    xui_node_payload = {
        "name": "RackNerd США (3X-UI VLESS)",
        "location": "US",
        "node_type": "xui",
        "xui_url": "http://23.95.48.191:2053",
        "xui_username": "admin",
        "xui_password": "admin",
        "xui_inbound_id": 1
    }
    res_xui = httpx.post(f"{API_BASE}/admin/nodes", json=xui_node_payload, headers=headers)
    print("3X-UI Node Add Result:", res_xui.status_code, res_xui.json())

    print("[4] Listing all nodes...")
    nodes_res = httpx.get(f"{API_BASE}/admin/nodes", headers=headers)
    print("All Nodes in system:", nodes_res.json())

if __name__ == "__main__":
    test_add_nodes()
