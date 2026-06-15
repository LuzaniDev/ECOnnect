import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


class MetaMessage(Base):
    __tablename__ = "meta_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    eco_empresa = Column(String(20), nullable=True, index=True)
    from_phone = Column(String(20), nullable=False)
    to_phone = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)
    template_name = Column(String(100), nullable=True)
    body = Column(Text, nullable=True)
    meta_message_id = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="sent")
    created_at = Column(DateTime, default=datetime.utcnow)
