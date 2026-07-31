"""开票请求 Schemas。"""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class InvoiceItemCreate(BaseModel):
    product_name: str = Field(..., max_length=500)
    tax_code: Optional[str] = Field(default=None, max_length=50)
    spec: Optional[str] = Field(default=None, max_length=200)
    unit: Optional[str] = Field(default=None, max_length=50)
    quantity: Decimal = Field(..., max_digits=18, decimal_places=6)
    unit_price: Decimal = Field(..., max_digits=18, decimal_places=8)
    tax_rate: Optional[Decimal] = Field(default=None, max_digits=8, decimal_places=6)
    discount_amount: Optional[Decimal] = Field(default=0, max_digits=18, decimal_places=2)


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    invoice_request_id: str
    product_name: str
    tax_code: Optional[str] = None
    spec: Optional[str] = None
    unit: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_with_tax: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None


class InvoiceRequestCreate(BaseModel):
    enterprise_id: str
    business_request_id: Optional[str] = None
    invoice_type: str = Field(..., max_length=30)
    buyer_name: str = Field(..., max_length=300)
    buyer_tax_no: Optional[str] = Field(default=None, max_length=50)
    buyer_address: Optional[str] = Field(default=None, max_length=500)
    buyer_phone: Optional[str] = Field(default=None, max_length=50)
    buyer_bank_name: Optional[str] = Field(default=None, max_length=200)
    buyer_bank_account: Optional[str] = Field(default=None, max_length=100)
    is_tax_inclusive: bool = True
    remark: Optional[str] = None
    receiver_email: Optional[str] = None
    receiver_mobile: Optional[str] = Field(default=None, max_length=50)
    items: List[InvoiceItemCreate] = Field(..., min_length=1)


class InvoiceRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    enterprise_id: str
    business_request_id: Optional[str] = None
    invoice_type: str
    buyer_name: str
    buyer_tax_no: Optional[str] = None
    buyer_address: Optional[str] = None
    buyer_phone: Optional[str] = None
    buyer_bank_name: Optional[str] = None
    buyer_bank_account: Optional[str] = None
    is_tax_inclusive: bool
    total_amount: Optional[Decimal] = None
    total_tax: Optional[Decimal] = None
    total_with_tax: Optional[Decimal] = None
    remark: Optional[str] = None
    receiver_email: Optional[str] = None
    receiver_mobile: Optional[str] = None
    config_snapshot: Optional[dict[str, Any]] = None
    status: str
    created_at: datetime
    items: List[InvoiceItemResponse] = Field(default_factory=list)
