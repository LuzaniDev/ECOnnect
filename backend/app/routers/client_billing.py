import uuid
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from ..database import get_db, async_session
from ..deps import get_current_user, require_admin
from ..models.user import User
from ..models.company_config import CompanyConfig
from ..models.client_billing import ClientBillingConfig, BillingTemplate
from ..schemas.client_billing import (
    ClientBillingConfigCreate,
    ClientBillingConfigUpdate,
    ClientBillingConfigResponse,
    BillingTemplateCreate,
    BillingTemplateUpdate,
    BillingTemplateResponse,
)
from ..services.client_billing_service import ClientBillingService
from ..services.audit_service import log_action

router = APIRouter(prefix="/api/client-billing", tags=["client-billing"])

_batch_progress: dict[str, dict] = {}


def _build_template_response(t: BillingTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "method": t.method,
        "url": t.url,
        "headers": t.headers,
        "body": t.body,
        "tag": t.tag,
        "api_token": t.api_token,
        "flow_id": t.flow_id,
        "offset_days": t.offset_days,
        "send_time": t.send_time,
        "eco_empresa": t.eco_empresa,
        "created_by": t.created_by,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


@router.get("/templates", response_model=list[BillingTemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BillingTemplate)
        .where(BillingTemplate.eco_empresa == current_user.eco_empresa)
        .order_by(BillingTemplate.name)
    )
    return [_build_template_response(t) for t in result.scalars().all()]


@router.post("/templates", response_model=BillingTemplateResponse)
async def create_template(
    data: BillingTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    t = BillingTemplate(
        name=data.name,
        method=data.method,
        url=data.url,
        headers=data.headers,
        body=data.body,
        tag=data.tag,
        api_token=data.api_token,
        flow_id=data.flow_id,
        offset_days=data.offset_days,
        send_time=data.send_time,
        eco_empresa=current_user.eco_empresa,
        created_by=current_user.id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return _build_template_response(t)


@router.put("/templates/{template_id}", response_model=BillingTemplateResponse)
async def update_template(
    template_id: UUID,
    data: BillingTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(BillingTemplate).where(BillingTemplate.id == template_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template nao encontrado")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(t, key, value)
    t.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(t)
    return _build_template_response(t)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(BillingTemplate).where(BillingTemplate.id == template_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template nao encontrado")
    await db.delete(t)
    await db.commit()
    return {"detail": "Template excluido"}


async def _process_batch(
    batch_id: str,
    data: list[dict],
    user_id: UUID,
    eco_empresa: str,
    request: Request,
):
    async with async_session() as db:
        total = len(data)
        for i, item in enumerate(data):
            try:
                config_data = ClientBillingConfigCreate(**item)
                service = ClientBillingService(db)
                config = await service.create_config(config_data, user_id, eco_empresa)
                ip = request.client.host if request.client else None
                await log_action(db, user_id, "", "create_client_billing", "client_billing",
                                 str(config.id), {"client_code": config.client_code, "client_name": config.client_name}, ip)
            except Exception:
                pass
            _batch_progress[batch_id]["current"] = i + 1
        _batch_progress[batch_id]["done"] = True


def _build_response(config) -> dict:
    return {
        "id": config.id,
        "client_code": config.client_code,
        "client_name": config.client_name,
        "client_phone": config.client_phone,
        "eco_empresa": config.eco_empresa,
        "billing_template_id": config.billing_template_id,
        "template_name": config.template_name,
        "template_method": config.template_method,
        "template_url": config.template_url,
        "template_headers": config.template_headers,
        "template_body": config.template_body,
        "template_tag": config.template_tag,
        "api_token": config.api_token,
        "flow_id": config.flow_id,
        "offset_days": config.offset_days,
        "send_time": config.send_time,
        "is_active": config.is_active,
        "last_pendencia_vencimento": config.last_pendencia_vencimento,
        "last_sent_at": config.last_sent_at,
        "next_check_date": config.next_check_date,
        "created_by": config.created_by,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.get("/configs", response_model=list[ClientBillingConfigResponse])
async def list_configs(
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ClientBillingService(db)
    configs = await service.list_configs(
        eco_empresa=current_user.eco_empresa,
        is_active=is_active,
    )
    return [_build_response(c) for c in configs]


@router.get("/configs/{config_id}", response_model=ClientBillingConfigResponse)
async def get_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ClientBillingService(db)
    config = await service.get_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    if current_user.eco_empresa and config.eco_empresa != current_user.eco_empresa:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return _build_response(config)


@router.post("/configs", response_model=ClientBillingConfigResponse)
async def create_config(
    data: ClientBillingConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientBillingService(db)
    config = await service.create_config(
        data, current_user.id, eco_empresa=current_user.eco_empresa or "01"
    )
    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "create_client_billing", "client_billing", str(config.id),
                     {"client_code": config.client_code, "client_name": config.client_name}, ip)
    return _build_response(config)


@router.post("/configs/batch")
async def create_configs_batch(
    data: list[dict],
    request: Request,
    current_user: User = Depends(require_admin),
):
    batch_id = str(uuid.uuid4())
    total = len(data)
    _batch_progress[batch_id] = {"total": total, "current": 0, "done": False}

    asyncio.create_task(_process_batch(
        batch_id, data, current_user.id, current_user.eco_empresa or "01", request
    ))

    return {"batch_id": batch_id, "total": total}


@router.get("/batch-status/{batch_id}")
async def get_batch_status(batch_id: str):
    status = _batch_progress.get(batch_id)
    if not status:
        raise HTTPException(status_code=404, detail="Batch nao encontrado")
    return status


@router.put("/configs/{config_id}", response_model=ClientBillingConfigResponse)
async def update_config(
    config_id: UUID,
    data: ClientBillingConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientBillingService(db)
    existing = await service.get_config(config_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    if current_user.eco_empresa and existing.eco_empresa != current_user.eco_empresa:
        raise HTTPException(status_code=403, detail="Acesso negado")
    config = await service.update_config(config_id, data)
    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "update_client_billing", "client_billing", str(config_id),
                     {"fields": list(data.model_dump(exclude_unset=True).keys())}, ip)
    return _build_response(config)


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientBillingService(db)
    existing = await service.get_config(config_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    if current_user.eco_empresa and existing.eco_empresa != current_user.eco_empresa:
        raise HTTPException(status_code=403, detail="Acesso negado")
    deleted = await service.delete_config(config_id)
    ip = request.client.host if request.client else None
    await log_action(db, current_user.id, current_user.username,
                     "delete_client_billing", "client_billing", str(config_id),
                     {"client_name": existing.client_name}, ip)
    return {"detail": "Configuracao excluida"}


@router.post("/check")
async def trigger_check(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ClientBillingService(db)
    await service.check_due_configs()
    return {"detail": "Verificacao concluida"}


async def _get_fb_conn(db: AsyncSession, empresa: str):
    result = await db.execute(
        select(CompanyConfig).where(CompanyConfig.company_code == empresa)
    )
    cc = result.scalar_one_or_none()
    if not cc:
        raise HTTPException(status_code=404, detail="Configuracao da empresa nao encontrada")
    import fdb
    return fdb.connect(
        dsn=cc.fb_database.replace("/", "\\"),
        user=cc.fb_user,
        password=cc.fb_password,
        charset="WIN1252",
    )


@router.get("/tipos")
async def list_tipos_cliente(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    empresa = current_user.eco_empresa or "01"
    fb_conn = await _get_fb_conn(db, empresa)
    try:
        cursor = fb_conn.cursor()
        cursor.execute("SELECT COD_TIPO, DESCR_TIPO FROM TRecTipoCliente WHERE ATIVO = 1 ORDER BY COD_TIPO")
        rows = cursor.fetchall()
        fb_conn.commit()
    except Exception:
        fb_conn.rollback()
        raise
    finally:
        fb_conn.close()

    return [
        {"cod_tipo": str(r[0] or "").strip(), "descr_tipo": str(r[1] or "").strip()}
        for r in rows
    ]


@router.get("/clientes")
async def list_clientes(
    page: int = Query(0, ge=0),
    nome: str = Query(""),
    page_size: int = Query(100, ge=1, le=500),
    tipo: str = Query(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    empresa = current_user.eco_empresa or "01"
    fb_conn = await _get_fb_conn(db, empresa)

    filtros = []
    if nome:
        safe = nome.replace("'", "''")
        if len(nome) >= 3:
            filtros.append(f"AND UPPER(Clg.Nome) STARTING WITH UPPER('{safe}')")
        else:
            filtros.append(f"AND Clg.Nome CONTAINING '{safe}'")

    if tipo:
        codigos = [t.strip() for t in tipo.split(",") if t.strip()]
        if codigos:
            quoted = ", ".join(f"'{c}'" for c in codigos)
            filtros.append(f"AND Clg.TipoCliente IN ({quoted})")

    sql = f"""
        SELECT FIRST {page_size} SKIP {page * page_size}
               Emp.Codigo,
               Clg.Codigo                                          AS Cliente,
               Clg.Nome,
               COALESCE(Clg.FoneCelular, Clg.Fone)                 AS Fone
          FROM TRecClienteGeral Clg
          JOIN TGerEmpresa Emp ON Emp.Codigo = ?
         WHERE 1=1 {' '.join(filtros)}
         ORDER BY Clg.Nome
    """
    try:
        cursor = fb_conn.cursor()
        cursor.execute(sql, (empresa,))
        rows = cursor.fetchall()
        fb_conn.commit()
    except Exception:
        fb_conn.rollback()
        raise
    finally:
        fb_conn.close()

    return {
        "data": [
            {
                "codigo": str(r[1] or ""),
                "nome": str(r[2] or ""),
                "fone": str(r[3] or "").strip(),
            }
            for r in rows
        ],
        "page": page,
        "page_size": page_size,
        "has_more": len(rows) >= page_size,
    }


@router.get("/pendencias/{client_code}")
async def get_client_pendencias(
    client_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    empresa = current_user.eco_empresa or "01"

    result = await db.execute(
        select(CompanyConfig).where(CompanyConfig.company_code == empresa)
    )
    company_config = result.scalar_one_or_none()
    if not company_config:
        raise HTTPException(status_code=404, detail="Configuracao da empresa nao encontrada")

    import fdb
    fb_conn = fdb.connect(
        dsn=company_config.fb_database.replace("/", "\\"),
        user=company_config.fb_user,
        password=company_config.fb_password,
        charset="WIN1252",
    )

    from ..services.client_billing_service import COBRANCA_SQL
    try:
        cursor = fb_conn.cursor()
        cursor.execute("""
            SELECT Clg.Nome, Clg.CpfCnpj, Clg.Fone, Clg.FoneCelular,
                   Clg.Endereco, Clg.NumeroEndereco, Clg.Bairro, Clg.Cidade, Clg.Regiao
              FROM TRecClienteGeral Clg
             WHERE Clg.Codigo = ?
        """, (client_code,))
        client_row = cursor.fetchone()

        cursor.execute(COBRANCA_SQL, (empresa, client_code))
        rows = cursor.fetchall()
        fb_conn.commit()
    except Exception:
        fb_conn.rollback()
        raise
    finally:
        fb_conn.close()

    client_info = {
        "client_code": client_code,
        "client_name": client_row[0] if client_row else "",
        "cpf_cnpj": client_row[1] if client_row else "",
        "fone": str(client_row[2] or client_row[3] or "").strip() if client_row else "",
        "endereco": client_row[4] if client_row else "",
        "numero": client_row[5] if client_row else "",
        "bairro": client_row[6] if client_row else "",
        "cidade": client_row[7] if client_row else "",
        "regiao": client_row[8] if client_row else "",
    }

    result_list = []
    for r in rows:
        venc = str(r[17])[:10] if r[17] else ""
        emissao = str(r[16])[:10] if r[16] else ""
        item = {
            "documento_str": r[13] if r[13] else "",
            "emissao": emissao,
            "vencimento": venc,
            "valor_total": float(r[18] or 0),
            "valor_pendente": float(r[20] or 0),
            "multa": float(r[21] or 0),
            "juros": float(r[22] or 0),
            "situacao": r[30] if r[30] else "",
        }
        result_list.append(item)

    return {**client_info, "pendencias": result_list}
