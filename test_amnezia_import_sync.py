import httpx

API_BASE = "http://5.129.229.25:8000/api"
AMNEZIA_URL = "http://5.129.229.25:8082"

def test_import():
    print("[1] Creating a key directly in amneziavpnphp panel...")
    amnez_token = httpx.post(f"{AMNEZIA_URL}/api/auth/token", data={"email": "admin@amnez.ia", "password": "admin123"}).json()["token"]
    amnez_headers = {"Authorization": f"Bearer {amnez_token}"}
    
    create_payload = {"server_id": 2, "name": "Direct Panel User"}
    direct_res = httpx.post(f"{AMNEZIA_URL}/api/clients/create", json=create_payload, headers=amnez_headers, timeout=60.0)
    assert direct_res.status_code == 200, f"Direct create failed: {direct_res.text}"
    created_id = str(direct_res.json()["client"]["id"])
    print(f"[+] Created client in amneziavpnphp with ID: {created_id}")

    print("\n[2] Logging in as SuperAdmin in B2B Orchestrator...")
    res = httpx.post(f"{API_BASE}/auth/login", data={"username": "admin@b2b.com", "password": "admin123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[3] Calling GET /api/admin/keys in B2B Orchestrator to trigger Two-Way Live Sync...")
    keys_res = httpx.get(f"{API_BASE}/admin/keys", headers=headers, timeout=60.0)
    all_keys = keys_res.json()
    imported_key = next((k for k in all_keys if k.get("remote_client_id") == created_id), None)

    if imported_key:
        print(f"[SUCCESS] Two-Way Sync Working! Client {created_id} ('{imported_key['employee_name']}') was automatically imported into B2B Orchestrator!")
        print("Config / link:", imported_key.get("config_content")[:50] + "...")
    else:
        print("[!] Key created in panel was NOT imported into B2B DB!")

if __name__ == "__main__":
    test_import()
