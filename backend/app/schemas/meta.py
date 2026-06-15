from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class MetaCredentialsCreate(BaseModel):
    waba_id: str
    phone_number_id: str
    access_token: str


class MetaCredentialsUpdate(BaseModel):
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    access_token: Optional[str] = None


class MetaCredentialsResponse(BaseModel):
    id: UUID
    eco_empresa: Optional[str]
    waba_id: str
    phone_number_id: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class MetaVerifyRequest(BaseModel):
    waba_id: str
    phone_number_id: str
    access_token: str


class MetaVerifyResponse(BaseModel):
    verified: bool
    message: str


class MetaTemplateSyncRequest(BaseModel):
    template_id: UUID


class MetaTemplateSyncResponse(BaseModel):
    meta_template_id: Optional[str]
    meta_status: Optional[str]
    success: bool
    message: str


class MetaSendRequest(BaseModel):
    template_id: UUID
    client_phone: str
    parameter_values: dict[str, str]


class MetaSendResponse(BaseModel):
    success: bool
    message_id: Optional[str]
    message: str


class MetaMessageResponse(BaseModel):
    id: UUID
    from_phone: str
    to_phone: str
    direction: str
    template_name: Optional[str]
    body: Optional[str]
    status: str
    created_at: datetime
