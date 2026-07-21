import io
import base64
import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClientKey, Employee, ProtocolType

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
    # Try Employee first (new system)
    employee = db.query(Employee).filter(Employee.secret_uuid == secret_uuid).first()
    if employee:
        return _render_employee_page(employee)

    # Fallback: legacy ClientKey lookup
    key = db.query(ClientKey).filter(ClientKey.secret_uuid == secret_uuid).first()
    if not key:
        raise HTTPException(status_code=404, detail="VPN Access Link not found or revoked.")

    # Legacy: find paired keys by base name
    base_name = _get_base_name(key.employee_name)
    siblings = db.query(ClientKey).filter(
        ClientKey.agency_id == key.agency_id,
        ClientKey.protocol == key.protocol
    ).all()
    siblings = [k for k in siblings if _get_base_name(k.employee_name) == base_name]
    if len(siblings) <= 1:
        siblings = [key]
    siblings.sort(key=lambda k: (0 if k.employee_name.lower().endswith("(phone)") else 1 if k.employee_name.lower().endswith("(pc)") else 2))

    return _render_legacy_page(key, siblings, base_name)


def _render_employee_page(employee: Employee) -> HTMLResponse:
    """Render page for new Employee model — all keys grouped by node."""
    agency_name = employee.agency.name if employee.agency else "Компания"

    # Group keys by node
    nodes_map = {}  # node_id -> {node_name, location, keys: []}
    for k in employee.keys:
        nid = k.node_id
        if nid not in nodes_map:
            nodes_map[nid] = {
                "name": k.node.name if k.node else "Сервер",
                "location": k.node.location if k.node else "",
                "node_type": k.node.node_type if k.node else "amnezia",
                "keys": []
            }
        label = "📱 Телефон" if k.employee_name.lower().endswith("(phone)") else \
                "💻 Компьютер" if k.employee_name.lower().endswith("(pc)") else \
                "🔑 Ключ"
        nodes_map[nid]["keys"].append({
            "label": label,
            "config": k.config_content,
            "protocol": k.protocol.value,
            "qr": generate_qr_data_url(k.config_content)
        })

    # Sort keys within each node: phone first, pc second
    for ndata in nodes_map.values():
        ndata["keys"].sort(key=lambda x: 0 if "Телефон" in x["label"] else 1 if "Компьютер" in x["label"] else 2)

    # Build accordion sections
    accordion_html = ""
    for idx, (nid, ndata) in enumerate(nodes_map.items()):
        icon = "🔒" if ndata["node_type"] == "amnezia" else "⚡"
        keys_html = ""
        for ki in ndata["keys"]:
            keys_html += f"""
            <div class="key-item">
                <div class="key-label">{ki["label"]}</div>
                <div class="qr-container"><img src="{ki["qr"]}" alt="QR"></div>
                <a href="{ki["config"]}" class="btn">Подключить в 1 клик</a>
                <div class="config-box">{ki["config"]}</div>
            </div>
            """

        open_attr = "open" if idx == 0 else ""
        accordion_html += f"""
        <details class="node-section" {open_attr}>
            <summary class="node-header">
                <span>{icon} {ndata["name"]}</span>
                <span class="node-loc">{ndata["location"]}</span>
            </summary>
            <div class="node-keys">{keys_html}</div>
        </details>
        """

    app_links = _get_app_links(employee.keys)

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VPN | {employee.name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
        {_get_styles()}
    </head>
    <body>
        <div class="container">
            <div class="header-card">
                <div class="logo"><div class="logo-hex">⬡</div>Scale<b>BoX</b>™</div><br>
                <h1>Привет, {employee.name}!</h1>
                <p class="subtitle">Корпоративный VPN · <strong>{agency_name}</strong></p>
                <div class="keys-badge">{len(employee.keys)} ключей на {len(nodes_map)} серверах</div>
            </div>
            {accordion_html}
            <div class="apps-card">
                <div class="apps-title">Скачать приложение:</div>
                {app_links}
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


def _render_legacy_page(key, siblings, base_name) -> HTMLResponse:
    """Render page for legacy keys without Employee."""
    agency_name = key.agency.name if key.agency else "Компания"
    protocol_title = "AmneziaWG v2" if key.protocol == ProtocolType.AMNEZIA_WG else "VLESS / Reality"

    key_cards_html = ""
    for i, k in enumerate(siblings):
        label = "📱 Телефон" if k.employee_name.lower().endswith("(phone)") else \
                "💻 Компьютер" if k.employee_name.lower().endswith("(pc)") else \
                f"🔑 Ключ {i+1}" if len(siblings) > 1 else "🔑 Ваш ключ"
        qr_url = generate_qr_data_url(k.config_content)
        key_cards_html += f"""
        <div class="key-item">
            <div class="key-label">{label}</div>
            <div class="qr-container"><img src="{qr_url}" alt="QR"></div>
            <a href="{k.config_content}" class="btn">Подключить в 1 клик</a>
            <div class="config-box">{k.config_content}</div>
        </div>
        """

    app_links = _get_app_links(siblings)

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VPN | {base_name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
        {_get_styles()}
    </head>
    <body>
        <div class="container">
            <div class="header-card">
                <div class="logo"><div class="logo-hex">⬡</div>Scale<b>BoX</b>™</div><br>
                <span class="keys-badge">{protocol_title}</span>
                <h1>Привет, {base_name}!</h1>
                <p class="subtitle">Корпоративный VPN · <strong>{agency_name}</strong></p>
            </div>
            <div class="legacy-grid">{key_cards_html}</div>
            <div class="apps-card">
                <div class="apps-title">Скачать приложение:</div>
                {app_links}
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


def _get_base_name(name: str) -> str:
    for suffix in [" (phone)", " (pc)", " (Phone)", " (PC)"]:
        if name.endswith(suffix):
            return name[:-len(suffix)].strip()
    return name.strip()


def _get_app_links(keys) -> str:
    has_awg = any(getattr(k, 'protocol', None) == ProtocolType.AMNEZIA_WG or (isinstance(k, dict) and k.get('protocol') == 'awg') for k in keys)
    has_vless = any(getattr(k, 'protocol', None) == ProtocolType.VLESS or (isinstance(k, dict) and k.get('protocol') == 'vless') for k in keys)

    links = '<div class="apps-grid">'
    if has_awg:
        links += """
        <a href="https://apps.apple.com/app/amneziavpn/id1600299950" target="_blank" class="app-btn">🍎 iOS / macOS — AmneziaVPN</a>
        <a href="https://play.google.com/store/apps/details?id=org.amnezia.vpn" target="_blank" class="app-btn">🤖 Android — AmneziaVPN</a>
        <a href="https://github.com/amnezia-vpn/amnezia-client/releases" target="_blank" class="app-btn">🖥️ Windows — AmneziaVPN</a>
        """
    if has_vless:
        links += """
        <a href="https://apps.apple.com/app/v2box-v2ray-client/id1641870473" target="_blank" class="app-btn">🍎 iOS — V2Box / Happ</a>
        <a href="https://play.google.com/store/apps/details?id=com.v2ray.ang" target="_blank" class="app-btn">🤖 Android — v2rayNG</a>
        <a href="https://github.com/2dust/v2rayN/releases" target="_blank" class="app-btn">🖥️ Windows — v2rayN</a>
        """
    links += '</div>'
    return links


def _get_styles() -> str:
    return """
    <style>
        :root {
            --bg: #0c1222; --card-bg: #141e30; --card-bg-alt: #182538;
            --primary: #e8792b; --primary-hover: #d4691f;
            --primary-glow: rgba(232, 121, 43, 0.18);
            --text: #f0f2f5; --text-muted: #94a3b8; --border: #243352;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg); color: var(--text);
            padding: 20px; display: flex; justify-content: center;
            min-height: 100vh;
        }
        .container { max-width: 560px; width: 100%; margin-top: 30px; }
        .header-card {
            background: var(--card-bg); border-radius: 16px; padding: 28px;
            text-align: center; border: 1px solid var(--border);
            margin-bottom: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
        }
        .logo {
            display: inline-flex; align-items: center; gap: 8px;
            font-size: 16px; font-weight: 700; margin-bottom: 14px;
        }
        .logo-hex {
            width: 28px; height: 28px; border-radius: 6px;
            background: linear-gradient(135deg, #e8792b, #f5a623);
            display: flex; align-items: center; justify-content: center;
            font-size: 13px; color: #fff;
        }
        .logo b { color: var(--primary); }
        h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.3px; margin-bottom: 4px; }
        .subtitle { color: var(--text-muted); font-size: 13px; margin-bottom: 12px; }
        .keys-badge {
            display: inline-block; background: var(--primary-glow); color: var(--primary);
            padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;
            border: 1px solid rgba(232,121,43,0.2);
        }

        /* Accordion */
        .node-section {
            background: var(--card-bg); border: 1px solid var(--border);
            border-radius: 12px; margin-bottom: 10px; overflow: hidden;
            transition: 0.2s;
        }
        .node-section[open] { border-color: var(--primary); }
        .node-header {
            padding: 14px 18px; cursor: pointer; display: flex;
            justify-content: space-between; align-items: center;
            font-size: 15px; font-weight: 600; list-style: none;
            user-select: none;
        }
        .node-header::-webkit-details-marker { display: none; }
        .node-header::after {
            content: '▸'; font-size: 12px; color: var(--text-muted);
            transition: 0.2s;
        }
        .node-section[open] .node-header::after { transform: rotate(90deg); color: var(--primary); }
        .node-loc { font-size: 12px; color: var(--text-muted); font-weight: 400; }
        .node-keys {
            padding: 0 18px 18px; display: grid;
            grid-template-columns: 1fr 1fr; gap: 14px;
        }
        @media(max-width:500px) { .node-keys { grid-template-columns: 1fr; } }

        /* Key items */
        .key-item {
            background: var(--card-bg-alt); border-radius: 10px;
            padding: 16px; text-align: center;
            border: 1px solid var(--border);
        }
        .key-label { font-size: 14px; font-weight: 700; margin-bottom: 10px; }
        .qr-container {
            background: white; padding: 10px; border-radius: 8px;
            display: inline-block; margin-bottom: 12px;
        }
        .qr-container img { display: block; max-width: 160px; height: auto; }
        .btn {
            display: block; width: 100%; padding: 10px;
            background: var(--primary); color: #fff; font-weight: 700;
            font-size: 12px; border-radius: 7px; text-decoration: none;
            margin-bottom: 8px; transition: 0.15s;
            box-shadow: 0 2px 6px var(--primary-glow);
        }
        .btn:hover { background: var(--primary-hover); }
        .config-box {
            background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px;
            font-family: monospace; font-size: 9px; word-break: break-all;
            color: #a5f3fc; user-select: all; max-height: 50px; overflow-y: auto;
        }

        /* Legacy grid */
        .legacy-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px;
        }
        @media(max-width:500px) { .legacy-grid { grid-template-columns: 1fr; } }

        /* Apps */
        .apps-card {
            background: var(--card-bg); border-radius: 12px; padding: 20px;
            text-align: center; border: 1px solid var(--border);
        }
        .apps-title { font-size: 13px; font-weight: 600; margin-bottom: 10px; }
        .apps-grid { display: flex; flex-direction: column; gap: 6px; }
        .app-btn {
            background: rgba(255,255,255,0.04); color: var(--text);
            padding: 9px; border-radius: 7px; font-size: 12px;
            text-decoration: none; border: 1px solid var(--border); transition: 0.15s;
        }
        .app-btn:hover { background: rgba(255,255,255,0.08); border-color: var(--primary); }
    </style>
    """
