from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..models.request import Request, RequestParameterValue
from ..models.template import Template
from ..models.user import User
from ..models.integration import IntegrationConfig
from ..schemas.request import RequestCreate


class RequestService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: RequestCreate, user_id: UUID) -> Request:
        template = await self.db.execute(
            select(Template).where(Template.id == data.template_id)
        )
        template = template.scalar_one_or_none()
        if not template:
            raise ValueError("Template não encontrado")

        user = await self.db.execute(select(User).where(User.id == user_id))
        user = user.scalar_one_or_none()
        if not user:
            raise ValueError("Usuário não encontrado")

        if data.tag == "cobrança":
            await self._check_cobranca_cooldown(data.client_phone, user_id, user.cobranca_cooldown_hours)

        request = Request(
            template_id=data.template_id,
            client_phone=data.client_phone,
            tag=data.tag,
            link=data.link,
            status="pending",
            created_by=user_id,
        )
        self.db.add(request)
        await self.db.flush()

        sorted_params = sorted(data.parameter_values.items(), key=lambda x: int(x[0]))
        for order_str, value in sorted_params:
            order = int(order_str)
            param_value = RequestParameterValue(
                request_id=request.id,
                param_order=order,
                param_label=order_str,
                value=value,
            )
            self.db.add(param_value)

        await self.db.commit()

        result = await self.db.execute(
            select(Request)
            .where(Request.id == request.id)
            .options(
                selectinload(Request.parameter_values),
                selectinload(Request.template),
                selectinload(Request.creator),
            )
        )
        return result.scalar_one()

    async def _check_cobranca_cooldown(self, phone: str, user_id: UUID, cooldown_hours: int):
        now_naive = datetime.utcnow()
        cutoff = now_naive - timedelta(hours=cooldown_hours)
        query = select(Request).where(
            and_(
                Request.client_phone == phone,
                Request.created_by == user_id,
                Request.tag == "cobrança",
                Request.created_at >= cutoff,
                Request.status != "cancelled",
            )
        ).order_by(Request.created_at.desc()).limit(1)
        result = await self.db.execute(query)
        last = result.scalar_one_or_none()
        if last:
            remaining = cooldown_hours - (now_naive - last.created_at).total_seconds() / 3600
            raise ValueError(
                f"Cooldown de cobrança ativo. Aguarde {remaining:.1f}h antes de enviar "
                f"nova cobrança para este número."
            )

    async def list_all(
        self, status: str = None, user_id: UUID = None, is_admin: bool = False,
        eco_empresa: str | None = None,
    ) -> list[Request]:
        query = (
            select(Request)
            .options(
                selectinload(Request.parameter_values),
                selectinload(Request.template),
                selectinload(Request.creator),
            )
            .order_by(Request.created_at.desc())
        )

        if not is_admin and user_id:
            query = query.where(Request.created_by == user_id)
        if status:
            query = query.where(Request.status == status)
        if eco_empresa and is_admin:
            query = query.join(Request.creator).where(User.eco_empresa == eco_empresa)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, request_id: UUID) -> Request | None:
        query = (
            select(Request)
            .where(Request.id == request_id)
            .options(
                selectinload(Request.parameter_values),
                selectinload(Request.template),
                selectinload(Request.creator),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_status(self, request_id: UUID, status: str) -> Request | None:
        request = await self.get_by_id(request_id)
        if not request:
            return None
        request.status = status
        await self.db.commit()
        await self.db.refresh(request)

        if status == "sent":
            try:
                await self._trigger_integration(request)
            except Exception:
                pass

        return request

    async def _trigger_integration(self, request: Request):
        query = select(IntegrationConfig).where(
            IntegrationConfig.template_id == request.template_id,
            IntegrationConfig.is_active == True,
        )
        result = await self.db.execute(query)
        config = result.scalar_one_or_none()
        if not config:
            return

        from ..services.integration_service import IntegrationService
        service = IntegrationService(self.db)
        try:
            await service.send_to_mundobots(config, request)
        except Exception as e:
            print(f"[Integration] Mundo dos Bots error: {e}")

    async def update_link(self, request_id: UUID, link: str | None) -> Request | None:
        request = await self.get_by_id(request_id)
        if not request:
            return None
        request.link = link
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def get_history_by_phone(self, phone: str) -> list[Request]:
        query = (
            select(Request)
            .where(Request.client_phone == phone)
            .options(
                selectinload(Request.parameter_values),
                selectinload(Request.template),
                selectinload(Request.creator),
            )
            .order_by(Request.created_at.desc())
            .limit(50)
        )
        result = await self.db.execute(query)
        return result.scalars().all()
