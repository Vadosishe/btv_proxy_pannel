import httpx

API_BASE = "http://5.129.229.25:8000/api"

def test_node5_flow():
    print("[1] Logging in as yi@bigtimeit.ai...")
    res = httpx.post(f"{API_BASE}/auth/login", data={"username": "yi@bigtimeit.ai", "password": "Wwe-72J-Fja-tA5"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[2] Attempting key creation on Node 5 (Timeweb BTV - Server ID 2)...")
    payload = {
        "employee_name": "Тестовый Сотрудник (Timeweb)",
        "protocol": "awg",
        "node_id": 5
    }
    key_res = httpx.post(f"{API_BASE}/agency/keys/create", json=payload, headers=headers, timeout=60.0)
    print("Key Create Status:", key_res.status_code)
    print("Key Create Result:", key_res.json())

if __name__ == "__main__":
    test_node5_flow()
