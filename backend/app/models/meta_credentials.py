import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


class MetaCredentials(Base):
    __tablename__ = "meta_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    eco_empresa = Column(String(20), nullable=True, index=True, unique=True)
    waba_id = Column(String(100), nullable=False)
    phone_number_id = Column(String(100), nullable=False)
    access_token = Column(Text, nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
