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
        """Converts raw Amnezia WireGuard config string to native Amnezia vpn://AAAL... URI format."""
        if not raw_conf:
            return ""
        return format_amnezia_vpn_link(raw_conf)


def wg_conf_to_amnezia_container_json(wg_conf: str, default_ip: str = "5.129.229.25") -> str:
    """Converts a WireGuard .conf string to official Amnezia Container JSON URI (vpn://AAALP3ja...)."""
    lines = [l.strip() for l in wg_conf.splitlines() if l.strip() and not l.strip().startswith("#")]
    params = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = v.strip()

    address = params.get("Address", "").split("/")[0]
    dns_servers = [d.strip() for d in params.get("DNS", "1.1.1.1, 1.0.0.1").split(",")]
    dns1 = dns_servers[0] if len(dns_servers) > 0 else "1.1.1.1"
    dns2 = dns_servers[1] if len(dns_servers) > 1 else "1.0.0.1"

    endpoint = params.get("Endpoint", f"{default_ip}:41679")
    ep_parts = endpoint.rsplit(":", 1)
    host = ep_parts[0] if ep_parts[0] else default_ip
    port = int(ep_parts[1]) if len(ep_parts) > 1 else 41679

    last_config_dict = {
        "H1": params.get("H1", ""),
        "H2": params.get("H2", ""),
        "H3": params.get("H3", ""),
        "H4": params.get("H4", ""),
        "I1": params.get("I1", ""),
        "I2": params.get("I2", ""),
        "I3": params.get("I3", ""),
        "I4": params.get("I4", ""),
        "I5": params.get("I5", ""),
        "Jc": params.get("Jc", "6"),
        "Jmax": params.get("Jmax", "50"),
        "Jmin": params.get("Jmin", "10"),
        "S1": params.get("S1", "145"),
        "S2": params.get("S2", "123"),
        "S3": params.get("S3", "27"),
        "S4": params.get("S4", "16"),
        "allowed_ips": [a.strip() for a in params.get("AllowedIPs", "0.0.0.0/0, ::/0").split(",")],
        "clientId": params.get("PublicKey", ""),
        "client_ip": address,
        "client_priv_key": params.get("PrivateKey", ""),
        "client_pub_key": params.get("PublicKey", ""),
        "config": wg_conf,
        "hostName": host,
        "mtu": params.get("MTU", "1280"),
        "persistent_keep_alive": params.get("PersistentKeepalive", "25"),
        "port": port,
        "psk_key": params.get("PresharedKey", ""),
        "server_pub_key": params.get("PublicKey", "")
    }

    container_json = {
        "containers": [
            {
                "awg": {
                    "H1": params.get("H1", ""),
                    "H2": params.get("H2", ""),
                    "H3": params.get("H3", ""),
                    "H4": params.get("H4", ""),
                    "Jc": params.get("Jc", "6"),
                    "Jmax": params.get("Jmax", "50"),
                    "Jmin": params.get("Jmin", "10"),
                    "S1": params.get("S1", "145"),
                    "S2": params.get("S2", "123"),
                    "last_config": json.dumps(last_config_dict, indent=4, ensure_ascii=False),
                    "port": str(port),
                    "transport_proto": "udp",
                    "I1": params.get("I1", ""),
                    "I2": params.get("I2", ""),
                    "I3": params.get("I3", ""),
                    "I4": params.get("I4", ""),
                    "I5": params.get("I5", ""),
                    "S3": params.get("S3", "27"),
                    "S4": params.get("S4", "16"),
                    "protocol_version": "2",
                    "subnet_address": "10.8.1.0"
                },
                "container": "amnezia-awg2"
            }
        ],
        "defaultContainer": "amnezia-awg2",
        "description": host,
        "dns1": dns1,
        "dns2": dns2,
        "hostName": host
    }

    json_bytes = json.dumps(container_json, ensure_ascii=False).encode('utf-8')
    compressed = zlib.compress(json_bytes, level=9)
    header = bytes([0, 0, 11, 63])
    b64 = base64.urlsafe_b64encode(header + compressed).decode('utf-8').rstrip('=')
    return f"vpn://{b64}"


def format_amnezia_vpn_link(vpn_link_or_conf: str) -> str:
    """Ensures Amnezia link is formatted in full native Amnezia Container JSON format (vpn://AAALP3ja...)."""
    if not vpn_link_or_conf:
        return ""
    if vpn_link_or_conf.startswith("vpn://AAALP3ja"):
        return vpn_link_or_conf

    raw_conf_text = ""
    if vpn_link_or_conf.startswith("vpn://"):
        b64 = vpn_link_or_conf.replace("vpn://", "")
        missing_padding = len(b64) % 4
        if missing_padding:
            b64 += '=' * (4 - missing_padding)
        try:
            raw = base64.b64decode(b64, altchars='-_')
            # Check if it's already container JSON
            for off in [4, 6, 0]:
                try:
                    dec = zlib.decompress(raw[off:])
                    text = dec.decode('utf-8', errors='ignore')
                    if '"containers"' in text:
                        return vpn_link_or_conf
                    if "[Interface]" in text:
                        raw_conf_text = text
                        break
                except Exception:
                    pass
        except Exception:
            pass
    elif "[Interface]" in vpn_link_or_conf:
        raw_conf_text = vpn_link_or_conf

    if raw_conf_text:
        return wg_conf_to_amnezia_container_json(raw_conf_text)

    return vpn_link_or_conf
