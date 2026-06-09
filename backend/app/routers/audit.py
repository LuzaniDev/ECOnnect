from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.audit_log import AuditLog

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
async def list_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(AuditLog)
        .options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "username": log.username,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
