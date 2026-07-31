"""企业 Schemas。"""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EnterpriseCreate(BaseModel):
    name: str = Field(..., max_length=300)
    tax_no: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    bank_name: Optional[str] = Field(default=None, max_length=200)
    bank_account: Optional[str] = Field(default=None, max_length=100)
    agency_id: Optional[str] = None
    branch_id: Optional[str] = None
    service_level: str = Field(default="normal", max_length=30)
    status: str = Field(default="pending", max_length=30)


class EnterpriseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=300)
    tax_no: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    bank_name: Optional[str] = Field(default=None, max_length=200)
    bank_account: Optional[str] = Field(default=None, max_length=100)
    agency_id: Optional[str] = None
    branch_id: Optional[str] = None
    service_level: Optional[str] = Field(default=None, max_length=30)


class EnterpriseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    name: str
    tax_no: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    status: str
    agency_id: Optional[str] = None
    branch_id: Optional[str] = None
    service_level: str
    created_at: datetime
    updated_at: datetime


class EnterpriseBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    tax_no: Optional[str] = None
    status: str


class EnterpriseConfigUpdate(BaseModel):
    invoice_types: Optional[List[Any]] = None
    default_tax_rate: Optional[Decimal] = Field(default=None, decimal_places=6)
    single_amount_limit: Optional[Decimal] = Field(default=None, decimal_places=2)
    daily_limit: Optional[int] = None
    max_concurrency: Optional[int] = None
    auto_approve_threshold: Optional[Decimal] = Field(default=None, decimal_places=2)
    split_rules: Optional[dict[str, Any]] = None
    merge_rules: Optional[dict[str, Any]] = None
    remark_template: Optional[str] = Field(default=None, max_length=500)
    enabled_time_windows: Optional[List[Any]] = None


class EnterpriseConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    enterprise_id: str
    invoice_types: Optional[List[Any]] = None
    default_tax_rate: Optional[Decimal] = None
    single_amount_limit: Optional[Decimal] = None
    daily_limit: Optional[int] = None
    max_concurrency: Optional[int] = None
    auto_approve_threshold: Optional[Decimal] = None
    split_rules: Optional[dict[str, Any]] = None
    merge_rules: Optional[dict[str, Any]] = None
    remark_template: Optional[str] = None
    enabled_time_windows: Optional[List[Any]] = None


class ServiceAssignmentCreate(BaseModel):
    user_id: str
    role: str = Field(..., max_length=50)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class ServiceAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    enterprise_id: str
    user_id: str
    role: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    status: str
    created_at: datetime
