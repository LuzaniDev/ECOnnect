from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models.user import User
from ..schemas.auth import RegisterRequest, LoginRequest, EcoLoginRequest, TokenResponse
from ..schemas.user import UserResponse
from ..services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
)
from ..deps import get_current_user
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")

    result = await db.execute(select(User))
    is_first = result.first() is None

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role="admin" if is_first else "user",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)


@router.post("/eco-login", response_model=TokenResponse)
async def eco_login(data: EcoLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.eco_usuario == data.eco_usuario)
    )
    user = result.scalar_one_or_none()

    if user:
        if user.role != data.role:
            user.role = data.role
        if user.eco_empresa != data.eco_empresa:
            user.eco_empresa = data.eco_empresa
        if not user.is_active:
            user.is_active = True
        await db.commit()
        await db.refresh(user)
    else:
        user = User(
            username=data.eco_usuario,
            email=f"{data.eco_usuario.lower()}@eco.local",
            hashed_password=hash_password(str(uuid.uuid4())),
            role=data.role,
            eco_usuario=data.eco_usuario,
            eco_empresa=data.eco_empresa,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
