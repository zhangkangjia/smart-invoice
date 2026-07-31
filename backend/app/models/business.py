"""业务申请与来源单据模型。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _gen_uuid


class BusinessRequest(Base):
    """统一业务申请。

    source_type 枚举: text / image / excel / api / web_link
    urgency 枚举: low / normal / high / urgent
    status: pending / processing / completed / cancelled
    """

    __tablename__ = "business_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_order_no: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    contact_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("customer_contacts.id", ondelete="SET NULL"), nullable=True)
    customer_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgency: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    expected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_handler_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    current_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class SourceDocument(Base):
    """业务申请来源单据。

    doc_type 枚举: text / image / pdf / ofd / excel
    """

    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    business_request_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("business_requests.id", ondelete="CASCADE"), index=True, nullable=True)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ocr_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
