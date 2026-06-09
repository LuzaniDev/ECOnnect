import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base


class Request(Base):
    __tablename__ = "requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
    client_phone = Column(String(20), nullable=False)
    tag = Column(String(30), nullable=True)
    link = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = relationship("Template", back_populates="requests")
    creator = relationship("User", back_populates="requests")
    parameter_values = relationship(
        "RequestParameterValue",
        back_populates="request",
        cascade="all, delete-orphan",
    )


class RequestParameterValue(Base):
    __tablename__ = "request_parameter_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    param_order = Column(Integer, nullable=False)
    param_label = Column(String(100), nullable=False)
    value = Column(Text, nullable=False)

    request = relationship("Request", back_populates="parameter_values")
