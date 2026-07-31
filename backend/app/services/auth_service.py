"""认证服务。"""

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.models.user import Role, User, UserRole

logger = logging.getLogger(__name__)


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User:
    """验证用户名/密码，返回 User 或抛出 401。"""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return user


async def _get_user_role_codes(db: AsyncSession, user_id: str) -> list[str]:
    result = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return [row[0] for row in result.all()]


async def create_tokens_for_user(db: AsyncSession, user: User) -> dict[str, Any]:
    """为用户创建 access + refresh token。"""
    role_codes = await _get_user_role_codes(db, user.id)
    extra_claims = {
        "tenant_id": user.tenant_id,
        "username": user.username,
        "roles": role_codes,
    }
    access_token = create_access_token(
        subject=user.id,
        extra_claims=extra_claims,
    )
    refresh_token = create_refresh_token(
        subject=user.id,
        extra_claims=extra_claims,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "roles": role_codes,
    }


async def refresh_access_token(
    db: AsyncSession,
    refresh_token_str: str,
) -> dict[str, Any]:
    """用 refresh token 换取新的 access + refresh token。"""
    payload = verify_token(refresh_token_str, expected_type="refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token 无效或已过期",
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token 无效",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    return await create_tokens_for_user(db, user)
