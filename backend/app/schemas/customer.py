"""客户抬头与联系人 Schemas。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerTitleCreate(BaseModel):
    name: str = Field(..., max_length=300)
    alias: Optional[str] = Field(default=None, max_length=300)
    tax_no: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    bank_name: Optional[str] = Field(default=None, max_length=200)
    bank_account: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    mobile: Optional[str] = Field(default=None, max_length=50)


class CustomerTitleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=300)
    alias: Optional[str] = Field(default=None, max_length=300)
    tax_no: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    bank_name: Optional[str] = Field(default=None, max_length=200)
    bank_account: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    mobile: Optional[str] = Field(default=None, max_length=50)
    status: Optional[str] = Field(default=None, max_length=20)


class CustomerTitleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    enterprise_id: str
    name: str
    alias: Optional[str] = None
    tax_no: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class CustomerContactCreate(BaseModel):
    customer_title_id: Optional[str] = None
    name: str = Field(..., max_length=100)
    mobile: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    is_primary: bool = False


class CustomerContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    enterprise_id: str
    customer_title_id: Optional[str] = None
    name: str
    mobile: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool
    created_at: datetime
