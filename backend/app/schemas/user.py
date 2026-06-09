from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    role: str
    is_active: bool
    cobranca_cooldown_hours: int = 48
    created_at: datetime
    eco_usuario: str | None = None
    eco_empresa: str | None = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None
    cobranca_cooldown_hours: int | None = None
