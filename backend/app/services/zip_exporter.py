import io
import zipfile
from typing import List
from app.models import ClientKey, ProtocolType

def generate_agency_keys_zip(agency_name: str, keys: List[ClientKey]) -> bytes:
    """Generates a structured ZIP archive containing employee VPN configs."""
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for key in keys:
            # Sanitize employee name for folder path
            safe_name = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in key.employee_name).strip()
            
            if key.protocol == ProtocolType.AMNEZIA_WG:
                folder_path = f"{agency_name}/{safe_name}/AmneziaWG"
                # Write vpn:// link text
                zip_file.writestr(f"{folder_path}/vpn_link.txt", key.config_content)
                # If raw conf content is stored, write .conf file as well
                if "[Interface]" in key.config_content:
                    zip_file.writestr(f"{folder_path}/{safe_name}.conf", key.config_content)
            
            elif key.protocol == ProtocolType.VLESS:
                folder_path = f"{agency_name}/{safe_name}/VLESS"
                zip_file.writestr(f"{folder_path}/vless_link.txt", key.config_content)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
