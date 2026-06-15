import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    parameter_count = Column(Integer, nullable=False, default=0)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    eco_empresa = Column(String(20), nullable=True, index=True)

    meta_template_id = Column(String(100), nullable=True)
    meta_status = Column(String(20), nullable=True)

    creator = relationship("User", back_populates="templates")
    requests = relationship("Request", back_populates="template")
