from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models.user import User
from ..models.template import Template
from ..schemas.template import TemplateCreate, TemplateUpdate, TemplateResponse
from ..services.template_service import TemplateService

router = APIRouter(prefix="/api/templates", tags=["templates"])


def _build_response(t: Template) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "body": t.body,
        "description": t.description,
        "parameter_count": t.parameter_count,
        "created_by": t.created_by,
        "creator_username": t.creator.username if t.creator else "",
        "is_active": t.is_active,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "parameters": [
            {"order": i + 1}
            for i in range(t.parameter_count or 0)
        ],
    }


@router.get("/", response_model=list[TemplateResponse])
async def list_templates(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TemplateService(db)
    templates = await service.list_all(active_only=active_only, eco_empresa=current_user.eco_empresa)
    return [_build_response(t) for t in templates]


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TemplateService(db)
    template = await service.get_by_id(template_id, eco_empresa=current_user.eco_empresa)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return _build_response(template)


@router.post("/", response_model=TemplateResponse)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = TemplateService(db)
    template = await service.create(data, current_user.id, eco_empresa=current_user.eco_empresa)
    result = await service.get_by_id(template.id, eco_empresa=current_user.eco_empresa)
    return _build_response(result)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = TemplateService(db)
    existing = await service.get_by_id(template_id, eco_empresa=current_user.eco_empresa)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    template = await service.update(template_id, data)
    result = await service.get_by_id(template.id, eco_empresa=current_user.eco_empresa)
    return _build_response(result)


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = TemplateService(db)
    existing = await service.get_by_id(template_id, eco_empresa=current_user.eco_empresa)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    success = await service.delete(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted successfully"}
