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
    employee = db.query(Employee).filter(Employee.secret_uuid == secret_uuid).first()
    if employee:
        return _render_employee_page(employee)

    key = db.query(ClientKey).filter(ClientKey.secret_uuid == secret_uuid).first()
    if not key:
        raise HTTPException(status_code=404, detail="VPN Access Link not found or revoked.")

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
    agency_name = employee.agency.name if employee.agency else "Компания"

    from app.services.amnezia import format_amnezia_vpn_link

    nodes_map = {}
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
        cfg = format_amnezia_vpn_link(k.config_content) if k.protocol == ProtocolType.AMNEZIA_WG else k.config_content
        nodes_map[nid]["keys"].append({
            "label": label,
            "config": cfg,
            "protocol": k.protocol.value,
            "qr": generate_qr_data_url(cfg)
        })

    for ndata in nodes_map.values():
        ndata["keys"].sort(key=lambda x: 0 if "Телефон" in x["label"] else 1 if "Компьютер" in x["label"] else 2)

    accordion_html = ""
    for idx, (nid, ndata) in enumerate(nodes_map.items()):
        icon = "🔒" if ndata["node_type"] == "amnezia" else "⚡"
        keys_html = ""
        for ki in ndata["keys"]:
            esc_cfg = ki["config"].replace("'", "\\'")
            keys_html += f"""
            <div class="key-item">
                <div class="key-label">{ki["label"]}</div>
                <div class="qr-container"><img src="{ki["qr"]}" alt="QR"></div>
                <button onclick="copyKeyText(this, '{esc_cfg}')" class="btn btn-copy">Скопировать ключ</button>
                <a href="{ki["config"]}" class="btn btn-subtle">Подключить в 1 клик</a>
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

    app_links = _get_app_links()

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
                <div class="logo"><div class="logo-mark">BT</div>BigTime <b>Tunnel</b></div><br>
                <h1>Привет, {employee.name}!</h1>
                <p class="subtitle">Корпоративный VPN · <strong>{agency_name}</strong></p>
                <div class="keys-badge">{len(employee.keys)} ключей на {len(nodes_map)} серверах</div>
            </div>
            {accordion_html}
            <div class="apps-card">
                <div class="apps-title">Приложения и Зеркала:</div>
                {app_links}
            </div>
        </div>
        <script>
            function copyKeyText(btn, text) {{
                navigator.clipboard.writeText(text);
                const orig = btn.innerText;
                btn.innerText = '✓ Скопировано!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.innerText = orig;
                    btn.classList.remove('copied');
                }}, 2000);
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


def _render_legacy_page(key, siblings, base_name) -> HTMLResponse:
    agency_name = key.agency.name if key.agency else "Компания"
    protocol_title = "AmneziaWG v2" if key.protocol == ProtocolType.AMNEZIA_WG else "VLESS / Reality"

    from app.services.amnezia import format_amnezia_vpn_link
    key_cards_html = ""
    for i, k in enumerate(siblings):
        label = "📱 Телефон" if k.employee_name.lower().endswith("(phone)") else \
                "💻 Компьютер" if k.employee_name.lower().endswith("(pc)") else \
                f"🔑 Ключ {i+1}" if len(siblings) > 1 else "🔑 Ваш ключ"
        cfg = format_amnezia_vpn_link(k.config_content) if k.protocol == ProtocolType.AMNEZIA_WG else k.config_content
        qr_url = generate_qr_data_url(cfg)
        esc_cfg = cfg.replace("'", "\\'")
        key_cards_html += f"""
        <div class="key-item">
            <div class="key-label">{label}</div>
            <div class="qr-container"><img src="{qr_url}" alt="QR"></div>
            <button onclick="copyKeyText(this, '{esc_cfg}')" class="btn btn-copy">Скопировать ключ</button>
            <a href="{cfg}" class="btn btn-subtle">Подключить в 1 клик</a>
            <div class="config-box">{cfg}</div>
        </div>
        """

    app_links = _get_app_links()

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
                <div class="logo"><div class="logo-mark">BT</div>BigTime <b>Tunnel</b></div><br>
                <span class="keys-badge">{protocol_title}</span>
                <h1>Привет, {base_name}!</h1>
                <p class="subtitle">Корпоративный VPN · <strong>{agency_name}</strong></p>
            </div>
            <div class="legacy-grid">{key_cards_html}</div>
            <div class="apps-card">
                <div class="apps-title">Приложения и Зеркала:</div>
                {app_links}
            </div>
        </div>
        <script>
            function copyKeyText(btn, text) {{
                navigator.clipboard.writeText(text);
                const orig = btn.innerText;
                btn.innerText = '✓ Скопировано!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.innerText = orig;
                    btn.classList.remove('copied');
                }}, 2000);
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


def _get_base_name(name: str) -> str:
    for suffix in [" (phone)", " (pc)", " (Phone)", " (PC)"]:
        if name.endswith(suffix):
            return name[:-len(suffix)].strip()
    return name.strip()


def _get_app_links() -> str:
    return """
    <div class="apps-grid">
        <a href="https://amnezia.org" target="_blank" class="app-btn">🌐 Amnezia.org (Официальный сайт)</a>
        <a href="https://storage.googleapis.com/amnezia/amnezia.org" target="_blank" class="app-btn">☁️ Зеркало Amnezia (Google Cloud)</a>
        <a href="https://dfvpn.com/" target="_blank" class="app-btn">📱 defaultVPN (iPhone iOS App Store)</a>
        <a href="https://github.com/amnezia-vpn/amnezia-client/releases" target="_blank" class="app-btn">📦 GitHub Releases (Desktop / APK)</a>
    </div>
    """


def _get_styles() -> str:
    return """
    <style>
        :root {
            --bg: #f8fafc; --card-bg: #ffffff; --card-bg-alt: #f1f5f9;
            --primary: #ff5b24; --primary-hover: #e04a18;
            --primary-glow: rgba(255, 91, 36, 0.18);
            --text: #0f172a; --text-muted: #64748b; --border: #e2e8f0;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg); color: var(--text);
            padding: 20px; display: flex; justify-content: center;
            min-height: 100vh;
        }
        .container { max-width: 560px; width: 100%; margin-top: 20px; }
        .header-card {
            background: var(--card-bg); border-radius: 16px; padding: 28px;
            text-align: center; border: 1px solid var(--border);
            margin-bottom: 16px;
            box-shadow: 0 4px 20px rgba(15, 23, 42, 0.05);
        }
        .logo {
            display: inline-flex; align-items: center; gap: 8px;
            font-size: 17px; font-weight: 800; margin-bottom: 14px; color: var(--text);
        }
        .logo-mark {
            width: 32px; height: 32px; border-radius: 8px;
            background: var(--primary);
            display: flex; align-items: center; justify-content: center;
            font-size: 13px; color: #fff; font-weight: 800;
        }
        .logo b { color: var(--primary); }
        h1 { font-size: 22px; font-weight: 800; letter-spacing: -0.3px; margin-bottom: 4px; }
        .subtitle { color: var(--text-muted); font-size: 13px; margin-bottom: 12px; }
        .keys-badge {
            display: inline-block; background: rgba(255, 91, 36, 0.1); color: var(--primary);
            padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700;
            border: 1px solid rgba(255, 91, 36, 0.2);
        }

        .node-section {
            background: var(--card-bg); border: 1px solid var(--border);
            border-radius: 12px; margin-bottom: 12px; overflow: hidden;
            transition: 0.2s; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
        }
        .node-section[open] { border-color: var(--primary); }
        .node-header {
            padding: 16px 20px; cursor: pointer; display: flex;
            justify-content: space-between; align-items: center;
            font-size: 15px; font-weight: 700; list-style: none;
            user-select: none;
        }
        .node-header::-webkit-details-marker { display: none; }
        .node-header::after {
            content: '▸'; font-size: 12px; color: var(--text-muted);
            transition: 0.2s;
        }
        .node-section[open] .node-header::after { transform: rotate(90deg); color: var(--primary); }
        .node-loc { font-size: 12px; color: var(--text-muted); font-weight: 600; }
        .node-keys {
            padding: 0 18px 18px; display: grid;
            grid-template-columns: 1fr 1fr; gap: 14px;
        }
        @media(max-width:500px) { .node-keys { grid-template-columns: 1fr; } }

        .key-item {
            background: var(--card-bg-alt); border-radius: 10px;
            padding: 16px; text-align: center;
            border: 1px solid var(--border);
        }
        .key-label { font-size: 14px; font-weight: 700; margin-bottom: 10px; color: var(--text); }
        .qr-container {
            background: white; padding: 10px; border-radius: 8px;
            display: inline-block; margin-bottom: 12px; border: 1px solid var(--border);
        }
        .qr-container img { display: block; max-width: 160px; height: auto; }
        .btn {
            display: block; width: 100%; padding: 10px;
            background: var(--primary); color: #fff; font-weight: 700;
            font-size: 12px; border-radius: 8px; text-decoration: none; border: none; cursor: pointer;
            margin-bottom: 8px; transition: 0.15s;
            box-shadow: 0 2px 8px var(--primary-glow);
        }
        .btn:hover { background: var(--primary-hover); }
        .btn-copy { background: #0f172a; color: #fff; }
        .btn-copy:hover { background: #1e293b; }
        .btn-copy.copied { background: #10b981 !important; }
        .btn-subtle { background: #e2e8f0; color: #334155; box-shadow: none; }
        .btn-subtle:hover { background: #cbd5e1; }

        .config-box {
            background: #ffffff; padding: 8px; border-radius: 6px; border: 1px solid var(--border);
            font-family: monospace; font-size: 10px; word-break: break-all;
            color: var(--text-muted); user-select: all; max-height: 50px; overflow-y: auto;
        }

        .legacy-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px;
        }
        @media(max-width:500px) { .legacy-grid { grid-template-columns: 1fr; } }

        .apps-card {
            background: var(--card-bg); border-radius: 12px; padding: 20px;
            text-align: center; border: 1px solid var(--border); box-shadow: 0 4px 20px rgba(15, 23, 42, 0.05);
        }
        .apps-title { font-size: 14px; font-weight: 700; margin-bottom: 12px; color: var(--text); }
        .apps-grid { display: flex; flex-direction: column; gap: 8px; }
        .app-btn {
            background: #f1f5f9; color: var(--text);
            padding: 10px 14px; border-radius: 8px; font-size: 13px; font-weight: 600;
            text-decoration: none; border: 1px solid var(--border); transition: 0.15s;
            display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        .app-btn:hover { background: #ffffff; border-color: var(--primary); color: var(--primary); transform: translateY(-1px); }
    </style>
    """
