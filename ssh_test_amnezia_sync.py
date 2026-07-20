import httpx

AMNEZIA_URL = "http://5.129.229.25:8082"

def test_amnezia_api():
    print("[*] Logging into amneziavpnphp API...")
    login_resp = httpx.post(f"{AMNEZIA_URL}/api/auth/token", data={"email": "admin@amnez.ia", "password": "admin123"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n[*] Fetching clients for Server ID 2...")
    clients_resp = httpx.get(f"{AMNEZIA_URL}/api/servers/2/clients", headers=headers)
    print("Server 2 Clients Status:", clients_resp.status_code)
    print("Server 2 Clients:", clients_resp.json())

    print("\n[*] Fetching all servers...")
    servers_resp = httpx.get(f"{AMNEZIA_URL}/api/servers", headers=headers)
    print("Servers:", servers_resp.json())

if __name__ == "__main__":
    test_amnezia_api()
