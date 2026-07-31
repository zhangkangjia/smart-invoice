"""工作项、交接、导入批次模型。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _gen_uuid


class WorkItem(Base):
    """工作项（待办任务）。

    work_type 枚举: data_correction / rule_conflict / approval / retry / delivery / channel_error / supplement
    priority 枚举: low / normal / high / urgent
    status 枚举: pending / in_progress / resolved / cancelled / escalated
    """

    __tablename__ = "work_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="SET NULL"), index=True, nullable=True)
    business_request_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("business_requests.id", ondelete="SET NULL"), nullable=True)
    work_type: Mapped[str] = mapped_column(String(30), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    collaborator_ids: Mapped[list[Any] | None] = mapped_column(JSON, default=list, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    exception_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    handling_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class WorkItemAssignment(Base):
    """工作项分配历史。

    action 枚举: assign / transfer / escalate / return
    """

    __tablename__ = "work_item_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_item_id: Mapped[str] = mapped_column(String(32), ForeignKey("work_items.id", ondelete="CASCADE"), index=True, nullable=False)
    from_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HandoverRecord(Base):
    """交接记录。

    status 枚举: pending / confirmed / completed
    """

    __tablename__ = "handover_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="SET NULL"), nullable=True)
    from_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    to_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    scope: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ImportBatch(Base):
    """导入批次。

    source_type: text / excel / image
    status: processing / completed / failed / partial
    """

    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enterprise_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exception_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="processing", nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
