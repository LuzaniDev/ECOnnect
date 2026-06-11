from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..services.cobranca_service import CobrancaService

router = APIRouter(prefix="/api/cobranca", tags=["cobranca"])


class CheckSentRequest(BaseModel):
    phones: list[str]


class CheckSentResponse(BaseModel):
    results: dict


@router.post("/check-sent", response_model=CheckSentResponse)
async def check_sent(
    data: CheckSentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CobrancaService(db)
    results = await service.check_sent_status(data.phones, current_user.id)
    return CheckSentResponse(results=results)
