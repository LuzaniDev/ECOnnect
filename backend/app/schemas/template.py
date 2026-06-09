from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=100)
    body: str
    description: Optional[str] = None
    parameter_count: int = Field(default=0, ge=0)


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    body: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    parameter_count: Optional[int] = None


class TemplateParameterBrief(BaseModel):
    order: int


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    body: str
    description: Optional[str] = None
    parameter_count: int = 0
    eco_empresa: Optional[str] = None
    created_by: UUID
    creator_username: str = ""
    is_active: bool
    created_at: datetime
    updated_at: datetime
    parameters: list[TemplateParameterBrief] = []

    class Config:
        from_attributes = True
