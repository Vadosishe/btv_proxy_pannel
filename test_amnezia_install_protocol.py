import httpx

AMNEZIA_URL = "http://5.129.229.25:8082"

def test_install():
    print("[*] Logging into amneziavpnphp API...")
    login_resp = httpx.post(f"{AMNEZIA_URL}/api/auth/token", data={"email": "admin@amnez.ia", "password": "admin123"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[*] Triggering AmneziaWG 2.0 (protocol_id 11) installation on Server ID 3 (RackNerd Chicago)...")
    res = httpx.post(f"{AMNEZIA_URL}/api/servers/3/protocols/install", json={"protocol_id": 11}, headers=headers, timeout=120.0)
    print("Install Status:", res.status_code)
    print("Install Response:", res.text)

if __name__ == "__main__":
    test_install()
