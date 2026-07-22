import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime
from ..database import get_db, async_session
from ..deps import get_current_user, require_admin
from ..models.user import User
from ..models.client_billing import BillingGroup, BillingGroupClient, ClientBillingConfig, BillingTemplate
from ..schemas.client_billing import (
    BillingGroupCreate, BillingGroupUpdate, BillingGroupResponse,
    GroupClientCreate, GroupClientResponse,
)
import logging
from ..services.audit_service import log_action
from ..services.client_billing_service import ClientBillingService

logger = logging.getLogger("billing_groups")

router = APIRouter(prefix="/api/billing-groups", tags=["billing-groups"])


def _build_client_response(c) -> dict:
    return {
        "id": c.id,
        "client_code": c.client_code,
        "client_name": c.client_name,
        "client_phone": c.client_phone,
        "config_id": c.config_id,
        "next_check_date": str(c.config.next_check_date) if c.config and c.config.next_check_date else None,
        "created_at": c.created_at,
    }


def _build_group_response(g) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "eco_empresa": g.eco_empresa,
        "billing_template_id": g.billing_template_id,
        "template_name": g.template_name,
        "template_method": g.template_method,
        "template_url": g.template_url,
        "template_headers": g.template_headers,
        "template_body": g.template_body,
        "template_tag": g.template_tag,
        "api_token": g.api_token,
        "flow_id": g.flow_id,
        "offset_days": g.offset_days,
        "send_time": g.send_time,
        "status": g.status,
        "created_by": g.created_by,
        "created_at": g.created_at,
        "updated_at": g.updated_at,
        "clients": [_build_client_response(c) for c in g.clients],
    }


@router.get("", response_model=list[BillingGroupResponse])
async def list_groups(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    empresa = current_user.eco_empresa or "01"
    query = (
        select(BillingGroup)
        .options(selectinload(BillingGroup.clients).selectinload(BillingGroupClient.config))
        .where(BillingGroup.eco_empresa == empresa)
        .order_by(BillingGroup.created_at.desc())
    )
    if status:
        query = query.where(BillingGroup.status == status)
    result = await db.execute(query)
    groups = result.scalars().all()
    return [_build_group_response(g) for g in groups]


@router.get("/{group_id}", response_model=BillingGroupResponse)
async def get_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(BillingGroup)
        .options(selectinload(BillingGroup.clients).selectinload(BillingGroupClient.config))
        .where(BillingGroup.id == group_id)
    )
    result = await db.execute(query)
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo nao encontrado")
    return _build_group_response(g)


@router.post("", response_model=BillingGroupResponse)
async def create_group(
    data: BillingGroupCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    eco_empresa = current_user.eco_empresa or "01"
    billing_template_id = data.billing_template_id

    if billing_template_id:
        tpl_result = await db.execute(
            select(BillingTemplate).where(BillingTemplate.id == billing_template_id)
        )
        tpl = tpl_result.scalar_one_or_none()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template nao encontrado")
        group = BillingGroup(
            name=data.name,
            eco_empresa=eco_empresa,
            billing_template_id=billing_template_id,
            template_name=tpl.name,
            template_method=tpl.method,
            template_url=tpl.url,
            template_headers=tpl.headers,
            template_body=tpl.body,
            template_tag=tpl.tag,
            api_token=tpl.api_token,
            flow_id=tpl.flow_id,
            offset_days=tpl.offset_days,
            send_time=tpl.send_time,
            status="pending",
            created_by=current_user.id,
        )
    else:
        group = BillingGroup(
            name=data.name,
            eco_empresa=eco_empresa,
            template_name=data.template_name,
            template_method=data.template_method,
            template_url=data.template_url,
            template_headers=data.template_headers,
            template_body=data.template_body,
            template_tag=data.template_tag,
            api_token=data.api_token,
            flow_id=data.flow_id,
            offset_days=data.offset_days,
            send_time=data.send_time,
            status="pending",
            created_by=current_user.id,
        )
    db.add(group)
    await db.flush()

    for c in data.clients:
        client = BillingGroupClient(
            group_id=group.id,
            client_code=c.client_code,
            client_name=c.client_name,
            client_phone=c.client_phone,
        )
        db.add(client)

    await db.commit()
    await db.refresh(group)

    query = (
        select(BillingGroup)
        .options(selectinload(BillingGroup.clients).selectinload(BillingGroupClient.config))
        .where(BillingGroup.id == group.id)
    )
    result = await db.execute(query)
    group = result.scalar_one()

    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "create_billing_group", "billing_group", str(group.id),
                     {"name": group.name, "clients": len(data.clients)}, ip)
    return _build_group_response(group)


@router.put("/{group_id}", response_model=BillingGroupResponse)
async def update_group(
    group_id: UUID,
    data: BillingGroupUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = (
        select(BillingGroup)
        .options(selectinload(BillingGroup.clients).selectinload(BillingGroupClient.config))
        .where(BillingGroup.id == group_id)
    )
    result = await db.execute(query)
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo nao encontrado")
    if current_user.eco_empresa and g.eco_empresa != current_user.eco_empresa:
        raise HTTPException(status_code=403, detail="Acesso negado")

    update_data = data.model_dump(exclude_unset=True)
    clients_data = update_data.pop("clients", None)

    TEMPLATE_FIELDS = [
        "template_name", "template_method", "template_url",
        "template_headers", "template_body", "template_tag",
        "api_token", "flow_id", "offset_days", "send_time",
    ]

    billing_template_id = update_data.pop("billing_template_id", None)
    if billing_template_id is not None:
        tpl_result = await db.execute(
            select(BillingTemplate).where(BillingTemplate.id == billing_template_id)
        )
        tpl = tpl_result.scalar_one_or_none()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template nao encontrado")
        g.billing_template_id = billing_template_id
        g.template_name = tpl.name
        g.template_method = tpl.method
        g.template_url = tpl.url
        g.template_headers = tpl.headers
        g.template_body = tpl.body
        g.template_tag = tpl.tag
        g.api_token = tpl.api_token
        g.flow_id = tpl.flow_id
        g.offset_days = tpl.offset_days
        g.send_time = tpl.send_time
        template_fields_updated = TEMPLATE_FIELDS[:]
    else:
        for key, value in update_data.items():
            setattr(g, key, value)
        template_fields_updated = [f for f in TEMPLATE_FIELDS if f in update_data]

    g.updated_at = datetime.utcnow()

    if template_fields_updated:
        for client in g.clients:
            if client.config:
                for f in template_fields_updated:
                    setattr(client.config, f, getattr(g, f))
                if billing_template_id is not None:
                    client.config.billing_template_id = billing_template_id
                client.config.updated_at = datetime.utcnow()

    if clients_data is not None:
        existing_result = await db.execute(
            select(BillingGroupClient).where(BillingGroupClient.group_id == group_id)
        )
        existing_clients = {c.client_code: c for c in existing_result.scalars().all()}

        incoming_codes = set()
        for c in clients_data:
            client_code = c["client_code"] if isinstance(c, dict) else c.client_code
            client_name = c["client_name"] if isinstance(c, dict) else c.client_name
            client_phone = c["client_phone"] if isinstance(c, dict) else c.client_phone
            incoming_codes.add(client_code)

            if client_code in existing_clients:
                old = existing_clients[client_code]
                name_changed = old.client_name != client_name
                phone_changed = old.client_phone != client_phone
                if name_changed or phone_changed:
                    service = ClientBillingService(db)
                    await service.sync_client_to_firebird(client_code, client_name, client_phone, g.eco_empresa or "01")
                old.client_name = client_name
                old.client_phone = client_phone
                old.config_id = old.config_id
            else:
                new_client = BillingGroupClient(
                    group_id=group_id,
                    client_code=client_code,
                    client_name=client_name,
                    client_phone=client_phone,
                )
                db.add(new_client)

        for code, old_client in existing_clients.items():
            if code not in incoming_codes:
                await db.delete(old_client)

    await db.commit()

    query = (
        select(BillingGroup)
        .options(selectinload(BillingGroup.clients).selectinload(BillingGroupClient.config))
        .where(BillingGroup.id == group_id)
    )
    result = await db.execute(query)
    g = result.scalar_one()

    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "update_billing_group", "billing_group", str(group_id),
                     {"fields": list(update_data.keys())}, ip)
    return _build_group_response(g)


@router.delete("/{group_id}")
async def delete_group(
    group_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = (
        select(BillingGroup)
        .options(selectinload(BillingGroup.clients).selectinload(BillingGroupClient.config))
        .where(BillingGroup.id == group_id)
    )
    result = await db.execute(query)
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo nao encontrado")
    if current_user.eco_empresa and g.eco_empresa != current_user.eco_empresa:
        raise HTTPException(status_code=403, detail="Acesso negado")

    await db.delete(g)
    await db.commit()

    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "delete_billing_group", "billing_group", str(group_id),
                     {"name": g.name}, ip)
    return {"detail": "Grupo excluido"}


@router.post("/{group_id}/register")
async def register_group(
    group_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = (
        select(BillingGroup)
        .options(selectinload(BillingGroup.clients).selectinload(BillingGroupClient.config))
        .where(BillingGroup.id == group_id)
    )
    result = await db.execute(query)
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo nao encontrado")
    if not g.clients:
        raise HTTPException(status_code=400, detail="Grupo sem clientes")

    errors = []
    success_count = 0
    skipped_count = 0
    for client in g.clients:
        if client.config_id:
            skipped_count += 1
            continue
        try:
            config = ClientBillingConfig(
                client_code=client.client_code,
                client_name=client.client_name,
                client_phone=client.client_phone,
                eco_empresa=g.eco_empresa,
                billing_template_id=g.billing_template_id,
                template_name=g.template_name,
                template_method=g.template_method,
                template_url=g.template_url,
                template_headers=g.template_headers,
                template_body=g.template_body,
                template_tag=g.template_tag,
                api_token=g.api_token,
                flow_id=g.flow_id,
                offset_days=g.offset_days,
                send_time=g.send_time,
                created_by=current_user.id,
            )
            db.add(config)
            await db.flush()
            client.config_id = config.id
            await db.flush()
            success_count += 1
        except Exception as e:
            logger.warning("Erro ao criar config para %s: %s", client.client_name, e)
            errors.append(f"{client.client_name}: erro ao registrar")

    if errors:
        g.status = "error"
    else:
        g.status = "registered"
    g.updated_at = datetime.utcnow()

    try:
        await db.commit()
    except Exception as e:
        logger.error("Erro no commit ao registrar grupo %s: %s", group_id, e)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar registros: {e}")

    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "register_billing_group", "billing_group", str(group_id),
                     {"success": success_count, "errors": len(errors)}, ip)

    return {"status": g.status, "success": success_count, "errors": errors}


@router.post("/{group_id}/test")
async def test_group(
    group_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = (
        select(BillingGroup)
        .options(selectinload(BillingGroup.clients).selectinload(BillingGroupClient.config))
        .where(BillingGroup.id == group_id)
    )
    result = await db.execute(query)
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo nao encontrado")

    service = ClientBillingService(db)
    tested = 0
    errors_list = []

    for client in g.clients:
        if not client.config:
            continue
        try:
            await service.send_test(client.config)
            tested += 1
        except Exception as e:
            errors_list.append(f"{client.client_name}: {e}")

    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "test_billing_group", "billing_group", str(group_id),
                     {"tested": tested, "errors": len(errors_list)}, ip)

    return {"tested": tested, "errors": errors_list}
