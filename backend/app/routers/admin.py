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

@router.get("/blackhole", response_model=List[BlackholeResponse])
def list_blackhole(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(BlackholeEntry).all()
