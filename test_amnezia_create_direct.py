import httpx

AMNEZIA_URL = "http://5.129.229.25:8082"

def test_direct_create():
    print("[*] Logging into amneziavpnphp API...")
    login_resp = httpx.post(f"{AMNEZIA_URL}/api/auth/token", data={"email": "admin@amnez.ia", "password": "admin123"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[*] Testing POST /api/clients/create for Server ID 2...")
    payload = {
        "server_id": 2,
        "name": "Direct Test Employee"
    }
    client_resp = httpx.post(f"{AMNEZIA_URL}/api/clients/create", json=payload, headers=headers, timeout=30.0)
    print("Response Status:", client_resp.status_code)
    print("Response Body:", client_resp.text)

if __name__ == "__main__":
    test_direct_create()
