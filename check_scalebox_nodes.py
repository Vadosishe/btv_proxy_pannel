import httpx

API_BASE = "http://5.129.229.25:8000/api"

res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

nodes = httpx.get(f"{API_BASE}/admin/nodes", headers=headers).json()
print("=== SCALEBOX NODES ===")
print(nodes)
