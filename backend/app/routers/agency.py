from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, Agency, Node, ClientKey, ProtocolType, Employee, Template
from app.schemas import ClientKeyCreate, ClientKeyResponse, AgencyResponse
from app.routers.auth import get_current_user
from app.services.amnezia import AmneziaClient
from app.services.xui import XUIClient
from app.services.zip_exporter import generate_agency_keys_zip
from app.config import settings

router = APIRouter(prefix="/api/agency", tags=["AgencyAdmin"])

def require_agency(user: User = Depends(get_current_user)):
    if not user.agency_id and user.role != UserRole.SUPERADMIN:
        raise HTTPException(status_code=403, detail="No agency associated with this user")
    return user


@router.get("/me")
def get_my_agency(db: Session = Depends(get_db), current_user: User = Depends(require_agency)):
    agency = db.query(Agency).get(current_user.agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    employee_count = db.query(Employee).filter(Employee.agency_id == agency.id).count()

    return {
        "id": agency.id,
        "name": agency.name,
        "quota_awg": agency.quota_awg,
        "quota_vless": agency.quota_vless,
        "employee_count": employee_count,
        "template_id": agency.template_id,
        "template_name": agency.template.name if agency.template else "",
        "created_at": agency.created_at.isoformat()
    }


# ==================== EMPLOYEES ====================

@router.get("/employees")
def list_my_employees(db: Session = Depends(get_db), current_user: User = Depends(require_agency)):
    from app.routers.admin import _ensure_orphan_keys_migrated
    _ensure_orphan_keys_migrated(db, agency_id=current_user.agency_id)
    employees = db.query(Employee).filter(Employee.agency_id == current_user.agency_id).all()
    result = []
    for e in employees:
        result.append({
            "id": e.id,
            "name": e.name,
            "secret_uuid": e.secret_uuid,
            "keys_count": len(e.keys),
            "keys": [{
                "id": k.id,
                "employee_name": k.employee_name,
                "protocol": k.protocol.value,
                "node_name": k.node.name if k.node else "N/A",
                "node_location": k.node.location if k.node else "",
            } for k in e.keys],
            "created_at": e.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return result


@router.post("/employees")
async def create_employee(
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agency)
):
    agency = db.query(Agency).get(current_user.agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    
    if not agency.template:
        raise HTTPException(status_code=400, detail="Шаблон не настроен. Обратитесь к администратору.")

    # Check quota (employee count)
    employee_count = db.query(Employee).filter(Employee.agency_id == agency.id).count()
    if employee_count >= agency.quota_awg:
        raise HTTPException(status_code=400, detail=f"Лимит сотрудников ({agency.quota_awg}) исчерпан!")

    # Use shared helper from admin module
    from app.routers.admin import _create_employee_with_keys
    return await _create_employee_with_keys(name, agency, agency.template, db)


@router.delete("/employees/{employee_id}")
async def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agency)
):
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.agency_id == current_user.agency_id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    from app.routers.admin import _revoke_employee_keys
    await _revoke_employee_keys(employee, db)
    db.delete(employee)
    db.commit()
    return {"detail": f"Сотрудник '{employee.name}' и все ключи удалены"}


# ==================== LEGACY KEY ENDPOINTS (backward compat) ====================

@router.get("/keys", response_model=List[ClientKeyResponse])
async def list_my_keys(db: Session = Depends(get_db), current_user: User = Depends(require_agency)):
    from app.services.sync_service import sync_remote_amnezia_keys
    await sync_remote_amnezia_keys(db)
    return db.query(ClientKey).filter(ClientKey.agency_id == current_user.agency_id).all()

@router.post("/keys/create", response_model=ClientKeyResponse)
async def create_client_key(
    payload: ClientKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agency)
):
    agency = db.query(Agency).get(current_user.agency_id)
    node = db.query(Node).get(payload.node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Selected server node not found")

    existing_keys = db.query(ClientKey).filter(
        ClientKey.agency_id == current_user.agency_id,
        ClientKey.protocol == payload.protocol
    ).all()

    config_content = ""
    remote_id = None

    if payload.protocol == ProtocolType.AMNEZIA_WG:
        if len(existing_keys) >= agency.quota_awg:
            raise HTTPException(status_code=400, detail=f"AmneziaWG key quota limit ({agency.quota_awg}) reached!")
        amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
        amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
        res = await amnezia.create_awg_client(node.amnezia_server_id or 1, payload.employee_name)
        config_content = res["vpn_link"]
        remote_id = res["client_id"]
    elif payload.protocol == ProtocolType.VLESS:
        if len(existing_keys) >= agency.quota_vless:
            raise HTTPException(status_code=400, detail=f"VLESS key quota limit ({agency.quota_vless}) reached!")
        if not node.xui_url or not node.xui_inbound_id:
            raise HTTPException(status_code=400, detail="Node is not configured for VLESS / 3X-UI")
        xui = XUIClient(node.xui_url, username=node.xui_username, password=node.xui_password, api_token=node.xui_api_token)
        res = await xui.add_vless_client(node.xui_inbound_id, payload.employee_name, group_name=agency.name)
        config_content = res["vless_link"]
        remote_id = res["client_id"]

    client_key = ClientKey(
        agency_id=agency.id, node_id=node.id, employee_name=payload.employee_name,
        protocol=payload.protocol, config_content=config_content, remote_client_id=remote_id
    )
    db.add(client_key)
    db.commit()
    db.refresh(client_key)
    return client_key

@router.delete("/keys/{key_id}")
async def revoke_key(key_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_agency)):
    key = db.query(ClientKey).filter(ClientKey.id == key_id, ClientKey.agency_id == current_user.agency_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    if key.node:
        node = key.node
        if key.protocol == ProtocolType.AMNEZIA_WG and key.remote_client_id:
            amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
            amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
            await amnezia.delete_awg_client(key.remote_client_id)
        elif key.protocol == ProtocolType.VLESS and node.xui_url and node.xui_inbound_id:
            xui = XUIClient(node.xui_url, username=node.xui_username, password=node.xui_password, api_token=node.xui_api_token)
            await xui.delete_client(node.xui_inbound_id, key.remote_client_id, email=f"{key.employee_name}_{key.remote_client_id[:6] if key.remote_client_id else ''}")
    db.delete(key)
    db.commit()
    return {"detail": "Key revoked successfully"}


@router.get("/export/zip")
def download_keys_zip(db: Session = Depends(get_db), current_user: User = Depends(require_agency)):
    agency = db.query(Agency).get(current_user.agency_id)
    keys = db.query(ClientKey).filter(ClientKey.agency_id == current_user.agency_id).all()
    zip_bytes = generate_agency_keys_zip(agency.name, keys)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{agency.name}_vpn_keys.zip"'}
    )
