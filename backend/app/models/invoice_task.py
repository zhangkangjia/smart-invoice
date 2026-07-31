"""开票任务、结果、交付、对账与异常模型。"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _gen_uuid


class InvoiceTask(Base):
    """开票任务。

    status 枚举:
        pending_validation / validation_passed / pending_submit / queuing /
        submitting / accepted / confirming / success / failed / unknown /
        awaiting_reconciliation / awaiting_manual / terminated
    """

    __tablename__ = "invoice_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_request_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    import_batch_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_validation", index=True, nullable=False)
    channel_submission_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    worker_node: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class InvoiceResult(Base):
    """开票结果。

    file_status 枚举: pending / available / missing
    """

    __tablename__ = "invoice_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    invoice_task_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_number: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    invoice_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_with_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    buyer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    file_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeliveryTask(Base):
    """交付任务。

    channel 枚举: email / download / api
    status 枚举: pending / sent / failed / retrying / delivered
    """

    __tablename__ = "delivery_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    invoice_result_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_results.id", ondelete="CASCADE"), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    receiver: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReconciliationCase(Base):
    """对账工单。

    case_type 枚举: unknown_result / callback_missing / amount_mismatch / file_missing / stuck_state
    status 枚举: open / investigating / resolved / closed
    """

    __tablename__ = "reconciliation_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    invoice_task_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_tasks.id", ondelete="CASCADE"), index=True, nullable=False)
    case_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExceptionCase(Base):
    """异常工单。

    exception_type 枚举:
        buyer_missing / tax_no_failed / product_unmatched / tax_rate_conflict /
        amount_mismatch / duplicate_suspect / quota_exceeded / auth_expired /
        channel_timeout / image_unclear / group_failed

    status 枚举: open / processing / resolved / ignored
    """

    __tablename__ = "exception_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="SET NULL"), index=True, nullable=True)
    invoice_task_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("invoice_tasks.id", ondelete="SET NULL"), nullable=True)
    exception_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_fixable: Mapped[bool] = mapped_column(default=False, nullable=False)
    affected_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True, nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
