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
        self.client = httpx.AsyncClient(timeout=120.0)
        self.token = None

    async def login(self) -> bool:
        resp = await self.client.post(
            f"{self.base_url}/api/auth/token",
            data={"email": self.email, "password": self.password},
            timeout=120.0
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
            "name": employee_name
        }

        resp = await self.client.post(
            f"{self.base_url}/api/clients/create",
            json=payload,
            headers=headers,
            timeout=120.0
        )


        if resp.status_code == 200:
            data = resp.json()
            client_obj = data.get("client", data)
            raw_conf = client_obj.get("config", "")
            vpn_uri = client_obj.get("vpn_link") or self._format_vpn_uri(raw_conf)
            return {
                "client_id": str(client_obj.get("id")),
                "conf_content": raw_conf,
                "vpn_link": vpn_uri
            }

        raise Exception(f"Failed to create AmneziaWG client: {resp.text}")

    async def delete_awg_client(self, client_id: str) -> bool:
        """Deletes/revokes an AmneziaWG client on amneziavpnphp."""
        if not self.token:
            await self.login()

        headers = {"Authorization": f"Bearer {self.token}"}
        resp = await self.client.delete(
            f"{self.base_url}/api/clients/{client_id}/delete",
            headers=headers,
            timeout=15.0
        )
        return resp.status_code == 200

    async def list_server_clients(self, server_id: int) -> Dict[str, Any]:
        """Gets active clients list for a server from amneziavpnphp."""
        if not self.token:
            await self.login()

        headers = {"Authorization": f"Bearer {self.token}"}
        resp = await self.client.get(
            f"{self.base_url}/api/servers/{server_id}/clients",
            headers=headers,
            timeout=15.0
        )
        if resp.status_code == 200:
            return resp.json()
        return {}

    async def get_client_details(self, client_id: str) -> Dict[str, Any]:
        """Gets client details including config and vpn_link from amneziavpnphp."""
        if not self.token:
            await self.login()

        headers = {"Authorization": f"Bearer {self.token}"}
        resp = await self.client.get(
            f"{self.base_url}/api/clients/{client_id}/details",
            headers=headers,
            timeout=15.0
        )
        if resp.status_code == 200:
            return resp.json()
        return {}

    def _format_vpn_uri(self, raw_conf: str) -> str:


        """Converts raw Amnezia WireGuard config string to vpn:// URI format if not provided directly."""
        compressed = zlib.compress(raw_conf.encode('utf-8'))
        b64 = base64.urlsafe_b64encode(compressed).decode('utf-8').rstrip('=')
        return f"vpn://{b64}"
