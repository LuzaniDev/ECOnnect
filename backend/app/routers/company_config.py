from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models.user import User
from ..models.company_config import CompanyConfig
from ..schemas.company_config import CompanyConfigUpdate, CompanyConfigResponse

router = APIRouter(prefix="/api/company-config", tags=["company-config"])


def _build_response(config: CompanyConfig) -> dict:
    return {
        "company_code": config.company_code,
        "fb_database": config.fb_database,
        "fb_user": config.fb_user,
        "fb_password": config.fb_password,
        "updated_at": config.updated_at,
    }


@router.get("/{company_code}", response_model=CompanyConfigResponse)
async def get_company_config(
    company_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CompanyConfig).where(CompanyConfig.company_code == company_code)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Configuracao nao encontrada")
    return _build_response(config)


@router.put("/{company_code}", response_model=CompanyConfigResponse)
async def update_company_config(
    company_code: str,
    data: CompanyConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(CompanyConfig).where(CompanyConfig.company_code == company_code)
    )
    config = result.scalar_one_or_none()

    if not config:
        config = CompanyConfig(company_code=company_code)
        db.add(config)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)

    config.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(config)
    return _build_response(config)
