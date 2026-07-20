import httpx

API_BASE = "http://5.129.229.25:8000/api"

print("[1] Logging in as SuperAdmin...")
res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("\n[2] Creating key on Node ID 4 (Racknerd Chicago, Server ID 3)...")
create_res = httpx.post(f"{API_BASE}/admin/keys/create?agency_id=1&employee_name=Test_Racknerd_User&protocol=awg&node_id=4", headers=headers, timeout=60.0)
print("Status:", create_res.status_code)
print("Result:", create_res.json())
