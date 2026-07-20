import httpx

API_BASE = "http://5.129.229.25:8000/api"

def test_sync_call():
    print("[1] Logging into B2B Orchestrator...")
    res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[2] Requesting /api/admin/keys...")
    keys_res = httpx.get(f"{API_BASE}/admin/keys", headers=headers, timeout=60.0)
    print("Status:", keys_res.status_code)
    keys = keys_res.json()
    print("Total Keys:", len(keys))
    for k in keys:
        print(f"ID: {k['id']}, Name: '{k['employee_name']}', RemoteID: {k.get('remote_client_id')}, Protocol: {k['protocol']}")

if __name__ == "__main__":
    test_sync_call()
