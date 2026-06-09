from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CompanyConfigCreate(BaseModel):
    company_code: str
    fb_database: str
    fb_user: str = "SYSDBA"
    fb_password: str = "masterkey"


class CompanyConfigUpdate(BaseModel):
    fb_database: Optional[str] = None
    fb_user: Optional[str] = None
    fb_password: Optional[str] = None


class CompanyConfigResponse(BaseModel):
    company_code: str
    fb_database: str
    fb_user: str
    fb_password: str
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
