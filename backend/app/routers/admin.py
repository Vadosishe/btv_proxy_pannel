from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, UserRole, Agency, Node, BlackholeEntry, ProtocolType,
    Template, Employee, ClientKey, template_nodes
)
from app.schemas import (
    AgencyCreate, AgencyResponse,
    UserCreate, UserResponse,
    NodeCreate, NodeResponse,
    BlackholeCreate, BlackholeResponse,
    TemplateCreate, TemplateUpdate, TemplateResponse,
    EmployeeResponse, AssignTemplate
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


# ==================== AGENCIES ====================

@router.post("/agencies", response_model=AgencyResponse)
def create_agency(payload: AgencyCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    existing = db.query(Agency).filter(Agency.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agency with this name already exists")
    
    agency = Agency(name=payload.name, quota_awg=payload.quota_awg, quota_vless=payload.quota_vless)
    db.add(agency)
    db.commit()
    db.refresh(agency)
    return _agency_to_response(agency)

@router.get("/agencies", response_model=List[AgencyResponse])
def list_agencies(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    agencies = db.query(Agency).all()
    return [_agency_to_response(a) for a in agencies]

@router.delete("/agencies/{agency_id}")
def delete_agency(agency_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    agency = db.query(Agency).get(agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    db.delete(agency)
    db.commit()
    return {"detail": "Agency deleted"}

def _agency_to_response(a: Agency) -> AgencyResponse:
    used_awg = sum(1 for e in a.employees for k in e.keys if k.protocol.value == "awg")
    used_vless = sum(1 for e in a.employees for k in e.keys if k.protocol.value == "vless")
    # Also count orphaned keys (without employee)
    used_awg += sum(1 for k in a.keys if k.protocol.value == "awg" and k.employee_id is None)
    used_vless += sum(1 for k in a.keys if k.protocol.value == "vless" and k.employee_id is None)
    return AgencyResponse(
        id=a.id, name=a.name,
        quota_awg=a.quota_awg, quota_vless=a.quota_vless,
        used_awg=used_awg, used_vless=used_vless,
        template_id=a.template_id,
        template_name=a.template.name if a.template else "",
        blacklist_profile_id=a.blacklist_profile_id,
        blacklist_profile_name=a.blacklist_profile.name if a.blacklist_profile else "",
        created_at=a.created_at
    )


# ==================== USERS ====================

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

@router.get("/users", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    return db.query(User).all()


# ==================== NODES ====================

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

    return {
        "node_id": node.id, "name": node.name, "node_type": str(node.node_type),
        "xui_connected": xui_status, "xui_error": xui_error,
        "amnezia_connected": amnezia_status, "amnezia_error": amnezia_error
    }


# ==================== TEMPLATES ====================

@router.post("/templates", response_model=TemplateResponse)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    existing = db.query(Template).filter(Template.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Template with this name already exists")
    template = Template(name=payload.name)
    if payload.node_ids:
        nodes = db.query(Node).filter(Node.id.in_(payload.node_ids)).all()
        template.nodes = nodes
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_to_response(template)

@router.get("/templates", response_model=List[TemplateResponse])
def list_templates(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    templates = db.query(Template).all()
    return [_template_to_response(t) for t in templates]

@router.put("/templates/{template_id}", response_model=TemplateResponse)
def update_template(template_id: int, payload: TemplateUpdate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    template = db.query(Template).get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if payload.name is not None:
        template.name = payload.name
    if payload.node_ids is not None:
        nodes = db.query(Node).filter(Node.id.in_(payload.node_ids)).all()
        template.nodes = nodes
    db.commit()
    db.refresh(template)
    return _template_to_response(template)

@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    template = db.query(Template).get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    # Unassign from agencies
    db.query(Agency).filter(Agency.template_id == template_id).update({Agency.template_id: None})
    db.delete(template)
    db.commit()
    return {"detail": "Template deleted"}

@router.put("/agencies/{agency_id}/template")
def assign_template_to_agency(agency_id: int, payload: AssignTemplate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    agency = db.query(Agency).get(agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    template = db.query(Template).get(payload.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    agency.template_id = payload.template_id
    db.commit()
    return {"detail": f"Template '{template.name}' assigned to '{agency.name}'"}

def _template_to_response(t: Template) -> TemplateResponse:
    return TemplateResponse(
        id=t.id, name=t.name,
        node_ids=[n.id for n in t.nodes],
        node_names=[f"{n.name} ({n.location})" for n in t.nodes],
        created_at=t.created_at
    )


# ==================== EMPLOYEES (superadmin) ====================

def _init_employee_tasks(name: str, agency: Agency, template: Template, db: Session) -> dict:
    employee = Employee(name=name, agency_id=agency.id)
    db.add(employee)
    db.commit()
    db.refresh(employee)

    tasks = []
    for node in template.nodes:
        if node.node_type == "amnezia":
            tasks.append({"node_id": node.id, "node_name": node.name, "node_location": node.location, "protocol": "awg", "suffix": "(phone)", "label": "Телефон"})
            tasks.append({"node_id": node.id, "node_name": node.name, "node_location": node.location, "protocol": "awg", "suffix": "(pc)", "label": "Компьютер"})
        elif node.node_type == "xui":
            tasks.append({"node_id": node.id, "node_name": node.name, "node_location": node.location, "protocol": "vless", "suffix": "", "label": "VLESS"})

    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "secret_uuid": employee.secret_uuid,
        "tasks": tasks
    }


async def _generate_single_key_for_employee(employee: Employee, node_id: int, protocol: str, suffix: str, db: Session) -> dict:
    from app.services.amnezia import AmneziaClient, format_amnezia_vpn_link
    from app.services.xui import XUIClient
    from app.config import settings

    node = db.query(Node).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    key_name = f"{employee.name} {suffix}".strip()
    
    if protocol == "awg":
        amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
        amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
        res = await amnezia.create_awg_client(node.amnezia_server_id or 1, key_name)
        vpn_link = format_amnezia_vpn_link(res["vpn_link"])
        ck = ClientKey(
            agency_id=employee.agency_id, node_id=node.id, employee_id=employee.id,
            employee_name=key_name, protocol=ProtocolType.AMNEZIA_WG,
            config_content=vpn_link, remote_client_id=res["client_id"]
        )
        db.add(ck)
        db.commit()
        return {"status": "ok", "key_name": key_name, "node_name": node.name, "vpn_link": vpn_link}
    elif protocol == "vless":
        if not node.xui_url or not node.xui_inbound_id:
            raise HTTPException(status_code=400, detail="Node is not configured for VLESS")
        xui = XUIClient(node.xui_url, username=node.xui_username, password=node.xui_password, api_token=node.xui_api_token)
        res = await xui.add_vless_client(node.xui_inbound_id, employee.name, group_name=employee.agency.name if employee.agency else "")
        ck = ClientKey(
            agency_id=employee.agency_id, node_id=node.id, employee_id=employee.id,
            employee_name=employee.name, protocol=ProtocolType.VLESS,
            config_content=res["vless_link"], remote_client_id=res["client_id"]
        )
        db.add(ck)
        db.commit()
        return {"status": "ok", "key_name": employee.name, "node_name": node.name, "vpn_link": res["vless_link"]}

    raise HTTPException(status_code=400, detail="Unknown protocol")


@router.get("/employees")
def list_all_employees(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    _ensure_orphan_keys_migrated(db)
    employees = db.query(Employee).all()
    return [_employee_to_dict(e) for e in employees]


@router.post("/employees/init")
def init_employee_creation(
    name: str, agency_id: int, template_id: int = None,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin)
):
    agency = db.query(Agency).get(agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    tmpl = db.query(Template).get(template_id) if template_id else agency.template
    if not tmpl or not tmpl.nodes:
        raise HTTPException(status_code=400, detail="К компании не привязан шаблон или в шаблоне нет серверных нод.")

    employee_count = db.query(Employee).filter(Employee.agency_id == agency_id).count()
    if employee_count >= agency.quota_awg:
        raise HTTPException(status_code=400, detail=f"Лимит сотрудников ({agency.quota_awg}) исчерпан!")

    return _init_employee_tasks(name, agency, tmpl, db)


@router.post("/employees/{employee_id}/generate_key")
async def generate_single_key(
    employee_id: int, payload: dict,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin)
):
    employee = db.query(Employee).get(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    node_id = payload.get("node_id")
    protocol = payload.get("protocol", "awg")
    suffix = payload.get("suffix", "")
    return await _generate_single_key_for_employee(employee, node_id, protocol, suffix, db)

@router.post("/employees")
async def create_employee_as_superadmin(
    name: str,
    agency_id: int,
    template_id: int = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin)
):
    agency = db.query(Agency).get(agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    
    # Determine template
    tmpl = None
    if template_id:
        tmpl = db.query(Template).get(template_id)
    elif agency.template_id:
        tmpl = agency.template
    
    if not tmpl:
        raise HTTPException(status_code=400, detail="К компании не привязан шаблон. Назначьте шаблон компании.")

    if not tmpl.nodes:
        raise HTTPException(status_code=400, detail=f"В шаблоне '{tmpl.name}' нет серверных нод! Добавьте ноды в шаблон.")

    # Check quota (count employees, not keys)
    employee_count = db.query(Employee).filter(Employee.agency_id == agency_id).count()
    if employee_count >= agency.quota_awg:
        raise HTTPException(status_code=400, detail=f"Лимит сотрудников ({agency.quota_awg}) исчерпан!")

    return await _create_employee_with_keys(name, agency, tmpl, db)

@router.get("/employees/{employee_id}/delete_tasks")
def get_employee_delete_tasks(employee_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    employee = db.query(Employee).get(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    keys = []
    for k in employee.keys:
        keys.append({
            "id": k.id,
            "name": k.employee_name,
            "node_name": k.node.name if k.node else "Неизвестный сервер"
        })
    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "keys": keys
    }

@router.delete("/employees/{employee_id}/revoke_key/{key_id}")
async def revoke_employee_single_key(employee_id: int, key_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    employee = db.query(Employee).get(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    key = db.query(ClientKey).filter(ClientKey.id == key_id, ClientKey.employee_id == employee_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found for this employee")
    
    await _revoke_single_key(key, db)
    
    remaining = db.query(ClientKey).filter(ClientKey.employee_id == employee_id).count()
    employee_deleted = False
    if remaining == 0:
        db.delete(employee)
        db.commit()
        employee_deleted = True
        
    return {"status": "ok", "key_id": key_id, "remaining": remaining, "employee_deleted": employee_deleted}

@router.delete("/employees/{employee_id}")
async def delete_employee_as_superadmin(employee_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    employee = db.query(Employee).get(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    await _revoke_employee_keys(employee, db)
    db.delete(employee)
    db.commit()
    return {"detail": f"Employee '{employee.name}' and all keys deleted"}


# ==================== KEYS (legacy, kept for backward compat) ====================

@router.get("/keys")
async def list_all_keys(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    from app.services.sync_service import sync_remote_amnezia_keys
    await sync_remote_amnezia_keys(db)
    keys = db.query(ClientKey).all()
    result = []
    for k in keys:
        result.append({
            "id": k.id, "secret_uuid": k.secret_uuid,
            "agency_id": k.agency_id, "agency_name": k.agency.name if k.agency else "N/A",
            "employee_name": k.employee_name, "protocol": k.protocol.value,
            "node_name": k.node.name if k.node else "N/A",
            "config_content": k.config_content, "remote_client_id": k.remote_client_id,
            "created_at": k.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return result

@router.post("/keys/create")
async def create_key_as_superadmin(
    agency_id: int, employee_name: str, protocol: ProtocolType, node_id: int,
    db: Session = Depends(get_db), _: User = Depends(require_superadmin)
):
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
        agency_id=agency.id, node_id=node.id, employee_name=employee_name,
        protocol=protocol, config_content=config_content, remote_client_id=remote_id
    )
    db.add(client_key)
    db.commit()
    db.refresh(client_key)
    return client_key

async def _revoke_single_key(key: ClientKey, db: Session):
    from app.services.amnezia import AmneziaClient
    from app.services.xui import XUIClient
    from app.config import settings

    if key.node:
        node = key.node
        try:
            if key.protocol == ProtocolType.AMNEZIA_WG and key.remote_client_id:
                amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
                amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
                await amnezia.delete_awg_client(key.remote_client_id)
            elif key.protocol == ProtocolType.VLESS and node.xui_url and node.xui_inbound_id:
                xui = XUIClient(node.xui_url, username=node.xui_username, password=node.xui_password, api_token=node.xui_api_token)
                await xui.delete_client(node.xui_inbound_id, key.remote_client_id, email=f"{key.employee_name}_{key.remote_client_id[:6] if key.remote_client_id else ''}")
        except Exception:
            pass
    db.delete(key)
    db.commit()


@router.delete("/keys/{key_id}")
async def delete_key_as_superadmin(key_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    key = db.query(ClientKey).get(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    await _revoke_single_key(key, db)
    return {"detail": "Key revoked successfully by SuperAdmin"}


# ==================== BLACKHOLE ====================

@router.post("/blackhole", response_model=BlackholeResponse)
def add_blackhole_entry(payload: BlackholeCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    entry = BlackholeEntry(**payload.dict())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ==================== SHARED HELPERS ====================

def _ensure_orphan_keys_migrated(db: Session, agency_id: int = None):
    import re, uuid
    query = db.query(ClientKey).filter(ClientKey.employee_id == None)
    if agency_id:
        query = query.filter(ClientKey.agency_id == agency_id)
    orphans = query.all()
    if not orphans:
        return
    groups = {}
    for k in orphans:
        base = re.sub(r'\s*\((phone|pc|Phone|PC)\)\s*$', '', k.employee_name).strip()
        key = (base, k.agency_id)
        if key not in groups:
            groups[key] = []
        groups[key].append(k)
        
    for (base_name, aid), keys_list in groups.items():
        emp = Employee(name=base_name, agency_id=aid, secret_uuid=str(uuid.uuid4()))
        db.add(emp)
        db.flush()
        for k in keys_list:
            k.employee_id = emp.id
    db.commit()


def _init_employee_tasks(name: str, agency: Agency, template: Template, db: Session) -> dict:
    employee = Employee(name=name, agency_id=agency.id)
    db.add(employee)
    db.commit()
    db.refresh(employee)

    tasks = []
    for node in template.nodes:
        if node.node_type == "amnezia":
            tasks.append({"node_id": node.id, "node_name": node.name, "node_location": node.location, "protocol": "awg", "suffix": "(phone)", "label": "Телефон"})
            tasks.append({"node_id": node.id, "node_name": node.name, "node_location": node.location, "protocol": "awg", "suffix": "(pc)", "label": "Компьютер"})
        elif node.node_type == "xui":
            tasks.append({"node_id": node.id, "node_name": node.name, "node_location": node.location, "protocol": "vless", "suffix": "", "label": "VLESS"})

    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "secret_uuid": employee.secret_uuid,
        "tasks": tasks
    }


async def _generate_single_key_for_employee(employee: Employee, node_id: int, protocol: str, suffix: str, db: Session) -> dict:
    from app.services.amnezia import AmneziaClient, format_amnezia_vpn_link
    from app.services.xui import XUIClient
    from app.config import settings

    node = db.query(Node).get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    key_name = f"{employee.name} {suffix}".strip()
    
    if protocol == "awg":
        amnezia_target_url = node.amnezia_url or settings.AMNEZIA_API_URL
        amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
        res = await amnezia.create_awg_client(node.amnezia_server_id or 1, key_name)
        vpn_link = format_amnezia_vpn_link(res["vpn_link"])
        ck = ClientKey(
            agency_id=employee.agency_id, node_id=node.id, employee_id=employee.id,
            employee_name=key_name, protocol=ProtocolType.AMNEZIA_WG,
            config_content=vpn_link, remote_client_id=res["client_id"]
        )
        db.add(ck)
        db.commit()
        return {"status": "ok", "key_name": key_name, "node_name": node.name, "vpn_link": vpn_link}
    elif protocol == "vless":
        if not node.xui_url or not node.xui_inbound_id:
            raise HTTPException(status_code=400, detail="Node is not configured for VLESS")
        xui = XUIClient(node.xui_url, username=node.xui_username, password=node.xui_password, api_token=node.xui_api_token)
        res = await xui.add_vless_client(node.xui_inbound_id, employee.name, group_name=employee.agency.name if employee.agency else "")
        ck = ClientKey(
            agency_id=employee.agency_id, node_id=node.id, employee_id=employee.id,
            employee_name=employee.name, protocol=ProtocolType.VLESS,
            config_content=res["vless_link"], remote_client_id=res["client_id"]
        )
        db.add(ck)
        db.commit()
        return {"status": "ok", "key_name": employee.name, "node_name": node.name, "vpn_link": res["vless_link"]}

    raise HTTPException(status_code=400, detail="Unknown protocol")


async def _create_employee_with_keys(name: str, agency: Agency, template: Template, db: Session) -> dict:
    """Create an Employee and all keys on template nodes."""
    res_tasks = _init_employee_tasks(name, agency, template, db)
    employee = db.query(Employee).get(res_tasks["employee_id"])

    created_keys = []
    errors = []

    for t in res_tasks["tasks"]:
        try:
            r = await _generate_single_key_for_employee(employee, t["node_id"], t["protocol"], t["suffix"], db)
            created_keys.append(r)
        except Exception as e:
            errors.append({"name": t["node_name"], "error": str(e)})

    if not created_keys:
        await _revoke_employee_keys(employee, db)
        db.delete(employee)
        db.commit()
        err_msg = "; ".join([e["error"] for e in errors]) if errors else "Неизвестная ошибка нод"
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось создать ни одного ключа на серверах: {err_msg}"
        )

    db.refresh(employee)
    return {
        "employee": _employee_to_dict(employee),
        "created_keys": created_keys,
        "errors": errors
    }

async def _revoke_employee_keys(employee: Employee, db: Session):
    """Revoke all keys for an employee on remote servers."""
    from app.services.amnezia import AmneziaClient
    from app.config import settings

    for key in employee.keys:
        try:
            if key.node and key.protocol == ProtocolType.AMNEZIA_WG and key.remote_client_id:
                amnezia_target_url = key.node.amnezia_url or settings.AMNEZIA_API_URL
                amnezia = AmneziaClient(amnezia_target_url, settings.AMNEZIA_ADMIN_EMAIL, settings.AMNEZIA_ADMIN_PASSWORD)
                await amnezia.delete_awg_client(key.remote_client_id)
            elif key.node and key.protocol == ProtocolType.VLESS and key.node.xui_url:
                from app.services.xui import XUIClient
                xui = XUIClient(key.node.xui_url, username=key.node.xui_username, password=key.node.xui_password, api_token=key.node.xui_api_token)
                await xui.delete_client(key.node.xui_inbound_id, key.remote_client_id, email=f"{key.employee_name}_{key.remote_client_id[:6] if key.remote_client_id else ''}")
        except Exception:
            pass  # Best effort remote deletion

def _employee_to_dict(e: Employee) -> dict:
    return {
        "id": e.id, "name": e.name,
        "agency_id": e.agency_id, "agency_name": e.agency.name if e.agency else "",
        "secret_uuid": e.secret_uuid,
        "keys_count": len(e.keys),
        "keys": [{
            "id": k.id, "employee_name": k.employee_name,
            "protocol": k.protocol.value,
            "node_name": k.node.name if k.node else "N/A",
            "node_location": k.node.location if k.node else "",
        } for k in e.keys],
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M")
    }


# ==================== BLACKLIST PROFILES ====================

from app.models import BlacklistProfile, BlacklistRule, EntryType
from app.schemas import BlacklistProfileCreate, BlacklistProfileResponse, BlacklistRuleCreate, BlacklistRuleResponse
from app.services.blacklist import sync_node_blacklist

@router.get("/blacklist-profiles", response_model=List[BlacklistProfileResponse])
def list_blacklist_profiles(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    return db.query(BlacklistProfile).all()

@router.post("/blacklist-profiles", response_model=BlacklistProfileResponse)
def create_blacklist_profile(payload: BlacklistProfileCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    existing = db.query(BlacklistProfile).filter(BlacklistProfile.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Профиль с таким названием уже существует")
    
    if payload.is_global:
        db.query(BlacklistProfile).update({BlacklistProfile.is_global: False})
        db.commit()

    profile = BlacklistProfile(name=payload.name, description=payload.description, is_global=payload.is_global)
    db.add(profile)
    db.commit()
    db.refresh(profile)

    if payload.rules:
        for r in payload.rules:
            rule = BlacklistRule(profile_id=profile.id, entry_type=r.entry_type, target_value=r.target_value.strip())
            db.add(rule)
        db.commit()
        db.refresh(profile)

    return profile

@router.post("/blacklist-profiles/{profile_id}/rules", response_model=BlacklistRuleResponse)
def add_rule_to_profile(profile_id: int, payload: BlacklistRuleCreate, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    profile = db.query(BlacklistProfile).get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    rule = BlacklistRule(profile_id=profile.id, entry_type=payload.entry_type, target_value=payload.target_value.strip())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@router.delete("/blacklist-profiles/{profile_id}/rules/{rule_id}")
def delete_rule_from_profile(profile_id: int, rule_id: int, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    rule = db.query(BlacklistRule).filter(BlacklistRule.id == rule_id, BlacklistRule.profile_id == profile_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    db.delete(rule)
    db.commit()
    return {"detail": "Правило удалено"}

@router.put("/agencies/{agency_id}/blacklist-profile")
def assign_blacklist_profile_to_agency(agency_id: int, payload: dict, db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    agency = db.query(Agency).get(agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    profile_id = payload.get("blacklist_profile_id")
    agency.blacklist_profile_id = profile_id
    db.commit()
    return {"detail": "Шаблон блэклиста назначен компании"}

@router.post("/blacklist-profiles/sync")
def sync_all_blacklist_rules(db: Session = Depends(get_db), _: User = Depends(require_superadmin)):
    nodes = db.query(Node).all()
    results = []
    for n in nodes:
        res = sync_node_blacklist(n.id, db)
        results.append({"node_id": n.id, "node_name": n.name, "result": res})
    return {"status": "ok", "synced_nodes": results}

