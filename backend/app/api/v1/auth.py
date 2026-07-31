"""认证路由。"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, Token
from app.services import auth_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=Token, summary="登录")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录，返回 access_token 和 refresh_token。"""
    user = await auth_service.authenticate_user(db, body.username, body.password)
    tokens = await auth_service.create_tokens_for_user(db, user)

    # 记录审计日志
    await log_action(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="login",
        entity_type="user",
        entity_id=user.id,
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    return Token(**tokens)


@router.post("/refresh", response_model=Token, summary="刷新 token")
async def refresh_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """使用 refresh_token 获取新的 token 对。"""
    tokens = await auth_service.refresh_access_token(db, body.refresh_token)
    await db.commit()
    return Token(**tokens)


@router.get("/me", summary="获取当前用户信息")
async def get_me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前登录用户的详细信息。"""
    from app.core.deps import _get_user_role_codes

    role_codes = await _get_user_role_codes(db, current_user.id)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "phone": current_user.phone,
        "full_name": current_user.full_name,
        "status": current_user.status,
        "is_super_admin": current_user.is_super_admin,
        "tenant_id": current_user.tenant_id,
        "roles": role_codes,
    }


@router.post("/logout", summary="登出")
async def logout(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """登出（前端清除 token，后端记录日志）。"""
    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="logout",
        entity_type="user",
        entity_id=current_user.id,
    )
    await db.commit()
    return {"message": "已登出"}
