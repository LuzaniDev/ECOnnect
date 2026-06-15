import json
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models.user import User
from ..models.integration import IntegrationConfig
from ..schemas.integration import (
    IntegrationConfigCreate,
    IntegrationConfigUpdate,
    IntegrationConfigResponse,
    TriggerRequest,
)
from ..services.integration_service import IntegrationService, compute_next_run
from ..services.audit_service import log_action

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _build_response(config: IntegrationConfig) -> dict:
    return {
        "id": config.id,
        "template_id": config.template_id,
        "template_name": config.template.name if config.template else "",
        "name": config.name or "Manual",
        "created_by": config.created_by,
        "created_by_username": config.creator.username if config.creator else "",
        "api_url": config.api_url,
        "api_token": config.api_token,
        "flow_id": config.flow_id,
        "field_mapping": config.field_mapping,
        "first_name_field": config.first_name_field or "1",
        "manual_payload": config.manual_payload,
        "manual_headers": config.manual_headers,
        "is_active": config.is_active,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
        "schedule_enabled": config.schedule_enabled,
        "schedule_preset": config.schedule_preset,
        "schedule_days": config.schedule_days,
        "schedule_time": config.schedule_time,
        "last_run_at": config.last_run_at,
        "next_run_at": config.next_run_at,
        "type": config.type or "normal",
    }


@router.get("/", response_model=list[IntegrationConfigResponse])
async def list_integrations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    configs = await service.list_all(eco_empresa=current_user.eco_empresa)
    return [_build_response(c) for c in configs]


@router.get("/template/{template_id}", response_model=IntegrationConfigResponse | None)
async def get_integration_by_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    config = await service.get_by_template(template_id, eco_empresa=current_user.eco_empresa)
    if not config:
        return None
    return _build_response(config)


@router.get("/{config_id}", response_model=IntegrationConfigResponse)
async def get_integration(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    config = await service.get_by_id(config_id, eco_empresa=current_user.eco_empresa)
    if not config:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    return _build_response(config)


async def _reload_config(db: AsyncSession, config_id: UUID) -> IntegrationConfig | None:
    result = await db.execute(
        select(IntegrationConfig)
        .where(IntegrationConfig.id == config_id)
        .options(
            selectinload(IntegrationConfig.template),
            selectinload(IntegrationConfig.creator),
        )
    )
    return result.scalar_one_or_none()


@router.post("/", response_model=IntegrationConfigResponse)
async def create_integration(
    data: IntegrationConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = IntegrationService(db)
    if data.template_id:
        existing = await service.get_by_template(data.template_id, eco_empresa=current_user.eco_empresa)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ja existe uma integracao para este template",
            )
    config = await service.create(data, current_user.id, eco_empresa=current_user.eco_empresa)
    config = await _reload_config(db, config.id)
    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "create_integration", "integration", str(config.id),
                     {"name": config.name, "api_url": config.api_url}, ip)
    return _build_response(config)


@router.put("/{config_id}", response_model=IntegrationConfigResponse)
async def update_integration(
    config_id: UUID,
    data: IntegrationConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = IntegrationService(db)
    existing = await service.get_by_id(config_id, eco_empresa=current_user.eco_empresa)
    if not existing:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    config = await service.update(config_id, data)
    config = await _reload_config(db, config.id)
    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "update_integration", "integration", str(config.id),
                     {"fields": list(data.model_dump(exclude_unset=True).keys())}, ip)
    return _build_response(config)


@router.delete("/{config_id}")
async def delete_integration(
    config_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = IntegrationService(db)
    config_before = await service.get_by_id(config_id, eco_empresa=current_user.eco_empresa)
    if not config_before:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    deleted = await service.delete(config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "delete_integration", "integration", str(config_id),
                     {"name": config_before.name if config_before else None}, ip)
    return {"detail": "Configuracao excluida"}


@router.post("/{config_id}/trigger")
async def trigger_integration(
    config_id: UUID,
    trigger_data: TriggerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    existing = await service.get_by_id(config_id, eco_empresa=current_user.eco_empresa)
    if not existing:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    try:
        result = await service.trigger(
            config_id,
            override_payload=trigger_data.override_payload,
            override_headers=trigger_data.override_headers,
        )
        ip = request.client.host if request.client else None
        await log_action(db, current_user.id, current_user.username,
                         "trigger_integration", "integration", str(config_id),
                         {"result": result}, ip)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{config_id}/trigger-stream")
async def trigger_integration_stream(
    config_id: UUID,
    trigger_data: TriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = IntegrationService(db)
    config = await service.get_by_id(config_id, eco_empresa=current_user.eco_empresa)
    if not config:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    if config.type != "ia":
        raise HTTPException(status_code=400, detail="Streaming suportado apenas para integracoes do tipo IA")
    if not config.is_active:
        raise HTTPException(status_code=400, detail="Integracao esta desativada")

    payload = trigger_data.override_payload or config.manual_payload or ""

    try:
        json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="JSON invalido no corpo da requisicao",
        )

    async def event_stream():
        full_text = ""
        model_name = ""
        total_duration = 0

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                async with client.stream(
                    "POST", config.api_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    resp.raise_for_status()
                    buffer = ""
                    async for chunk in resp.aiter_bytes():
                        buffer += chunk.decode("utf-8")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                ol = json.loads(line)
                                token = ol.get("response", "")
                                done = ol.get("done", False)
                                full_text += token
                                yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                                if done:
                                    model_name = ol.get("model", "")
                                    total_duration = ol.get("total_duration", 0)
                            except json.JSONDecodeError:
                                continue
        except httpx.HTTPError as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            await db.rollback()
            return

        c = await db.get(IntegrationConfig, config_id)
        if c:
            c.last_run_at = datetime.utcnow()
            if c.schedule_enabled and c.schedule_preset:
                c.next_run_at = compute_next_run(
                    c.schedule_preset, c.schedule_days, c.schedule_time or "09:00"
                )
            else:
                c.next_run_at = None
            await db.commit()

        yield (
            f"data: {json.dumps({'done': True, 'full_response': full_text, 'model': model_name, 'total_duration': total_duration})}\n\n"
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
