from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models import UserRole, ProtocolType, EntryType

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    agency_id: Optional[int] = None

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    agency_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: UserRole
    agency_id: Optional[int]

class AgencyCreate(BaseModel):
    name: str
    quota_awg: int = 20
    quota_vless: int = 10

class AgencyResponse(BaseModel):
    id: int
    name: str
    quota_awg: int
    quota_vless: int
    used_awg: int = 0
    used_vless: int = 0
    created_at: datetime

    class Config:
        from_attributes = True

class NodeCreate(BaseModel):
    name: str
    location: str
    node_type: str = "xui" # "xui" or "amnezia"
    xui_url: Optional[str] = None
    xui_api_token: Optional[str] = None
    xui_username: Optional[str] = None
    xui_password: Optional[str] = None
    xui_inbound_id: Optional[int] = None
    amnezia_url: Optional[str] = None
    amnezia_server_id: Optional[int] = None

class NodeResponse(BaseModel):
    id: int
    name: str
    location: str
    node_type: str
    xui_url: Optional[str]
    xui_inbound_id: Optional[int]
    amnezia_url: Optional[str]
    amnezia_server_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True



class ClientKeyCreate(BaseModel):
    employee_name: str
    protocol: ProtocolType
    node_id: int

class ClientKeyResponse(BaseModel):
    id: int
    secret_uuid: str
    employee_name: str
    protocol: ProtocolType
    config_content: str
    remote_client_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BlackholeCreate(BaseModel):
    entry_type: EntryType
    value: str
    description: Optional[str] = None

class BlackholeResponse(BaseModel):
    id: int
    entry_type: EntryType
    value: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
