"""安全工具：JWT、密码哈希。"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import hashlib
import hmac
import os
import base64

from jose import JWTError, jwt

from app.core.config import settings


# --------------------------------------------------------------------------- #
# 密码哈希 - 使用 bcrypt 直接调用避免 passlib 兼容性问题
# --------------------------------------------------------------------------- #
import bcrypt


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。"""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配。"""
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #

def _create_token(
    subject: str,
    expires_delta: timedelta,
    token_type: str,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(
    subject: str,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """创建 access token。"""
    return _create_token(
        subject,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
        extra_claims,
    )


def create_refresh_token(
    subject: str,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """创建 refresh token。"""
    return _create_token(
        subject,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh",
        extra_claims,
    )


def decode_token(token: str) -> dict[str, Any]:
    """解码 JWT，返回 payload dict。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def verify_token(token: str, expected_type: str = "access") -> Optional[dict[str, Any]]:
    """验证 token，返回 payload 或 None。"""
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload
