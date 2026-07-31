"""开票请求、明细、拆票/合票关系模型。"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _gen_uuid


class InvoiceRequest(Base):
    """开票请求。

    invoice_type 枚举: special / normal / electronic_special / electronic_normal
    status: pending / submitting / success / failed / cancelled
    """

    __tablename__ = "invoice_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    business_request_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("business_requests.id", ondelete="SET NULL"), nullable=True)
    invoice_type: Mapped[str] = mapped_column(String(30), nullable=False)
    buyer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    buyer_tax_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    buyer_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    buyer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    buyer_bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    buyer_bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_tax_inclusive: Mapped[bool] = mapped_column(default=True, nullable=False)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_with_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    receiver_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    receiver_mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ORM relationships
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice_request",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class InvoiceItem(Base):
    """开票明细行。"""

    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    invoice_request_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    spec: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_with_tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), default=0, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoice_request: Mapped["InvoiceRequest"] = relationship(back_populates="items")


class SplitRelation(Base):
    """拆票关系。"""

    __tablename__ = "split_relations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    parent_request_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    child_request_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    split_type: Mapped[str] = mapped_column(String(50), nullable=False)
    split_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MergeRelation(Base):
    """合票关系。"""

    __tablename__ = "merge_relations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    merged_request_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    source_request_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoice_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    merge_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
