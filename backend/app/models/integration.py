import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from ..database import Base


CRON_PRESETS = {
    "1h": "0 * * * *",
    "6h": "0 */6 * * *",
    "12h": "0 */12 * * *",
    "daily": "0 9 * * *",
    "weekly": "0 9 * * 1",
    "biweekly": "0 9 1,15 * *",
    "monthly": "0 9 1 * *",
}


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), default="Manual")
    api_url = Column(String(255), nullable=False, default="https://app.mundodosbots.com.br/api/users")
    api_token = Column(String(255), nullable=False)
    flow_id = Column(String(50), nullable=False, default="")
    field_mapping = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    first_name_field = Column(String(10), default="1")
    manual_payload = Column(Text, nullable=True)
    manual_headers = Column(JSON, nullable=True)
    schedule_enabled = Column(Boolean, default=False)
    schedule_preset = Column(String(20), nullable=True)
    schedule_days = Column(JSON, nullable=True, default=list)
    schedule_time = Column(String(5), nullable=True, default="09:00")
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    type = Column(String(20), nullable=False, default="normal")

    eco_empresa = Column(String(20), nullable=True, index=True)

    template = relationship("Template")
    creator = relationship("User")
