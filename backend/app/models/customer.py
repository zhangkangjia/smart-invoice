"""客户抬头与联系人模型。"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _gen_uuid


class CustomerTitle(Base):
    """客户开票抬头。"""

    __tablename__ = "customer_titles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    alias: Mapped[str | None] = mapped_column(String(300), nullable=True)
    tax_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class CustomerContact(Base):
    """客户联系人。"""

    __tablename__ = "customer_contacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), ForeignKey("enterprises.id", ondelete="CASCADE"), index=True, nullable=False)
    customer_title_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("customer_titles.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mobile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
