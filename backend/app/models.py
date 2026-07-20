import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
import enum

from app.database import Base

class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    AGENCY_ADMIN = "agency_admin"

class ProtocolType(str, enum.Enum):
    AMNEZIA_WG = "awg"
    VLESS = "vless"

class EntryType(str, enum.Enum):
    DOMAIN = "domain"
    IP = "ip"

class Agency(Base):
    __tablename__ = "agencies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    quota_awg = Column(Integer, default=20)
    quota_vless = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    admins = relationship("User", back_populates="agency")
    keys = relationship("ClientKey", back_populates="agency", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.AGENCY_ADMIN)
    agency_id = Column(Integer, ForeignKey("agencies.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agency = relationship("Agency", back_populates="admins")

class NodeType(str, enum.Enum):
    XUI = "xui"
    AMNEZIA = "amnezia"

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    node_type = Column(String, default="xui") # "xui" or "amnezia"
    
    # 3X-UI credentials & Inbound ID
    xui_url = Column(String, nullable=True)
    xui_api_token = Column(String, nullable=True)
    xui_username = Column(String, nullable=True)
    xui_password = Column(String, nullable=True)
    xui_inbound_id = Column(Integer, nullable=True)
    
    # amneziavpnphp Master Panel URL & Server ID
    amnezia_url = Column(String, nullable=True)
    amnezia_server_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


    keys = relationship("ClientKey", back_populates="node", cascade="all, delete-orphan")



class ClientKey(Base):
    __tablename__ = "client_keys"

    id = Column(Integer, primary_key=True, index=True)
    secret_uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    agency_id = Column(Integer, ForeignKey("agencies.id"), nullable=False)
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    
    employee_name = Column(String, nullable=False)
    protocol = Column(Enum(ProtocolType), nullable=False)
    
    # Raw config string (vpn://... or vless://...)
    config_content = Column(Text, nullable=False)
    
    # Reference ID in amnezia/3xui for deletion
    remote_client_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agency = relationship("Agency", back_populates="keys")
    node = relationship("Node", back_populates="keys")

class BlackholeEntry(Base):
    __tablename__ = "blackhole_entries"

    id = Column(Integer, primary_key=True, index=True)
    entry_type = Column(Enum(EntryType), nullable=False)
    value = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
