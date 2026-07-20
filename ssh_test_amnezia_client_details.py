import httpx

AMNEZIA_URL = "http://5.129.229.25:8082"

def test_details():
    print("[*] Logging into amneziavpnphp API...")
    login_resp = httpx.post(f"{AMNEZIA_URL}/api/auth/token", data={"email": "admin@amnez.ia", "password": "admin123"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[*] Fetching client details for Client ID 1...")
    res = httpx.get(f"{AMNEZIA_URL}/api/clients/1/details", headers=headers)
    print("Client 1 Details Status:", res.status_code)
    print("Client 1 Details Body:", res.json())

if __name__ == "__main__":
    test_details()
