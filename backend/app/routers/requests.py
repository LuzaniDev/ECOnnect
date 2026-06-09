from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
from ..database import get_db
from ..deps import get_current_user
from ..models.user import User
from ..models.request import Request
from ..schemas.request import RequestCreate, RequestResponse, RequestLinkUpdate
from ..services.request_service import RequestService

router = APIRouter(prefix="/api/requests", tags=["requests"])


def _build_response(r: Request) -> dict:
    return {
        "id": r.id,
        "template_id": r.template_id,
        "template_name": r.template.name if r.template else "",
        "client_phone": r.client_phone,
        "tag": r.tag,
        "link": r.link,
        "status": r.status,
        "created_by": r.created_by,
        "created_by_username": r.creator.username if r.creator else "",
        "created_at": r.created_at,
        "updated_at": r.updated_at,
        "parameter_values": [
            {
                "id": pv.id,
                "param_order": pv.param_order,
                "param_label": pv.param_label,
                "value": pv.value,
            }
            for pv in (r.parameter_values or [])
        ],
    }


@router.get("/", response_model=list[RequestResponse])
async def list_requests(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RequestService(db)
    is_admin = current_user.role == "admin"
    requests = await service.list_all(
        status=status, user_id=current_user.id, is_admin=is_admin,
        eco_empresa=current_user.eco_empresa,
    )
    return [_build_response(r) for r in requests]


@router.get("/history/{phone}", response_model=list[RequestResponse])
async def get_request_history(
    phone: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RequestService(db)
    requests = await service.get_history_by_phone(phone)
    return [_build_response(r) for r in requests]


@router.get("/{request_id}", response_model=RequestResponse)
async def get_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RequestService(db)
    req = await service.get_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    return _build_response(req)


@router.post("/", response_model=RequestResponse)
async def create_request(
    data: RequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RequestService(db)
    try:
        req = await service.create(data, current_user.id)
        return _build_response(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{request_id}/send", response_model=RequestResponse)
async def send_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RequestService(db)
    req = await service.get_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request is not pending")
    updated = await service.update_status(request_id, "sent")
    return _build_response(updated)


@router.put("/{request_id}/cancel", response_model=RequestResponse)
async def cancel_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RequestService(db)
    req = await service.get_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request is not pending")
    updated = await service.update_status(request_id, "cancelled")
    return _build_response(updated)


@router.put("/{request_id}/link", response_model=RequestResponse)
async def update_request_link(
    request_id: UUID,
    data: RequestLinkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RequestService(db)
    req = await service.get_by_id(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    updated = await service.update_link(request_id, data.link)
    return _build_response(updated)
