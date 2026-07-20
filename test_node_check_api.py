import httpx

API_BASE = "http://5.129.229.25:8000/api"

def test_check():
    print("[1] Logging in as SuperAdmin...")
    res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[2] Testing connection to Node 5 (Timeweb BTV)...")
    res5 = httpx.post(f"{API_BASE}/admin/nodes/5/test", headers=headers)
    print("Node 5 Test Status:", res5.status_code)
    print("Node 5 Test Body:", res5.json())

    print("\n[3] Testing connection to Node 4 (Racknerd Chicago)...")
    res4 = httpx.post(f"{API_BASE}/admin/nodes/4/test", headers=headers)
    print("Node 4 Test Status:", res4.status_code)
    print("Node 4 Test Body:", res4.json())

if __name__ == "__main__":
    test_check()
