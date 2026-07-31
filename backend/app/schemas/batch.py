"""批量操作 Schemas。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BatchPreviewRequest(BaseModel):
    """批量操作预览请求。"""

    operation_type: str = Field(
        ...,
        description="操作类型: invoice / retry / rule_change / enterprise_pause / channel_switch",
    )
    target_ids: list[str] = Field(default_factory=list, description="目标ID列表")
    params: dict[str, Any] = Field(default_factory=dict, description="操作参数")


class BatchExecuteRequest(BaseModel):
    """批量操作执行请求。"""

    operation_type: str = Field(..., description="操作类型")
    target_ids: list[str] = Field(default_factory=list, description="目标ID列表")
    params: dict[str, Any] = Field(default_factory=dict, description="操作参数")
    preview_token: str = Field(..., description="预览返回的确认令牌")


class BatchPreviewResponse(BaseModel):
    """批量操作预览响应。"""

    operation_type: str
    total_count: int = 0
    executable_count: int = 0
    non_executable_count: int = 0
    high_risk_count: int = 0
    unknown_result_count: int = 0
    requires_approval: bool = False
    affected_enterprises: list[str] = Field(default_factory=list)
    details: list[dict[str, Any]] = Field(default_factory=list)
    non_executable_reasons: dict[str, list[str]] = Field(default_factory=dict)
    preview_token: str | None = None


class BatchExecuteResponse(BaseModel):
    """批量操作执行响应。"""

    operation_type: str
    batch_no: str
    total_count: int
    success_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    details: list[dict[str, Any]] = Field(default_factory=list)


class CreateLinkRequest(BaseModel):
    """创建提交链接请求。"""

    enterprise_id: str
    link_type: str = Field(default="one_time", description="one_time / permanent / expiring")
    password: str | None = Field(default=None, description="访问密码（可选）")
    max_uses: int = Field(default=1, ge=1, description="最大使用次数")
    expires_at: datetime | None = Field(default=None, description="过期时间")


class SubmissionLinkResponse(BaseModel):
    """提交链接响应。"""

    id: str
    enterprise_id: str
    token: str
    link_type: str
    max_uses: int
    used_count: int
    expires_at: datetime | None = None
    is_active: bool
    created_at: datetime


class SubmissionInfoResponse(BaseModel):
    """提交链接信息响应（客户可见，脱敏）。"""

    enterprise_name: str
    requires_password: bool
    link_type: str


class SubmissionAuthResponse(BaseModel):
    """提交链接认证响应。"""

    session_token: str
    expires_in: int = 3600


class SubmissionResultResponse(BaseModel):
    """提交结果响应。"""

    request_id: str
    status: str
    current_stage: str | None = None
    invoice_number: str | None = None
    file_download_url: str | None = None
