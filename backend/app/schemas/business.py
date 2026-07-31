"""业务申请 Schemas。"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class BusinessRequestCreate(BaseModel):
    """文字提交创建业务申请。"""

    enterprise_id: str
    source_type: str = Field(default="text", max_length=20)
    source_channel: Optional[str] = Field(default=None, max_length=50)
    external_order_no: Optional[str] = Field(default=None, max_length=100)
    customer_remark: Optional[str] = None
    internal_remark: Optional[str] = None
    urgency: str = Field(default="normal", max_length=20)
    expected_at: Optional[datetime] = None
    contact_id: Optional[str] = None
    content: Optional[str] = None  # 文字内容


class BusinessRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    enterprise_id: str
    source_type: str
    source_channel: Optional[str] = None
    external_order_no: Optional[str] = None
    contact_id: Optional[str] = None
    customer_remark: Optional[str] = None
    internal_remark: Optional[str] = None
    urgency: str
    expected_at: Optional[datetime] = None
    current_handler_id: Optional[str] = None
    current_stage: Optional[str] = None
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SourceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    business_request_id: str
    doc_type: str
    content: Optional[str] = None
    file_key: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    ocr_result: Optional[dict[str, Any]] = None
    created_at: datetime
