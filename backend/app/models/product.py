"""商品规则与版本模型。"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _gen_uuid


class ProductRule(Base):
    """商品映射规则：原始名称 -> 标准化名称与税码。"""

    __tablename__ = "product_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    aliases: Mapped[list[Any] | None] = mapped_column(JSON, default=list, nullable=True)
    standard_name: Mapped[str] = mapped_column(String(500), nullable=False)
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remark_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class RuleVersion(Base):
    """规则版本快照。"""

    __tablename__ = "rule_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
