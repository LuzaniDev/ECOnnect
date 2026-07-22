import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, Date
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from ..database import Base


class BillingTemplate(Base):
    __tablename__ = "billing_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    method = Column(String(10), nullable=False, default="POST")
    url = Column(String(500), nullable=False)
    headers = Column(JSON, nullable=True)
    body = Column(Text, nullable=True)
    tag = Column(String(100), nullable=True)
    api_token = Column(String(255), nullable=False)
    flow_id = Column(String(50), nullable=False, default="")
    offset_days = Column(Integer, nullable=False, default=0)
    send_time = Column(String(5), nullable=False, default="09:00")
    eco_empresa = Column(String(20), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User")


class ClientBillingConfig(Base):
    __tablename__ = "client_billing_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_code = Column(String(20), nullable=False)
    client_name = Column(String(200), nullable=False)
    client_phone = Column(String(20), nullable=False)
    eco_empresa = Column(String(20), nullable=False, index=True)

    billing_template_id = Column(UUID(as_uuid=True), ForeignKey("billing_templates.id"), nullable=True)

    template_name = Column(String(100), nullable=False)
    template_method = Column(String(10), nullable=False, default="POST")
    template_url = Column(String(500), nullable=False)
    template_headers = Column(JSON, nullable=True)
    template_body = Column(Text, nullable=True)
    template_tag = Column(String(100), nullable=True)

    api_token = Column(String(255), nullable=False)
    flow_id = Column(String(50), nullable=False, default="")

    offset_days = Column(Integer, nullable=False, default=0)
    send_time = Column(String(5), nullable=False, default="09:00")

    is_active = Column(Boolean, default=True)
    last_pendencia_vencimento = Column(Date, nullable=True)
    last_sent_at = Column(DateTime, nullable=True)
    next_check_date = Column(Date, nullable=True)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User")
    billing_template = relationship("BillingTemplate", foreign_keys=[billing_template_id])


class BillingGroup(Base):
    __tablename__ = "billing_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    eco_empresa = Column(String(20), nullable=False, index=True)

    billing_template_id = Column(UUID(as_uuid=True), ForeignKey("billing_templates.id"), nullable=True)

    template_name = Column(String(100), nullable=False)
    template_method = Column(String(10), nullable=False, default="POST")
    template_url = Column(String(500), nullable=False)
    template_headers = Column(JSON, nullable=True)
    template_body = Column(Text, nullable=True)
    template_tag = Column(String(100), nullable=True)

    api_token = Column(String(255), nullable=False)
    flow_id = Column(String(50), nullable=False, default="")

    offset_days = Column(Integer, nullable=False, default=0)
    send_time = Column(String(5), nullable=False, default="09:00")

    status = Column(String(20), nullable=False, default="pending")

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clients = relationship("BillingGroupClient", back_populates="group", cascade="all, delete-orphan")
    creator = relationship("User")
    billing_template = relationship("BillingTemplate", foreign_keys=[billing_template_id])


class BillingGroupClient(Base):
    __tablename__ = "billing_group_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("billing_groups.id", ondelete="CASCADE"), nullable=False)
    client_code = Column(String(20), nullable=False)
    client_name = Column(String(200), nullable=False)
    client_phone = Column(String(20), nullable=False)
    config_id = Column(UUID(as_uuid=True), ForeignKey("client_billing_configs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("BillingGroup", back_populates="clients")
    config = relationship("ClientBillingConfig", foreign_keys=[config_id])
