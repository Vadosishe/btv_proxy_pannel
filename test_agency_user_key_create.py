import httpx

API_BASE = "http://5.129.229.25:8000/api"

def test_user_flow():
    print("[1] Logging in as yi@bigtimeit.ai...")
    res = httpx.post(f"{API_BASE}/auth/login", data={"username": "yi@bigtimeit.ai", "password": "Wwe-72J-Fja-tA5"})
    print("Login Status:", res.status_code, res.json())
    if res.status_code != 200:
        return

    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[2] Fetching Agency Info...")
    agency_res = httpx.get(f"{API_BASE}/agency/me", headers=headers)
    print("Agency Info:", agency_res.status_code, agency_res.json())

    print("\n[3] Fetching Nodes...")
    nodes_res = httpx.get(f"{API_BASE}/admin/nodes", headers=headers)
    print("Nodes:", nodes_res.status_code, nodes_res.json())
    nodes = nodes_res.json()
    if not nodes:
        print("[!] No nodes found!")
        return

    node = nodes[0]
    print(f"\n[4] Attempting key creation on Node {node['id']} ({node['name']}, type: {node['node_type']})...")
    payload = {
        "employee_name": "Тестовый Сотрудник",
        "protocol": "awg" if node['node_type'] == 'amnezia' else "vless",
        "node_id": node['id']
    }
    key_res = httpx.post(f"{API_BASE}/agency/keys/create", json=payload, headers=headers, timeout=30.0)
    print("Key Create Status:", key_res.status_code)
    try:
        print("Key Create Result:", key_res.json())
    except:
        print("Raw text:", key_res.text)

if __name__ == "__main__":
    test_user_flow()
