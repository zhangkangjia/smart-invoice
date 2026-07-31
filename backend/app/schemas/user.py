"""用户与角色 Schemas。"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(..., max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    full_name: Optional[str] = Field(default=None, max_length=100)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)
    tenant_id: Optional[str] = None
    role_codes: List[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    full_name: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default=None, max_length=20)
    role_codes: Optional[List[str]] = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    status: str
    is_super_admin: bool
    created_at: datetime
    updated_at: datetime
    roles: List[str] = Field(default_factory=list)


class UserBrief(BaseModel):
    """用户简要信息。"""

    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    full_name: Optional[str] = None


class RoleCreate(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    permissions: List[Any] = Field(default_factory=list)


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    code: str
    description: Optional[str] = None
    permissions: List[Any] = Field(default_factory=list)
