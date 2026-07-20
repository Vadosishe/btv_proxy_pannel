import httpx

API_BASE = "http://5.129.229.25:8000/api"
AMNEZIA_URL = "http://5.129.229.25:8082"

def test_sync():
    print("[1] Logging in as yi@bigtimeit.ai...")
    res = httpx.post(f"{API_BASE}/auth/login", data={"username": "yi@bigtimeit.ai", "password": "Wwe-72J-Fja-tA5"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("[2] Creating key for Sync Test...")
    payload = {"employee_name": "Sync Test Client", "protocol": "awg", "node_id": 5}
    create_res = httpx.post(f"{API_BASE}/agency/keys/create", json=payload, headers=headers, timeout=60.0)
    assert create_res.status_code == 200, f"Key creation failed: {create_res.text}"
    key_data = create_res.json()
    remote_client_id = key_data["remote_client_id"]
    key_id = key_data["id"]
    print(f"[+] Key created in B2B DB (ID: {key_id}, Remote ID: {remote_client_id})")

    print(f"\n[3] Deleting Remote Client {remote_client_id} directly in amneziavpnphp API...")
    amnez_token = httpx.post(f"{AMNEZIA_URL}/api/auth/token", data={"email": "admin@amnez.ia", "password": "admin123"}).json()["token"]
    amnez_headers = {"Authorization": f"Bearer {amnez_token}"}
    del_res = httpx.delete(f"{AMNEZIA_URL}/api/clients/{remote_client_id}/delete", headers=amnez_headers, timeout=30.0)
    print("Direct amneziavpnphp deletion status:", del_res.status_code)

    print("\n[4] Calling GET /api/agency/keys in B2B Orchestrator to trigger Live Deletion Sync...")
    keys_res = httpx.get(f"{API_BASE}/agency/keys", headers=headers)
    active_keys = keys_res.json()
    active_ids = [k["id"] for k in active_keys]
    print("Active Key IDs in B2B Orchestrator:", active_ids)

    if key_id not in active_ids:
        print("[SUCCESS] Live Sync working! Key was automatically removed from B2B Orchestrator database!")
    else:
        print("[!] Key still present in B2B Orchestrator DB!")

if __name__ == "__main__":
    test_sync()
