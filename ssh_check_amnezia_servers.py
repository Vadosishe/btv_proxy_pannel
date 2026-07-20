import httpx

AMNEZIA_URL = "http://5.129.229.25:8082"

def check_servers():
    print("[*] Logging into amneziavpnphp API...")
    resp = httpx.post(f"{AMNEZIA_URL}/api/auth/token", data={"email": "admin@amnez.ia", "password": "admin123"})
    if resp.status_code != 200:
        print(f"[!] Login failed: {resp.text}")
        return

    token = resp.json().get("token")
    print(f"[+] Token received: {token[:15]}...")

    headers = {"Authorization": f"Bearer {token}"}
    servers_resp = httpx.get(f"{AMNEZIA_URL}/api/servers", headers=headers)
    print("\n=== Registered Servers in amneziavpnphp ===")
    print(servers_resp.json())

if __name__ == "__main__":
    check_servers()
