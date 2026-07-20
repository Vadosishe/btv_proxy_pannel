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

@router.get("/c/{secret_uuid}", response_class=HTMLResponse)
def view_employee_portal(secret_uuid: str, db: Session = Depends(get_db)):
    key = db.query(ClientKey).filter(ClientKey.secret_uuid == secret_uuid).first()
    if not key:
        raise HTTPException(status_code=404, detail="Corporate VPN Access Link not found or revoked.")

    qr_url = generate_qr_data_url(key.config_content)
    protocol_title = "AmneziaWG v2" if key.protocol == ProtocolType.AMNEZIA_WG else "VLESS / Reality"
    
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
        <title>Корпоративный VPN | {key.employee_name}</title>
        <style>
            :root {{
                --bg: #0f172a;
                --card-bg: #1e293b;
                --primary: #38bdf8;
                --primary-hover: #0284c7;
                --text: #f8fafc;
                --text-muted: #94a3b8;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }}
            .card {{
                background-color: var(--card-bg);
                border-radius: 16px;
                padding: 32px;
                max-width: 480px;
                width: 100%;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
                text-align: center;
            }}
            h1 {{ font-size: 24px; margin-bottom: 8px; font-weight: 700; }}
            p {{ color: var(--text-muted); font-size: 14px; margin-bottom: 24px; }}
            .badge {{
                display: inline-block;
                background: rgba(56, 189, 248, 0.1);
                color: var(--primary);
                padding: 6px 12px;
                border-radius: 9999px;
                font-size: 13px;
                font-weight: 600;
                margin-bottom: 20px;
            }}
            .qr-container {{
                background: white;
                padding: 16px;
                border-radius: 12px;
                display: inline-block;
                margin-bottom: 24px;
            }}
            .qr-container img {{ display: block; max-width: 220px; height: auto; }}
            .btn {{
                display: block;
                width: 100%;
                padding: 14px 0;
                background-color: var(--primary);
                color: #0f172a;
                font-weight: 700;
                border-radius: 10px;
                text-decoration: none;
                transition: background-color 0.2s;
                margin-bottom: 12px;
            }}
            .btn:hover {{ background-color: var(--primary-hover); }}
            .apps-grid {{ display: flex; flex-direction: column; gap: 8px; margin-top: 16px; }}
            .app-btn {{
                background: rgba(255, 255, 255, 0.05);
                color: var(--text);
                padding: 10px;
                border-radius: 8px;
                font-size: 13px;
                text-decoration: none;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            .app-btn:hover {{ background: rgba(255, 255, 255, 0.1); }}
            .config-box {{
                background: rgba(0,0,0,0.3);
                padding: 12px;
                border-radius: 8px;
                font-family: monospace;
                font-size: 11px;
                word-break: break-all;
                color: #a5f3fc;
                margin-bottom: 16px;
                user-select: all;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">Протокол: {protocol_title}</span>
            <h1>Привет, {key.employee_name}!</h1>
            <p>Ваш персональный доступ к корпоративной сети компании <strong>{key.agency.name}</strong></p>
            
            <div class="qr-container">
                <img src="{qr_url}" alt="VPN QR Code">
            </div>

            <a href="{key.config_content}" class="btn">Подключить в 1 клик</a>

            <div class="config-box">{key.config_content}</div>

            <p style="margin-top: 24px; font-weight: 600;">Скачать приложение для вашего устройства:</p>
            {app_store_links}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
