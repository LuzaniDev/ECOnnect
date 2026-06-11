from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.request import Request
from ..models.user import User


class CobrancaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_sent_status(self, phones: list[str], user_id: UUID) -> dict:
        result = {}
        now = datetime.utcnow()

        user = await self.db.execute(select(User).where(User.id == user_id))
        user = user.scalar_one_or_none()
        cooldown = user.cobranca_cooldown_hours if user else 48

        for phone in phones:
            query = select(Request).where(
                and_(
                    Request.client_phone == phone,
                    Request.tag == "cobrança",
                    Request.status.in_(["sent", "pending"]),
                )
            ).order_by(Request.created_at.desc()).limit(1)

            row = await self.db.execute(query)
            last = row.scalar_one_or_none()

            if last:
                hours_since = (now - last.created_at).total_seconds() / 3600
                remaining = max(0, cooldown - hours_since)
                result[phone] = {
                    "sent": True,
                    "remaining_hours": round(remaining, 1),
                    "last_sent_at": last.created_at.isoformat() if last.created_at else None,
                }
            else:
                result[phone] = {
                    "sent": False,
                    "remaining_hours": 0,
                    "last_sent_at": None,
                }

        return result
