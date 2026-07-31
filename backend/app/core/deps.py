"""FastAPI 依赖注入。"""

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.db.session import get_db
from app.models.user import Role, User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """从 JWT token 中解析当前用户。

    支持多租户切换：JWT 中若有 current_tenant_id（仅超管有），
    则覆盖 user.tenant_id 作为当前操作租户。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verify_token(token, expected_type="access")
    if payload is None:
        raise credentials_exception

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    # 超管租户切换：如果 JWT 里有 current_tenant_id 且与用户原始 tenant 不同，
    # 临时把 user.tenant_id 替换为 current_tenant_id（不持久化）
    switched_tenant = payload.get("current_tenant_id")
    if switched_tenant and user.is_super_admin and switched_tenant != user.tenant_id:
        # 标记当前为切换后的租户（不改 DB）
        object.__setattr__(user, "_switched_tenant_id", switched_tenant)
    return user


def get_tenant_id(user: User) -> str:
    """获取当前操作租户ID（支持超管切换后的租户）。"""
    return getattr(user, "_switched_tenant_id", None) or user.tenant_id


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """确保当前用户处于活跃状态。"""
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return current_user


async def _get_user_role_codes(db: AsyncSession, user_id: str) -> list[str]:
    """获取用户的角色 code 列表。"""
    result = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return [row[0] for row in result.all()]


def require_roles(*required_roles: str):
    """角色检查依赖工厂。

    用法::

        @router.get("/", dependencies=[Depends(require_roles("admin"))])
    """

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_super_admin:
            return current_user
        user_roles = await _get_user_role_codes(db, current_user.id)
        if not any(r in required_roles for r in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(required_roles)}",
            )
        return current_user

    return role_checker
