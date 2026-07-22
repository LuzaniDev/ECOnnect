from datetime import datetime, date
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class BillingTemplateCreate(BaseModel):
    name: str
    method: str = "POST"
    url: str
    headers: Optional[list] = None
    body: Optional[str] = None
    tag: Optional[str] = None
    api_token: str
    flow_id: str = ""
    offset_days: int = 0
    send_time: str = "09:00"


class BillingTemplateUpdate(BaseModel):
    name: Optional[str] = None
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[list] = None
    body: Optional[str] = None
    tag: Optional[str] = None
    api_token: Optional[str] = None
    flow_id: Optional[str] = None
    offset_days: Optional[int] = None
    send_time: Optional[str] = None


class BillingTemplateResponse(BaseModel):
    id: UUID
    name: str
    method: str
    url: str
    headers: Optional[list] = None
    body: Optional[str] = None
    tag: Optional[str] = None
    api_token: str
    flow_id: str
    offset_days: int
    send_time: str
    eco_empresa: Optional[str] = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientBillingConfigCreate(BaseModel):
    client_code: str
    client_name: str
    client_phone: str
    billing_template_id: Optional[UUID] = None

    template_name: str
    template_method: str = "POST"
    template_url: str
    template_headers: Optional[list] = None
    template_body: Optional[str] = None
    template_tag: Optional[str] = None

    api_token: str
    flow_id: str = ""

    offset_days: int = 0
    send_time: str = "09:00"


class GroupClientCreate(BaseModel):
    client_code: str
    client_name: str
    client_phone: str


class BillingGroupCreate(BaseModel):
    name: str
    billing_template_id: Optional[UUID] = None
    template_name: str
    template_method: str = "POST"
    template_url: str
    template_headers: Optional[list] = None
    template_body: Optional[str] = None
    template_tag: Optional[str] = None
    api_token: str
    flow_id: str = ""
    offset_days: int = 0
    send_time: str = "09:00"
    clients: list[GroupClientCreate] = []


class BillingGroupUpdate(BaseModel):
    name: Optional[str] = None
    billing_template_id: Optional[UUID] = None
    template_name: Optional[str] = None
    template_method: Optional[str] = None
    template_url: Optional[str] = None
    template_headers: Optional[list] = None
    template_body: Optional[str] = None
    template_tag: Optional[str] = None
    api_token: Optional[str] = None
    flow_id: Optional[str] = None
    offset_days: Optional[int] = None
    send_time: Optional[str] = None
    status: Optional[str] = None
    clients: Optional[list[GroupClientCreate]] = None


class GroupClientResponse(BaseModel):
    id: UUID
    client_code: str
    client_name: str
    client_phone: str
    config_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BillingGroupResponse(BaseModel):
    id: UUID
    name: str
    eco_empresa: Optional[str] = None
    billing_template_id: Optional[UUID] = None
    template_name: str
    template_method: str
    template_url: str
    template_headers: Optional[list] = None
    template_body: Optional[str] = None
    template_tag: Optional[str] = None
    api_token: str
    flow_id: str
    offset_days: int
    send_time: str
    status: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    clients: list[GroupClientResponse] = []

    class Config:
        from_attributes = True


class ClientBillingConfigUpdate(BaseModel):
    offset_days: Optional[int] = None
    send_time: Optional[str] = None
    billing_template_id: Optional[UUID] = None
    template_name: Optional[str] = None
    template_method: Optional[str] = None
    template_url: Optional[str] = None
    template_headers: Optional[list] = None
    template_body: Optional[str] = None
    template_tag: Optional[str] = None
    api_token: Optional[str] = None
    flow_id: Optional[str] = None
    is_active: Optional[bool] = None


class ClientBillingConfigResponse(BaseModel):
    id: UUID
    client_code: str
    client_name: str
    client_phone: str
    eco_empresa: Optional[str] = None
    billing_template_id: Optional[UUID] = None

    template_name: str
    template_method: str
    template_url: str
    template_headers: Optional[list] = None
    template_body: Optional[str] = None
    template_tag: Optional[str] = None

    api_token: str
    flow_id: str

    offset_days: int
    send_time: str

    is_active: bool
    last_pendencia_vencimento: Optional[date] = None
    last_sent_at: Optional[datetime] = None
    next_check_date: Optional[date] = None

    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
