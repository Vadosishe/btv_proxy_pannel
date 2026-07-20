import httpx

API_BASE = "http://5.129.229.25:8000/api"

def test_revoke():
    print("[1] Logging in as SuperAdmin...")
    res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[2] Fetching all keys...")
    keys = httpx.get(f"{API_BASE}/admin/keys", headers=headers, timeout=60.0).json()
    print("Found total keys:", len(keys))
    if not keys:
        return

    target_key = keys[0]
    print(f"\n[3] Attempting SuperAdmin deletion of Key ID {target_key['id']} ('{target_key['employee_name']}')...")
    del_res = httpx.delete(f"{API_BASE}/admin/keys/{target_key['id']}", headers=headers, timeout=60.0)
    print("SuperAdmin Revoke Status:", del_res.status_code)
    print("SuperAdmin Revoke Result:", del_res.json())

if __name__ == "__main__":
    test_revoke()
