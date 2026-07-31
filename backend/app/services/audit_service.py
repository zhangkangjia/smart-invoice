"""审计日志服务。"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    tenant_id: str,
    user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
    trace_id: str | None = None,
) -> AuditLog:
    """记录审计日志。"""
    log_entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_value=before,
        after_value=after,
        ip_address=ip,
        trace_id=trace_id,
    )
    db.add(log_entry)
    await db.flush()
    return log_entry
