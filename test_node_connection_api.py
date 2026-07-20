import httpx

API_BASE = "http://5.129.229.25:8000/api"

def test_nodes():
    login_res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    nodes = httpx.get(f"{API_BASE}/admin/nodes", headers=headers).json()
    print("Fetched Nodes Count:", len(nodes))
    for n in nodes:
        node_id = n["id"]
        test_res = httpx.post(f"{API_BASE}/admin/nodes/{node_id}/test", headers=headers)
        print(f"Node {node_id} ({n['name']}) Test Status:", test_res.status_code, test_res.json())

if __name__ == "__main__":
    test_nodes()
