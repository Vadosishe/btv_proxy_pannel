from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, Agency, Node, BlackholeEntry
from app.schemas import (
    AgencyCreate, AgencyResponse,
    UserCreate, UserResponse,
    NodeCreate, NodeResponse,
    BlackholeCreate, BlackholeResponse
)
from app.routers.auth import get_current_user, get_password_hash

router = APIRouter(prefix="/api/admin", tags=["SuperAdmin"])

def require_superadmin(user: User = Depends(get_current_user)):
    if user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden. SuperAdmin only."
        )
    return user

@router.post("/agencies", response_model=AgencyResponse)
def create_agency(payload: AgencyCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    existing = db.query(Agency).filter(Agency.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agency with this name already exists")
    
    agency = Agency(name=payload.name, quota_awg=payload.quota_awg, quota_vless=payload.quota_vless)
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return agency

@router.get("/agencies", response_model=List[AgencyResponse])
def list_agencies(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    agencies = db.query(Agency).all()
    result = []
    for a in agencies:
        used_awg = sum(1 for k in a.keys if k.protocol.value == "awg")
        used_vless = sum(1 for k in a.keys if k.protocol.value == "vless")
        result.append(AgencyResponse(
            id=a.id,
            name=a.name,
            quota_awg=a.quota_awg,
            quota_vless=a.quota_vless,
            used_awg=used_awg,
            used_vless=used_vless,
            created_at=a.created_at
        ))
    return result

@router.post("/users", response_model=UserResponse)
def register_agency_admin(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    if payload.agency_id:
        agency = db.query(Agency).get(payload.agency_id)
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role=UserRole.AGENCY_ADMIN,
        agency_id=payload.agency_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/nodes", response_model=NodeResponse)
def add_node(payload: NodeCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    node = Node(**payload.dict())
    db.add(node)
    db.commit()
    db.refresh(node)
    return node

@router.get("/nodes", response_model=List[NodeResponse])
def list_nodes(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Node).all()

@router.post("/blackhole", response_model=BlackholeResponse)
def add_blackhole_entry(payload: BlackholeCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    entry = BlackholeEntry(**payload.dict())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/users", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    return db.query(User).all()

@router.get("/keys")
def list_all_keys(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    from app.models import ClientKey
    keys = db.query(ClientKey).all()
    result = []
    for k in keys:
        result.append({
            "id": k.id,
            "secret_uuid": k.secret_uuid,
            "agency_id": k.agency_id,
            "agency_name": k.agency.name if k.agency else "N/A",
            "employee_name": k.employee_name,
            "protocol": k.protocol.value,
            "node_name": k.node.name if k.node else "N/A",
            "config_content": k.config_content,
            "created_at": k.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return result

@router.delete("/nodes/{node_id}")
def delete_node(node_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    node = db.query(Node).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    db.delete(node)
    db.commit()
    return {"detail": "Node deleted successfully"}

@router.post("/nodes/{node_id}/test")
async def test_node_connection(node_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    node = db.query(Node).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    xui_status = False
    xui_error = None
    amnezia_status = False
    amnezia_error = None

    if node.node_type == "xui":
        if node.xui_url:
            try:
                from app.services.xui import XUIClient
                xui = XUIClient(node.xui_url, username=node.xui_username, password=node.xui_password, api_token=node.xui_api_token)
                xui_status = await xui.login()
            except Exception as e:
                xui_error = str(e)
    else:
        if node.amnezia_server_id:
            try:
                from app.services.amnezia import AmneziaClient
                from app.config import settings
                amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
                amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
                amnezia_status = await amnezia.login()
            except Exception as e:
                amnezia_error = str(e)


@router.post("/keys/create")
async def create_key_as_superadmin(
    agency_id: int,
    employee_name: str,
    protocol: ProtocolType,
    node_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin)
):
    from app.models import Agency, Node, ClientKey
    from app.services.amnezia import AmneziaClient
    from app.services.xui import XUIClient
    from app.config import settings

    agency = db.query(Agency).get(agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    node = db.query(Node).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    config_content = ""
    remote_id = None

    if protocol == ProtocolType.AMNEZIA_WG:
        amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
        amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
        res = await amnezia.create_awg_client(node.amnezia_server_id or 1, employee_name)
        config_content = res["vpn_link"]
        remote_id = res["client_id"]

    elif protocol == ProtocolType.VLESS:
        if not node.xui_url or not node.xui_inbound_id:
            raise HTTPException(status_code=400, detail="Node is not configured for VLESS / 3X-UI")

        xui = XUIClient(node.xui_url, username=node.xui_username, password=node.xui_password, api_token=node.xui_api_token)
        res = await xui.add_vless_client(node.xui_inbound_id, employee_name, group_name=agency.name)
        config_content = res["vless_link"]
        remote_id = res["client_id"]

    client_key = ClientKey(
        agency_id=agency.id,
        node_id=node.id,
        employee_name=employee_name,
        protocol=protocol,
        config_content=config_content,
        remote_client_id=remote_id
    )
    db.add(client_key)
    db.commit()
    db.refresh(client_key)
    return client_key





