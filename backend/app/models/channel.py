"""开票通道模型。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _gen_uuid


class ChannelBinding(Base):
    """企业-通道绑定。

    status 枚举: pending / authorized / expired / revoked
    """

    __tablename__ = "channel_bindings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    credentials_encrypted: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class ChannelSubmission(Base):
    """通道提交记录。

    status 枚举: submitting / accepted / confirming / success / failed / unknown
    """

    __tablename__ = "channel_submissions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    invoice_task_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    request_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    channel_business_no: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    response_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="submitting", index=True, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChannelRequestLog(Base):
    """通道请求日志（脱敏）。"""

    __tablename__ = "channel_request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    channel_submission_id: Mapped[str] = mapped_column(String(32), ForeignKey("channel_submissions.id", ondelete="CASCADE"), index=True, nullable=False)
    request_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    request_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    response_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
