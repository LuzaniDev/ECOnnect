from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class IntegrationConfigCreate(BaseModel):
    template_id: Optional[UUID] = None
    name: str = "Manual"
    api_token: str
    flow_id: str = ""
    field_mapping: dict[str, str] = {}
    first_name_field: str = "1"
    is_active: bool = True
    type: str = "normal"
    manual_payload: Optional[str] = None
    manual_headers: Optional[dict[str, str]] = None
    schedule_enabled: bool = False
    schedule_preset: Optional[str] = None
    schedule_days: Optional[list[int]] = None
    schedule_time: Optional[str] = "09:00"


class IntegrationConfigUpdate(BaseModel):
    template_id: Optional[UUID] = None
    name: Optional[str] = None
    api_token: Optional[str] = None
    type: Optional[str] = None
    flow_id: Optional[str] = None
    field_mapping: Optional[dict[str, str]] = None
    is_active: Optional[bool] = None
    first_name_field: Optional[str] = None
    api_url: Optional[str] = None
    manual_payload: Optional[str] = None
    manual_headers: Optional[dict[str, str]] = None
    schedule_enabled: Optional[bool] = None
    schedule_preset: Optional[str] = None
    schedule_days: Optional[list[int]] = None
    schedule_time: Optional[str] = None


class TriggerRequest(BaseModel):
    override_payload: Optional[str] = None
    override_headers: Optional[dict[str, str]] = None


class IntegrationConfigResponse(BaseModel):
    id: UUID
    template_id: Optional[UUID] = None
    template_name: str = ""
    name: str = "Manual"
    created_by: UUID
    created_by_username: str = ""
    api_url: str
    api_token: str
    flow_id: str
    field_mapping: dict[str, str] = {}
    is_active: bool
    created_at: datetime
    updated_at: datetime
    eco_empresa: Optional[str] = None
    first_name_field: str = "1"
    manual_payload: Optional[str] = None
    manual_headers: Optional[dict[str, str]] = None
    schedule_enabled: bool = False
    schedule_preset: Optional[str] = None
    schedule_days: Optional[list[int]] = None
    schedule_time: Optional[str] = "09:00"
    type: str = "normal"
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None

    class Config:
        from_attributes = True
