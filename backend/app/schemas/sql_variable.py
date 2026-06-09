from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class SqlVariableCreate(BaseModel):
    name: str
    label: Optional[str] = None
    sql_query: str
    value_column: Optional[int] = None
    company_code: str


class SqlVariableUpdate(BaseModel):
    name: Optional[str] = None
    label: Optional[str] = None
    sql_query: Optional[str] = None
    value_column: Optional[int] = None


class SqlVariableResponse(BaseModel):
    id: UUID
    name: str
    label: Optional[str] = None
    sql_query: str
    value_column: Optional[int] = None
    company_code: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SqlVariableListResponse(BaseModel):
    id: UUID
    name: str
    label: Optional[str] = None
    sql_query: str
    value_column: Optional[int] = None
    company_code: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
