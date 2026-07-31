"""商品规则 Schemas。"""

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductRuleCreate(BaseModel):
    enterprise_id: str
    original_name: str = Field(..., max_length=500)
    aliases: List[str] = Field(default_factory=list)
    standard_name: str = Field(..., max_length=500)
    tax_code: Optional[str] = Field(default=None, max_length=50)
    default_tax_rate: Optional[Decimal] = Field(default=None, decimal_places=6)
    unit: Optional[str] = Field(default=None, max_length=50)
    spec: Optional[str] = Field(default=None, max_length=200)
    remark_template: Optional[str] = Field(default=None, max_length=500)


class ProductRuleUpdate(BaseModel):
    original_name: Optional[str] = Field(default=None, max_length=500)
    aliases: Optional[List[str]] = None
    standard_name: Optional[str] = Field(default=None, max_length=500)
    tax_code: Optional[str] = Field(default=None, max_length=50)
    default_tax_rate: Optional[Decimal] = Field(default=None, decimal_places=6)
    unit: Optional[str] = Field(default=None, max_length=50)
    spec: Optional[str] = Field(default=None, max_length=200)
    remark_template: Optional[str] = Field(default=None, max_length=500)
    status: Optional[str] = Field(default=None, max_length=20)


class ProductRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    enterprise_id: str
    original_name: str
    aliases: Optional[List[Any]] = None
    standard_name: str
    tax_code: Optional[str] = None
    default_tax_rate: Optional[Decimal] = None
    unit: Optional[str] = None
    spec: Optional[str] = None
    remark_template: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
