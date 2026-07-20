import httpx

API_BASE = "http://5.129.229.25:8000/api"

def test_superadmin_create():
    print("[1] Logging in as SuperAdmin...")
    res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[2] Attempting SuperAdmin key creation for Agency 1 on Node 5...")
    params = {
        "agency_id": 1,
        "employee_name": "Суперадмин Выпуск",
        "protocol": "awg",
        "node_id": 5
    }
    key_res = httpx.post(f"{API_BASE}/admin/keys/create", params=params, headers=headers, timeout=60.0)
    print("SuperAdmin Key Create Status:", key_res.status_code)
    print("SuperAdmin Key Create Result:", key_res.json())

if __name__ == "__main__":
    test_superadmin_create()
