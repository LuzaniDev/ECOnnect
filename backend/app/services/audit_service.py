from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    user_id: UUID | None,
    username: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
):
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.commit()
