"""认证相关 Schemas。"""

from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., min_length=1, description="密码")


class RefreshTokenRequest(BaseModel):
    """刷新 token 请求。"""

    refresh_token: str = Field(..., description="refresh token")


class Token(BaseModel):
    """登录返回的 token 响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    roles: List[str] = Field(default_factory=list)


class TokenData(BaseModel):
    """token 中携带的数据。"""

    user_id: Optional[str] = None
    username: Optional[str] = None
    tenant_id: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
