"""企业模型。"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _gen_uuid


class Enterprise(Base):
    """被服务企业。"""

    __tablename__ = "enterprises"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    tax_no: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # pending|configuring|observing|simulating|pending_approval|active|suspended|terminated|archived
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True, nullable=False)
    agency_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("agencies.id", ondelete="SET NULL"), nullable=True)
    branch_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    service_level: Mapped[str] = mapped_column(String(30), default="standard", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class EnterpriseConfig(Base):
    """企业开票配置。"""

    __tablename__ = "enterprise_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_types: Mapped[list[Any] | None] = mapped_column(JSON, default=list, nullable=True)
    default_tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    single_amount_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    daily_limit: Mapped[int | None] = mapped_column(nullable=True)
    max_concurrency: Mapped[int | None] = mapped_column(nullable=True)
    auto_approve_threshold: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    split_rules: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    merge_rules: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    remark_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enabled_time_windows: Mapped[list[Any] | None] = mapped_column(JSON, default=list, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class EnterpriseTemplate(Base):
    """企业配置模板（按行业）。"""

    __tablename__ = "enterprise_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class ServiceAssignment(Base):
    """企业服务人员分配。

    role 枚举: customer_manager / accountant / invoice_clerk / reviewer / customer_service / substitute
    """

    __tablename__ = "service_assignments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
