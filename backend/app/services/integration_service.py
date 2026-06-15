import json
import httpx
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..models.integration import IntegrationConfig, CRON_PRESETS
from ..models.request import Request
from ..models.template import Template
from ..models.user import User
from ..schemas.integration import IntegrationConfigCreate, IntegrationConfigUpdate


DEFAULT_API_URL = "https://app.mundodosbots.com.br/api/users"


def compute_next_run(preset: str, days: list[int] | None, time_str: str) -> datetime | None:
    now = datetime.utcnow()
    hour, minute = (int(x) for x in time_str.split(":"))

    if preset == "1h":
        return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    elif preset == "6h":
        next_hour = ((now.hour // 6) + 1) * 6
        if next_hour >= 24:
            next_date = now + timedelta(days=1)
            return next_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    elif preset == "12h":
        next_hour = 12 if now.hour < 12 else 0
        if next_hour == 0:
            next_date = now + timedelta(days=1)
            return next_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return now.replace(hour=12, minute=0, second=0, microsecond=0)
    elif preset == "daily":
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target
    elif preset == "weekly":
        if not days:
            days = [0]
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        current_weekday = now.weekday()
        next_days = [d for d in days if d >= current_weekday]
        if next_days and (next_days[0] > current_weekday or target > now):
            delta = next_days[0] - current_weekday
        else:
            delta = (7 - current_weekday) + days[0]
        target += timedelta(days=delta)
        return target
    elif preset == "biweekly":
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=15)
        return target
    elif preset == "monthly":
        target = now.replace(day=1, hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            if target.month == 12:
                target = target.replace(year=target.year + 1, month=1)
            else:
                target = target.replace(month=target.month + 1)
        return target
    return None


class IntegrationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: IntegrationConfigCreate, user_id: UUID, eco_empresa: str | None = None) -> IntegrationConfig:
        next_run = None
        if data.schedule_enabled and data.schedule_preset:
            days = data.schedule_days if data.schedule_days else None
            next_run = compute_next_run(data.schedule_preset, days, data.schedule_time or "09:00")

        config = IntegrationConfig(
            template_id=data.template_id,
            name=data.name or "Manual",
            created_by=user_id,
            eco_empresa=eco_empresa,
            api_url=DEFAULT_API_URL,
            api_token=data.api_token,
            flow_id=data.flow_id or "",
            field_mapping=data.field_mapping or {},
            first_name_field=data.first_name_field,
            manual_payload=data.manual_payload,
            manual_headers=data.manual_headers,
            schedule_enabled=data.schedule_enabled,
            schedule_preset=data.schedule_preset,
            schedule_days=data.schedule_days or [],
            schedule_time=data.schedule_time or "09:00",
            next_run_at=next_run,
            type=data.type or "normal",
        )
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def list_all(self, eco_empresa: str | None = None) -> list[IntegrationConfig]:
        query = (
            select(IntegrationConfig)
            .options(
                selectinload(IntegrationConfig.template),
                selectinload(IntegrationConfig.creator),
            )
            .order_by(IntegrationConfig.created_at.desc())
        )
        if eco_empresa:
            query = query.where(IntegrationConfig.eco_empresa == eco_empresa)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, config_id: UUID, eco_empresa: str | None = None) -> IntegrationConfig | None:
        query = (
            select(IntegrationConfig)
            .where(IntegrationConfig.id == config_id)
            .options(
                selectinload(IntegrationConfig.template),
                selectinload(IntegrationConfig.creator),
            )
        )
        if eco_empresa:
            query = query.where(IntegrationConfig.eco_empresa == eco_empresa)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_template(self, template_id: UUID, eco_empresa: str | None = None) -> IntegrationConfig | None:
        query = (
            select(IntegrationConfig)
            .where(IntegrationConfig.template_id == template_id, IntegrationConfig.is_active == True)
            .options(
                selectinload(IntegrationConfig.template),
                selectinload(IntegrationConfig.creator),
            )
        )
        if eco_empresa:
            query = query.where(IntegrationConfig.eco_empresa == eco_empresa)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update(self, config_id: UUID, data: IntegrationConfigUpdate) -> IntegrationConfig | None:
        config = await self.get_by_id(config_id)
        if not config:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(config, key, value)

        if data.schedule_enabled and config.schedule_preset:
            config.next_run_at = compute_next_run(
                config.schedule_preset,
                config.schedule_days,
                config.schedule_time or "09:00",
            )
        elif not config.schedule_enabled:
            config.next_run_at = None

        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def delete(self, config_id: UUID) -> bool:
        config = await self.get_by_id(config_id)
        if not config:
            return False
        await self.db.delete(config)
        await self.db.commit()
        return True

    async def trigger(self, config_id: UUID, override_payload: str = None, override_headers: dict[str, str] = None) -> dict:
        config = await self.get_by_id(config_id)
        if not config:
            raise ValueError("Configuracao nao encontrada")
        if not config.is_active:
            raise ValueError("Integracao esta desativada")

        if config.type == "cobranca" and config.last_run_at:
            cooldown = config.creator.cobranca_cooldown_hours if config.creator else 0
            if cooldown > 0:
                elapsed = (datetime.utcnow() - config.last_run_at).total_seconds() / 3600
                if elapsed < cooldown:
                    remaining = cooldown - elapsed
                    raise ValueError(
                        f"Cooldown de cobrança ativo. Aguarde {remaining:.1f}h "
                        f"antes de executar novamente esta integração."
                    )

        if config.template_id:
            result = await self.db.execute(
                select(Request)
                .where(
                    and_(
                        Request.template_id == config.template_id,
                        Request.status == "pending",
                    )
                )
                .options(selectinload(Request.parameter_values))
                .order_by(Request.created_at.asc())
                .limit(10)
            )
            pending = result.scalars().all()

            if not pending:
                return {"sent": 0, "message": "Nenhuma requisicao pendente para este template"}

            sent_count = 0
            for request in pending:
                try:
                    await self.send_to_mundobots(config, request)
                    request.status = "sent"
                    sent_count += 1
                except Exception as e:
                    print(f"[Integration] Falha ao enviar request {request.id}: {e}")

            await self.db.commit()
            result_msg = {"sent": sent_count, "total": len(pending)}
        elif config.type == "ia":
            payload = override_payload if override_payload is not None else (config.manual_payload or "")

            try:
                json.loads(payload)
            except json.JSONDecodeError:
                raise ValueError(
                    "JSON invalido no corpo da requisicao. "
                    "Verifique se todas as chaves e valores estao formatados corretamente "
                    '(exemplo: use "{{var}}" em vez de {{var}}).'
                )

            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    config.api_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()

            result_msg = {
                "ai_response": result.get("response", ""),
                "model": result.get("model", ""),
                "total_duration": result.get("total_duration", 0),
                "done": result.get("done", True),
            }
        elif config.type == "n8n":
            payload = override_payload if override_payload is not None else (config.manual_payload or "")
            headers = override_headers if override_headers is not None else dict(config.manual_headers or {})
            headers.setdefault("Content-Type", "application/json")

            try:
                json.loads(payload)
            except json.JSONDecodeError:
                raise ValueError(
                    "JSON invalido no corpo da requisicao. "
                    "Verifique se todas as chaves e valores estao formatados corretamente "
                    '(exemplo: use "{{var}}" em vez de {{var}}).'
                )

            async with httpx.AsyncClient(timeout=1200) as client:
                response = await client.post(
                    config.api_url,
                    data=payload,
                    headers=headers,
                )
                response.raise_for_status()

            result_msg = {"sent": 1, "total": 1, "response": response.json()}
        else:
            payload = override_payload if override_payload is not None else (config.manual_payload or "")
            headers = override_headers if override_headers is not None else dict(config.manual_headers or {})
            headers.setdefault("X-ACCESS-TOKEN", config.api_token)
            headers.setdefault("accept", "application/json")
            headers.setdefault("Content-Type", "application/json")

            try:
                json.loads(payload)
            except json.JSONDecodeError:
                raise ValueError(
                    "JSON invalido no corpo da requisicao. "
                    "Verifique se todas as chaves e valores estao formatados corretamente "
                    "(exemplo: use \"{{var}}\" em vez de {{var}})."
                )

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    config.api_url,
                    data=payload,
                    headers=headers,
                )
                response.raise_for_status()

            result_msg = {"sent": 1, "total": 1, "response": response.json()}

        config.last_run_at = datetime.utcnow()
        if config.schedule_enabled and config.schedule_preset:
            config.next_run_at = compute_next_run(
                config.schedule_preset,
                config.schedule_days,
                config.schedule_time or "09:00",
            )
        else:
            config.next_run_at = None
        await self.db.commit()

        return result_msg

    async def get_due(self, eco_empresa: str | None = None) -> list[IntegrationConfig]:
        now = datetime.utcnow()
        query = (
            select(IntegrationConfig)
            .where(
                and_(
                    IntegrationConfig.schedule_enabled == True,
                    IntegrationConfig.is_active == True,
                    IntegrationConfig.next_run_at <= now,
                )
            )
            .options(
                selectinload(IntegrationConfig.template),
                selectinload(IntegrationConfig.creator),
            )
        )
        if eco_empresa:
            query = query.where(IntegrationConfig.eco_empresa == eco_empresa)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def send_to_mundobots(self, config: IntegrationConfig, request: Request) -> dict:
        params = {pv.param_label: pv.value for pv in (request.parameter_values or [])}
        payload = {
            "phone": request.client_phone,
            "first_name": params.get(config.first_name_field or "1", ""),
            "actions": [],
        }

        field_mapping = config.field_mapping or {}
        for param_order, field_name in field_mapping.items():
            value = params.get(param_order, "")
            if value:
                payload["actions"].append({
                    "action": "set_field_value",
                    "field_name": field_name,
                    "value": value,
                })

        payload["actions"].append({
            "action": "send_flow",
            "flow_id": int(config.flow_id),
        })

        headers = {
            "accept": "application/json",
            "X-ACCESS-TOKEN": config.api_token,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                config.api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
