"""杂项模型：提交链接、保存视图、迁移批次、外部身份。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _gen_uuid


class SubmissionLink(Base):
    """客户网页提交链接。

    link_type 枚举: one_time / permanent / expiring
    """

    __tablename__ = "submission_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    link_type: Mapped[str] = mapped_column(String(20), default="one_time", nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SavedView(Base):
    """用户保存的列表视图。"""

    __tablename__ = "saved_views"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    is_shared: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MigrationBatch(Base):
    """数据迁移批次。"""

    __tablename__ = "migration_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    batch_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExternalIdentity(Base):
    """外部身份映射。"""

    __tablename__ = "external_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    external_system: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
