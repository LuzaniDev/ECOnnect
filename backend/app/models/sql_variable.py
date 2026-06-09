import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


class SqlVariable(Base):
    __tablename__ = "sql_variables"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    label = Column(String(200), nullable=True)
    sql_query = Column(Text, nullable=False)
    value_column = Column(Integer, nullable=True)
    company_code = Column(String(20), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
