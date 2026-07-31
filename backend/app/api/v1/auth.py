"""认证路由。"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db
from app.models.tenant import Tenant
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
    from app.core.deps import _get_user_role_codes, get_tenant_id

    role_codes = await _get_user_role_codes(db, current_user.id)
    current_tenant_id = get_tenant_id(current_user)

    # 获取当前租户名
    tenant_name = ""
    if current_tenant_id:
        t_result = await db.execute(select(Tenant).where(Tenant.id == current_tenant_id))
        tenant = t_result.scalar_one_or_none()
        if tenant:
            tenant_name = tenant.name

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "phone": current_user.phone,
        "full_name": current_user.full_name,
        "status": current_user.status,
        "is_super_admin": current_user.is_super_admin,
        "tenant_id": current_tenant_id,
        "tenant_name": tenant_name,
        "original_tenant_id": current_user.tenant_id,
        "roles": role_codes,
    }


@router.get("/tenants", summary="可访问的租户列表（超管）")
async def list_tenants(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取可切换的租户列表。

    - 超级管理员：返回所有租户
    - 普通用户：只返回自己所属租户
    """
    if current_user.is_super_admin:
        result = await db.execute(select(Tenant).where(Tenant.status == "active").order_by(Tenant.name))
        tenants = result.scalars().all()
    else:
        result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
        tenants = result.scalars().all()

    from app.core.deps import get_tenant_id
    current_tenant_id = get_tenant_id(current_user)

    return {
        "current_tenant_id": current_tenant_id,
        "tenants": [
            {"id": t.id, "name": t.name, "code": t.code, "status": t.status}
            for t in tenants
        ],
    }


@router.post("/switch-tenant", summary="切换当前操作租户（超管）")
async def switch_tenant(
    body: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """切换当前操作的租户（仅超级管理员）。

    切换后颁发新 token，前端替换旧 token。
    退出切换：调用本接口传 tenant_id = 用户原始 tenant_id。
    """
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="仅超级管理员可切换租户")

    target_tenant_id = body.get("tenant_id")
    if not target_tenant_id:
        raise HTTPException(status_code=400, detail="缺少 tenant_id")

    # 校验目标租户存在
    result = await db.execute(select(Tenant).where(Tenant.id == target_tenant_id, Tenant.status == "active"))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在或已停用")

    # 颁发带 current_tenant_id 的新 token
    from app.core.deps import _get_user_role_codes
    role_codes = await _get_user_role_codes(db, current_user.id)
    extra_claims = {
        "tenant_id": current_user.tenant_id,
        "current_tenant_id": target_tenant_id,
        "username": current_user.username,
        "roles": role_codes,
    }
    access_token = create_access_token(subject=current_user.id, extra_claims=extra_claims)
    refresh_token = create_refresh_token(subject=current_user.id, extra_claims=extra_claims)

    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="switch_tenant",
        entity_type="tenant",
        entity_id=target_tenant_id,
        after={"to_tenant": tenant.name},
    )
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "current_tenant_id": target_tenant_id,
        "current_tenant_name": tenant.name,
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
