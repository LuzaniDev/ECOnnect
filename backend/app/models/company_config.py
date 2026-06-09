from datetime import datetime
from sqlalchemy import Column, String, DateTime
from ..database import Base


class CompanyConfig(Base):
    __tablename__ = "company_configs"

    company_code = Column(String(20), primary_key=True)
    fb_database = Column(String(500), nullable=False, default="C:/ecosis/dados/ecodados.eco")
    fb_user = Column(String(50), nullable=False, default="SYSDBA")
    fb_password = Column(String(100), nullable=False, default="masterkey")
    updated_at = Column(DateTime, default=datetime.utcnow)
