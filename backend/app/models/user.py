import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    is_active = Column(Boolean, default=True)
    cobranca_cooldown_hours = Column(Integer, nullable=False, default=48)
    created_at = Column(DateTime, default=datetime.utcnow)

    eco_usuario = Column(String(50), nullable=True, index=True)
    eco_empresa = Column(String(20), nullable=True)
    tab_permissions = Column(JSON, nullable=True)

    templates = relationship("Template", back_populates="creator")
    requests = relationship("Request", back_populates="creator")
