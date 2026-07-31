"""SQLAlchemy 2.0 声明式基类与通用 Mixin。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _gen_uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """全局声明式基类。"""


class TimestampMixin:
    """通用时间戳 mixin。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )


class TenantMixin(TimestampMixin):
    """多租户通用 mixin。

    适用于 Tenant 自身之外的所有租户级表。
    """

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=_gen_uuid,
    )
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class EnterpriseMixin(TimestampMixin):
    """企业级表通用 mixin。"""

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=_gen_uuid,
    )
    tenant_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    enterprise_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
