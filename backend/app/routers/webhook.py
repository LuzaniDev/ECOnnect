from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..services import meta_service

router = APIRouter(prefix="/webhook", tags=["webhook"])

VERIFY_TOKEN = "econnect_meta_webhook_2024"


@router.get("/meta")
async def verify_webhook(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge) if hub_challenge and hub_challenge.isdigit() else hub_challenge
    return {"error": "Token de verificação inválido"}


@router.post("/meta")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    entries = body.get("entry", [])
    for entry in entries:
        await meta_service.process_webhook_entry(entry, db)
    return {"status": "ok"}
