import httpx
import base64
import zlib
import json
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


from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

def derive_pubkey(priv_b64: str) -> str:
    try:
        raw_priv = base64.b64decode(priv_b64)
        priv = X25519PrivateKey.from_private_bytes(raw_priv)
        pub = priv.public_key()
        return base64.b64encode(pub.public_bytes_raw()).decode('utf-8')
    except Exception:
        return ""

def format_amnezia_vpn_link(conf: str, default_host: str = "5.129.229.25", protocol_slug: str = "awg2") -> str:
    """Formats WireGuard conf or vpn:// into 1-to-1 exact match with official Amnezia panel QrUtil::encodeVpnUrlConf."""
    if not conf:
        return ""
    if conf.startswith("vpn://AAALP3ja"):
        return conf

    if conf.startswith("vpn://"):
        b64_in = conf.replace("vpn://", "")
        rem = len(b64_in) % 4
        if rem: b64_in += '=' * (4 - rem)
        try:
            raw_in = base64.b64decode(b64_in, altchars='-_')
            for off in [4, 6, 0]:
                try:
                    dec = zlib.decompress(raw_in[off:])
                    t = dec.decode('utf-8', errors='ignore')
                    if '[Interface]' in t:
                        conf = t
                        break
                    elif '"containers"' in t:
                        d = json.loads(t)
                        for c in d.get("containers", []):
                            if "awg" in c and "last_config" in c["awg"]:
                                lc = json.loads(c["awg"]["last_config"])
                                if "config" in lc:
                                    conf = lc["config"]
                                    break
                except Exception: pass
        except Exception: pass

    lines = [l.strip() for l in conf.splitlines() if l.strip()]
    params = {
        'H1': None, 'H2': None, 'H3': None, 'H4': None,
        'I1': None, 'I2': None, 'I3': None, 'I4': None, 'I5': None,
        'Jc': None, 'Jmin': None, 'Jmax': None,
        'S1': None, 'S2': None, 'S3': None, 'S4': None
    }
    address = None
    priv_key = None
    pub_key_server = None
    psk = None
    endpoint_host = default_host
    endpoint_port = 41679
    mtu = 1280
    keep_alive = 25
    allowed_ips = []
    dns1 = "1.1.1.1"
    dns2 = "1.0.0.1"

    for line in lines:
        if "=" in line:
            parts = [x.strip() for x in line.split("=", 1)]
            k, v = parts[0], parts[1]
            if k in params:
                params[k] = v
            elif k == "Address":
                address = v
            elif k == "PrivateKey":
                priv_key = v
            elif k == "PublicKey":
                pub_key_server = v
            elif k == "PresharedKey":
                psk = v
            elif k == "Endpoint":
                if ":" in v:
                    h, p = v.rsplit(":", 1)
                    endpoint_host = h
                    if p.isdigit(): endpoint_port = int(p)
            elif k == "MTU":
                if v.isdigit(): mtu = int(v)
            elif k == "PersistentKeepalive":
                if v.isdigit(): keep_alive = int(v)
            elif k == "AllowedIPs":
                allowed_ips = [x.strip() for x in v.split(",")]
            elif k == "DNS":
                d_parts = [x.strip() for x in v.split(",")]
                if len(d_parts) > 0: dns1 = d_parts[0]
                if len(d_parts) > 1: dns2 = d_parts[1]

    client_ip = re.sub(r'/(\d{1,2})$', '', address or '')
    client_pub_key = derive_pubkey(priv_key) if priv_key else ""

    last_config_obj = {
        "H1": str(params['H1'] or ''),
        "H2": str(params['H2'] or ''),
        "H3": str(params['H3'] or ''),
        "H4": str(params['H4'] or ''),
        "I1": str(params['I1'] or ''),
        "I2": str(params['I2'] or ''),
        "I3": str(params['I3'] or ''),
        "I4": str(params['I4'] or ''),
        "I5": str(params['I5'] or ''),
        "Jc": str(params['Jc'] or ''),
        "Jmax": str(params['Jmax'] or ''),
        "Jmin": str(params['Jmin'] or ''),
        "S1": str(params['S1'] or ''),
        "S2": str(params['S2'] or ''),
        "S3": str(params['S3'] or ''),
        "S4": str(params['S4'] or ''),
        "allowed_ips": allowed_ips if allowed_ips else ["0.0.0.0/0", "::/0"],
        "clientId": client_pub_key,
        "client_ip": client_ip,
        "client_priv_key": str(priv_key or ''),
        "client_pub_key": client_pub_key,
        "config": conf,
        "hostName": endpoint_host,
        "mtu": str(mtu),
        "persistent_keep_alive": str(keep_alive),
        "port": endpoint_port,
        "psk_key": str(psk or ''),
        "server_pub_key": str(pub_key_server or '')
    }

    last_config_json = json.dumps(last_config_obj, indent=4, ensure_ascii=False, separators=(',', ': '))

    awg_dict = {
        "H1": str(params['H1'] or ''),
        "H2": str(params['H2'] or ''),
        "H3": str(params['H3'] or ''),
        "H4": str(params['H4'] or ''),
        "Jc": str(params['Jc'] or ''),
        "Jmax": str(params['Jmax'] or ''),
        "Jmin": str(params['Jmin'] or ''),
        "S1": str(params['S1'] or ''),
        "S2": str(params['S2'] or ''),
        "last_config": last_config_json,
        "port": str(endpoint_port),
        "transport_proto": "udp"
    }

    if protocol_slug == "awg2":
        subnet = "10.8.1.0"
        if address:
            m = re.match(r'^(\d+\.\d+\.\d+)\.\d+', address)
            if m: subnet = m.group(1) + ".0"
        awg_dict.update({
            "I1": str(params['I1'] or ''),
            "I2": str(params['I2'] or ''),
            "I3": str(params['I3'] or ''),
            "I4": str(params['I4'] or ''),
            "I5": str(params['I5'] or ''),
            "S3": str(params['S3'] or ''),
            "S4": str(params['S4'] or ''),
            "protocol_version": "2",
            "subnet_address": subnet
        })

    container_name = "amnezia-awg2" if protocol_slug == "awg2" else "amnezia-awg"

    envelope = {
        "containers": [
            {
                "awg": awg_dict,
                "container": container_name
            }
        ],
        "defaultContainer": container_name,
        "description": endpoint_host,
        "dns1": dns1,
        "dns2": dns2,
        "hostName": endpoint_host
    }

    envelope_json = json.dumps(envelope, indent=4, ensure_ascii=False, separators=(',', ': '))

    header = bytes([0, 0, 11, 63])
    compressed = zlib.compress(envelope_json.encode('utf-8'), 9)
    b64 = base64.b64encode(header + compressed).decode('utf-8')
    b64_url = b64.replace('+', '-').replace('/', '_').rstrip('=')
    return f"vpn://{b64_url}"
