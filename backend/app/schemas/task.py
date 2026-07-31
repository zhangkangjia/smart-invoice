"""工作项与导入批次 Schemas。"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkItemUpdate(BaseModel):
    assigned_to: Optional[str] = None
    priority: Optional[str] = Field(default=None, max_length=20)
    deadline_at: Optional[datetime] = None
    status: Optional[str] = Field(default=None, max_length=20)
    handling_note: Optional[str] = None


class WorkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    enterprise_id: Optional[str] = None
    business_request_id: Optional[str] = None
    work_type: str
    assigned_to: Optional[str] = None
    collaborator_ids: Optional[List[Any]] = None
    priority: str
    deadline_at: Optional[datetime] = None
    status: str
    exception_reason: Optional[str] = None
    handling_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ImportBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    source_type: str
    created_by: Optional[str] = None
    enterprise_count: int
    task_count: int
    success_count: int
    failure_count: int
    exception_count: int
    status: str
    file_name: Optional[str] = None
    created_at: datetime
