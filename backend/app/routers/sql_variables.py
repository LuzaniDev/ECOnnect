from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models.user import User
from ..models.sql_variable import SqlVariable
from ..schemas.sql_variable import (
    SqlVariableCreate,
    SqlVariableUpdate,
    SqlVariableResponse,
    SqlVariableListResponse,
)

router = APIRouter(prefix="/api/sql-variables", tags=["sql-variables"])


def _build_response(v: SqlVariable) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "label": v.label,
        "sql_query": v.sql_query,
        "value_column": v.value_column,
        "company_code": v.company_code,
        "created_by": v.created_by,
        "created_at": v.created_at,
        "updated_at": v.updated_at,
    }


def _build_list_response(v: SqlVariable) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "label": v.label,
        "sql_query": v.sql_query,
        "value_column": v.value_column,
        "company_code": v.company_code,
        "created_at": v.created_at,
        "updated_at": v.updated_at,
    }


@router.get("/", response_model=list[SqlVariableListResponse])
async def list_sql_variables(
    company_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(SqlVariable).order_by(SqlVariable.name.asc())
    if company_code:
        query = query.where(SqlVariable.company_code == company_code)
    elif current_user.eco_empresa:
        query = query.where(SqlVariable.company_code == current_user.eco_empresa)
    result = await db.execute(query)
    return [_build_list_response(v) for v in result.scalars().all()]


@router.get("/{variable_id}", response_model=SqlVariableResponse)
async def get_sql_variable(
    variable_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SqlVariable).where(SqlVariable.id == variable_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Variavel nao encontrada")
    return _build_response(v)


@router.post("/", response_model=SqlVariableResponse)
async def create_sql_variable(
    data: SqlVariableCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    v = SqlVariable(
        name=data.name,
        label=data.label,
        sql_query=data.sql_query,
        value_column=data.value_column,
        company_code=data.company_code,
        created_by=current_user.id,
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return _build_response(v)


@router.put("/{variable_id}", response_model=SqlVariableResponse)
async def update_sql_variable(
    variable_id: UUID,
    data: SqlVariableUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(SqlVariable).where(SqlVariable.id == variable_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Variavel nao encontrada")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(v, key, value)
    v.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(v)
    return _build_response(v)


@router.delete("/{variable_id}")
async def delete_sql_variable(
    variable_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(SqlVariable).where(SqlVariable.id == variable_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Variavel nao encontrada")
    await db.delete(v)
    await db.commit()
    return {"detail": "Variavel excluida"}
