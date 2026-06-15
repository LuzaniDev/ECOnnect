from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models.user import User
from ..models.template import Template
from ..schemas.meta import (
    MetaCredentialsCreate,
    MetaCredentialsUpdate,
    MetaCredentialsResponse,
    MetaVerifyRequest,
    MetaVerifyResponse,
    MetaTemplateSyncRequest,
    MetaTemplateSyncResponse,
    MetaSendRequest,
    MetaSendResponse,
    MetaMessageResponse,
)
from ..services import meta_service

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/credentials", response_model=MetaCredentialsResponse | None)
async def get_credentials(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eco = current_user.eco_empresa
    creds = await meta_service.get_credentials(db, eco)
    if not creds:
        return None
    return creds


@router.post("/credentials", response_model=MetaCredentialsResponse)
async def save_credentials(
    data: MetaCredentialsCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    eco = current_user.eco_empresa
    if not eco:
        raise HTTPException(status_code=400, detail="Usuário sem empresa vinculada")
    creds = await meta_service.save_credentials(db, eco, data.model_dump())
    return creds


@router.post("/verify", response_model=MetaVerifyResponse)
async def verify(
    data: MetaVerifyRequest,
    current_user: User = Depends(require_admin),
):
    ok, msg = await meta_service.verify_credentials(
        data.waba_id, data.phone_number_id, data.access_token
    )
    return MetaVerifyResponse(verified=ok, message=msg)


@router.post("/templates/sync", response_model=MetaTemplateSyncResponse)
async def sync_template(
    data: MetaTemplateSyncRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    eco = current_user.eco_empresa
    if not eco:
        raise HTTPException(status_code=400, detail="Usuário sem empresa vinculada")

    creds = await meta_service.get_credentials(db, eco)
    if not creds or not creds.is_verified:
        raise HTTPException(status_code=400, detail="Credenciais Meta não configuradas")

    result = await db.execute(
        Template.__table__.select().where(
            Template.__table__.c.id == data.template_id,
            Template.__table__.c.eco_empresa == eco,
        )
    )
    template_row = result.fetchone()
    if not template_row:
        raise HTTPException(status_code=404, detail="Template não encontrado")

    template = Template(
        id=template_row.id,
        name=template_row.name,
        body=template_row.body,
        parameter_count=template_row.parameter_count,
        description=template_row.description,
    )

    meta_id, meta_status, msg = await meta_service.create_meta_template(creds, template)

    await db.execute(
        Template.__table__.update()
        .where(Template.__table__.c.id == data.template_id)
        .values(meta_template_id=meta_id, meta_status=meta_status)
    )
    await db.commit()

    return MetaTemplateSyncResponse(
        meta_template_id=meta_id,
        meta_status=meta_status,
        success=bool(meta_id),
        message=msg,
    )


@router.get("/templates/{template_id}/status")
async def template_status(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eco = current_user.eco_empresa
    result = await db.execute(
        Template.__table__.select().where(
            Template.__table__.c.id == template_id,
            Template.__table__.c.eco_empresa == eco,
        )
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    return {
        "meta_template_id": row.meta_template_id,
        "meta_status": row.meta_status,
    }


@router.post("/send", response_model=MetaSendResponse)
async def send_message(
    data: MetaSendRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eco = current_user.eco_empresa
    if not eco:
        raise HTTPException(status_code=400, detail="Usuário sem empresa vinculada")

    creds = await meta_service.get_credentials(db, eco)
    if not creds or not creds.is_verified:
        raise HTTPException(status_code=400, detail="Credenciais Meta não configuradas")

    result = await db.execute(
        Template.__table__.select().where(
            Template.__table__.c.id == data.template_id,
            Template.__table__.c.eco_empresa == eco,
        )
    )
    template_row = result.fetchone()
    if not template_row:
        raise HTTPException(status_code=404, detail="Template não encontrado")

    template = Template(
        name=template_row.name,
        body=template_row.body,
        parameter_count=template_row.parameter_count,
    )

    ok, msg_id, msg = await meta_service.send_template_message(
        creds, template, data.client_phone, data.parameter_values
    )

    await meta_service.log_message(
        db,
        eco,
        {
            "from_phone": creds.phone_number_id,
            "to_phone": data.client_phone,
            "direction": "outgoing",
            "template_name": template.name,
            "body": template.body,
            "meta_message_id": msg_id,
            "status": "sent" if ok else "failed",
        },
    )

    return MetaSendResponse(success=ok, message_id=msg_id, message=msg)


@router.get("/messages", response_model=list[MetaMessageResponse])
async def list_messages(
    phone: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    eco = current_user.eco_empresa
    msgs = await meta_service.list_messages(db, eco, phone)
    return msgs
