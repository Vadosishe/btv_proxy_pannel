import httpx

API_BASE = "http://5.129.229.25:8000/api"

print("[1] Logging in as SuperAdmin...")
res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("\n[2] Testing connection to Node ID 3 (Racknerd Chicago)...")
test_res = httpx.post(f"{API_BASE}/admin/nodes/3/test", headers=headers, timeout=30.0)
print("Status:", test_res.status_code)
print("Result:", test_res.json())
