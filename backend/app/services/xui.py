import httpx
import uuid
import json
import re
from typing import Dict, Any, Optional

def transliterate_ru_to_en(text: str) -> str:
    """Transliterates Cyrillic names to safe ASCII for email and remarks."""
    ru_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ы': 'y', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh',
        'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
        'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts',
        'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ы': 'Y', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    result = []
    for char in text:
        result.append(ru_map.get(char, char))
    res_str = "".join(result)
    res_str = re.sub(r'[^a-zA-Z0-9_-]', '_', res_str)
    return res_str.strip('_')

class XUIClient:
    """Enhanced Client for 3X-UI v3 API integration with Bearer/Session auth and smart flow validation."""

    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None, api_token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.api_token = api_token
        self.session = httpx.AsyncClient(timeout=10.0, verify=False)
        self.cookies = {}

    async def login(self) -> bool:
        if self.api_token:
            return True # Bearer token bypasses login
        
        login_url = f"{self.base_url}/login"
        resp = await self.session.post(
            login_url,
            data={"username": self.username, "password": self.password}
        )
        if resp.status_code == 200 and resp.json().get("success"):
            self.cookies = resp.cookies
            return True
        return False

    def _get_headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def add_vless_client(self, inbound_id: int, employee_name: str, group_name: Optional[str] = None) -> Dict[str, Any]:
        """Creates a VLESS client on the specified 3X-UI inbound using 3-step bulletproof flow."""
        await self.login()
        headers = self._get_headers()
        
        client_uuid = str(uuid.uuid4())
        clean_name = transliterate_ru_to_en(employee_name)
        email = f"{clean_name}_{client_uuid[:6]}"
        sub_id = client_uuid.replace('-', '')[:16]

        # 1. Fetch inbound details
        inbound_resp = await self.session.get(
            f"{self.base_url}/panel/api/inbounds/get/{inbound_id}",
            cookies=self.cookies,
            headers=headers
        )
        inbound_data = inbound_resp.json().get("obj", {})
        port = inbound_data.get("port")
        protocol = inbound_data.get("protocol", "vless").lower()
        
        stream_settings = json.loads(inbound_data.get("streamSettings", "{}")) if isinstance(inbound_data.get("streamSettings"), str) else inbound_data.get("streamSettings", {})
        security = stream_settings.get("security", "none")
        network = stream_settings.get("network", "tcp")
        
        reality_settings = stream_settings.get("realitySettings", {})
        settings = reality_settings.get("settings", {})
        
        public_key = settings.get("publicKey", "")
        short_id = reality_settings.get("shortIds", [""])[0] if reality_settings.get("shortIds") else ""
        server_names = reality_settings.get("serverNames", ["example.com"])
        sni = server_names[0] if server_names else "example.com"

        # Validate flow (xtls-rprx-vision only supported for VLESS + Reality/TLS over TCP)
        flow = "xtls-rprx-vision" if protocol == "vless" and security in ["reality", "tls"] and network == "tcp" else ""

        # 2. Add client payload (3X-UI v3 API format)
        client_payload = {
            "id": client_uuid,
            "email": email,
            "subId": sub_id,
            "flow": flow,
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True,
            "group": group_name or "B2B Clients",
            "comment": f"B2B: {employee_name}"
        }

        payload = {
            "client": client_payload,
            "inboundIds": [inbound_id]
        }

        # Try v3 global client add API first, fall back to inbound addClient
        add_resp = await self.session.post(
            f"{self.base_url}/panel/api/clients/add",
            json=payload,
            cookies=self.cookies,
            headers=headers
        )
        if not add_resp.json().get("success"):
            # Fallback to inbounds/addClient
            legacy_payload = {
                "id": inbound_id,
                "settings": json.dumps({"clients": [client_payload]})
            }
            await self.session.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                json=legacy_payload,
                cookies=self.cookies,
                headers=headers
            )

        # Build vless:// link
        host_ip = self.base_url.split("//")[-1].split(":")[0]
        vless_link = (
            f"vless://{client_uuid}@{host_ip}:{port}?"
            f"type={network}&security={security}&pbk={public_key}&fp=chrome&sni={sni}&sid={short_id}"
        )
        if flow:
            vless_link += f"&flow={flow}"
        vless_link += f"#{employee_name}"

        return {
            "client_id": client_uuid,
            "email": email,
            "vless_link": vless_link
        }

    async def delete_client(self, inbound_id: int, client_id: str, email: Optional[str] = None) -> bool:
        """3-step bulletproof deletion algorithm (delClientByEmail -> delClient -> del global)."""
        await self.login()
        headers = self._get_headers()

        # Step 1: Delete by Email in inbound (3X-UI 3.3.0+)
        if email:
            try:
                resp = await self.session.post(
                    f"{self.base_url}/panel/api/inbounds/{inbound_id}/delClientByEmail/{email}",
                    cookies=self.cookies,
                    headers=headers
                )
                if resp.status_code == 200 and resp.json().get("success"):
                    return True
            except Exception:
                pass

        # Step 2: Delete by Client UUID in inbound
        try:
            resp = await self.session.post(
                f"{self.base_url}/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
                cookies=self.cookies,
                headers=headers
            )
            if resp.status_code == 200 and resp.json().get("success"):
                return True
        except Exception:
            pass

        # Step 3: Global delete fallback
        if email:
            try:
                resp = await self.session.post(
                    f"{self.base_url}/panel/api/clients/del/{email}",
                    cookies=self.cookies,
                    headers=headers
                )
                if resp.status_code == 200 and resp.json().get("success"):
                    return True
            except Exception:
                pass

        return False
