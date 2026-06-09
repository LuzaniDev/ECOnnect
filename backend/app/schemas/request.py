from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class RequestCreate(BaseModel):
    template_id: UUID
    client_phone: str
    tag: Optional[str] = None
    link: Optional[str] = None
    parameter_values: dict[str, str]


class RequestParameterValueResponse(BaseModel):
    id: UUID
    param_order: int
    param_label: str
    value: str

    class Config:
        from_attributes = True


class RequestResponse(BaseModel):
    id: UUID
    template_id: UUID
    template_name: str
    client_phone: str
    tag: Optional[str] = None
    link: Optional[str] = None
    status: str
    created_by: UUID
    created_by_username: str
    created_at: datetime
    updated_at: datetime
    parameter_values: list[RequestParameterValueResponse] = []

    class Config:
        from_attributes = True


class RequestUpdate(BaseModel):
    status: Optional[str] = None


class RequestLinkUpdate(BaseModel):
    link: Optional[str] = None
