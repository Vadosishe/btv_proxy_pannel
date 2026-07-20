import httpx
import base64
import zlib
from typing import Dict, Any

class AmneziaClient:
    """Client for amneziavpnphp API integration."""

    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.email = email
        self.password = password
        self.client = httpx.AsyncClient(timeout=10.0)
        self.token = None

    async def login(self) -> bool:
        resp = await self.client.post(
            f"{self.base_url}/api/auth/token",
            json={"email": self.email, "password": self.password}
        )
        if resp.status_code == 200:
            self.token = resp.json().get("token")
            return True
        return False

    async def create_awg_client(self, server_id: int, employee_name: str) -> Dict[str, Any]:
        """Creates an AmneziaWG v2 client on amneziavpnphp."""
        if not self.token:
            await self.login()

        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "server_id": server_id,
            "name": employee_name,
            "protocol_id": "awg2"
        }

        resp = await self.client.post(
            f"{self.base_url}/api/clients/create",
            json=payload,
            headers=headers
        )

        if resp.status_code == 200:
            data = resp.json()
            raw_conf = data.get("config", "")
            vpn_uri = data.get("vpn_link") or self._format_vpn_uri(raw_conf)
            return {
                "client_id": str(data.get("id")),
                "conf_content": raw_conf,
                "vpn_link": vpn_uri
            }
        raise Exception(f"Failed to create AmneziaWG client: {resp.text}")

    def _format_vpn_uri(self, raw_conf: str) -> str:
        """Converts raw Amnezia WireGuard config string to vpn:// URI format if not provided directly."""
        compressed = zlib.compress(raw_conf.encode('utf-8'))
        b64 = base64.urlsafe_b64encode(compressed).decode('utf-8').rstrip('=')
        return f"vpn://{b64}"
