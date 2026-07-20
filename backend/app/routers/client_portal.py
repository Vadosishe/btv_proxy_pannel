import io
import base64
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClientKey, ProtocolType

router = APIRouter(tags=["ClientPortal"])

def generate_qr_data_url(text: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

def get_device_label(name: str) -> str:
    """Extract device label from employee name like 'Иванов (phone)' -> '📱 Телефон'"""
    lower = name.lower()
    if lower.endswith("(phone)"):
        return "📱 Телефон"
    elif lower.endswith("(pc)"):
        return "💻 Компьютер"
    return ""

def get_base_name(name: str) -> str:
    """Extract base name: 'Иванов Иван (phone)' -> 'Иванов Иван'"""
    for suffix in [" (phone)", " (pc)", " (Phone)", " (PC)"]:
        if name.endswith(suffix):
            return name[:-len(suffix)].strip()
    return name.strip()

@router.get("/c/{secret_uuid}", response_class=HTMLResponse)
def view_employee_portal(secret_uuid: str, db: Session = Depends(get_db)):
    key = db.query(ClientKey).filter(ClientKey.secret_uuid == secret_uuid).first()
    if not key:
        raise HTTPException(status_code=404, detail="Corporate VPN Access Link not found or revoked.")

    # Find paired keys (phone + pc) for the same employee & agency
    base_name = get_base_name(key.employee_name)
    paired_keys = db.query(ClientKey).filter(
        ClientKey.agency_id == key.agency_id,
        ClientKey.protocol == key.protocol
    ).all()
    
    # Filter to same base name
    siblings = [k for k in paired_keys if get_base_name(k.employee_name) == base_name]
    
    # If only this key found, show single key
    if len(siblings) <= 1:
        siblings = [key]

    # Sort: phone first, then pc, then others
    def sort_key(k):
        ln = k.employee_name.lower()
        if ln.endswith("(phone)"): return 0
        if ln.endswith("(pc)"): return 1
        return 2
    siblings.sort(key=sort_key)

    protocol_title = "AmneziaWG v2" if key.protocol == ProtocolType.AMNEZIA_WG else "VLESS / Reality"
    agency_name = key.agency.name if key.agency else "Компания"
    display_name = base_name if base_name else key.employee_name
    
    # Build key cards HTML
    key_cards_html = ""
    for i, k in enumerate(siblings):
        device_label = get_device_label(k.employee_name)
        if not device_label:
            device_label = f"🔑 Ключ {i+1}" if len(siblings) > 1 else "🔑 Ваш ключ"
        
        qr_url = generate_qr_data_url(k.config_content)
        
        key_cards_html += f"""
        <div class="key-card">
            <div class="device-label">{device_label}</div>
            <div class="qr-container">
                <img src="{qr_url}" alt="VPN QR Code">
            </div>
            <a href="{k.config_content}" class="btn">Подключить в 1 клик</a>
            <div class="config-box">{k.config_content}</div>
        </div>
        """
    
    app_store_links = """
    <div class="apps-grid">
        <a href="https://apps.apple.com/app/amneziavpn/id1600299950" target="_blank" class="app-btn">iOS / macOS (AmneziaWG)</a>
        <a href="https://play.google.com/store/apps/details?id=org.amnezia.vpn" target="_blank" class="app-btn">Android (AmneziaWG)</a>
        <a href="https://github.com/amnezia-vpn/amnezia-client/releases" target="_blank" class="app-btn">Windows Client</a>
    </div>
    """ if key.protocol == ProtocolType.AMNEZIA_WG else """
    <div class="apps-grid">
        <a href="https://apps.apple.com/app/v2box-v2ray-client/id1641870473" target="_blank" class="app-btn">iOS (V2Box / Happ)</a>
        <a href="https://play.google.com/store/apps/details?id=com.v2ray.ang" target="_blank" class="app-btn">Android (v2rayNG)</a>
        <a href="https://github.com/2dust/v2rayN/releases" target="_blank" class="app-btn">Windows (v2rayN)</a>
    </div>
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Корпоративный VPN | {display_name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #0c1222;
                --card-bg: #141e30;
                --card-bg-alt: #182538;
                --primary: #e8792b;
                --primary-hover: #d4691f;
                --primary-glow: rgba(232, 121, 43, 0.18);
                --text: #f0f2f5;
                --text-muted: #94a3b8;
                --border: #243352;
            }}
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                min-height: 100vh;
            }}
            .container {{
                max-width: 520px;
                width: 100%;
                margin-top: 40px;
            }}
            .header-card {{
                background-color: var(--card-bg);
                border-radius: 16px;
                padding: 32px;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
                text-align: center;
                border: 1px solid var(--border);
                margin-bottom: 16px;
            }}
            .logo {{
                display: inline-flex; align-items: center; gap: 8px;
                font-size: 16px; font-weight: 700; color: var(--text);
                margin-bottom: 16px;
            }}
            .logo-hex {{
                width: 28px; height: 28px; border-radius: 6px;
                background: linear-gradient(135deg, #e8792b 0%, #f5a623 100%);
                display: flex; align-items: center; justify-content: center;
                font-size: 13px; color: #fff;
            }}
            .logo b {{ color: var(--primary); }}
            h1 {{ font-size: 22px; margin-bottom: 6px; font-weight: 700; letter-spacing: -0.3px; }}
            .subtitle {{ color: var(--text-muted); font-size: 14px; margin-bottom: 20px; }}
            .badge {{
                display: inline-block;
                background: var(--primary-glow);
                color: var(--primary);
                padding: 5px 12px;
                border-radius: 9999px;
                font-size: 12px;
                font-weight: 600;
                margin-bottom: 16px;
                border: 1px solid rgba(232, 121, 43, 0.2);
            }}
            .keys-grid {{
                display: grid;
                grid-template-columns: {'1fr 1fr' if len(siblings) == 2 else '1fr'};
                gap: 16px;
                margin-bottom: 16px;
            }}
            @media(max-width:600px) {{
                .keys-grid {{ grid-template-columns: 1fr; }}
            }}
            .key-card {{
                background-color: var(--card-bg);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.4);
                text-align: center;
                border: 1px solid var(--border);
            }}
            .device-label {{
                font-size: 15px;
                font-weight: 700;
                margin-bottom: 14px;
                letter-spacing: -0.2px;
            }}
            .qr-container {{
                background: white;
                padding: 12px;
                border-radius: 10px;
                display: inline-block;
                margin-bottom: 16px;
            }}
            .qr-container img {{ display: block; max-width: 180px; height: auto; }}
            .btn {{
                display: block;
                width: 100%;
                padding: 12px 0;
                background-color: var(--primary);
                color: #fff;
                font-weight: 700;
                font-size: 13px;
                border-radius: 8px;
                text-decoration: none;
                transition: 0.15s;
                margin-bottom: 10px;
                box-shadow: 0 2px 8px var(--primary-glow);
            }}
            .btn:hover {{ background-color: var(--primary-hover); }}
            .apps-card {{
                background-color: var(--card-bg);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.4);
                text-align: center;
                border: 1px solid var(--border);
            }}
            .apps-title {{ font-size: 14px; font-weight: 600; margin-bottom: 12px; }}
            .apps-grid {{ display: flex; flex-direction: column; gap: 8px; }}
            .app-btn {{
                background: rgba(255, 255, 255, 0.04);
                color: var(--text);
                padding: 10px;
                border-radius: 8px;
                font-size: 13px;
                text-decoration: none;
                border: 1px solid var(--border);
                transition: 0.15s;
            }}
            .app-btn:hover {{ background: rgba(255, 255, 255, 0.08); border-color: var(--primary); }}
            .config-box {{
                background: rgba(0,0,0,0.3);
                padding: 10px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 10px;
                word-break: break-all;
                color: #a5f3fc;
                user-select: all;
                max-height: 60px;
                overflow-y: auto;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-card">
                <div class="logo">
                    <div class="logo-hex">⬡</div>
                    Scale<b>BoX</b>™
                </div>
                <br>
                <span class="badge">Протокол: {protocol_title}</span>
                <h1>Привет, {display_name}!</h1>
                <p class="subtitle">Ваш персональный доступ к корпоративной сети компании <strong>{agency_name}</strong></p>
            </div>

            <div class="keys-grid">
                {key_cards_html}
            </div>

            <div class="apps-card">
                <div class="apps-title">Скачать приложение для вашего устройства:</div>
                {app_store_links}
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
