"""工作项服务。"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import WorkItem, WorkItemAssignment

logger = logging.getLogger(__name__)


async def create_work_item(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str | None,
    business_request_id: str | None,
    work_type: str,
    assigned_to: str | None = None,
    priority: str = "normal",
    exception_reason: str | None = None,
    deadline_at: datetime | None = None,
    created_by: str | None = None,
) -> WorkItem:
    """创建工作项。"""
    work_item = WorkItem(
        tenant_id=tenant_id,
        enterprise_id=enterprise_id,
        business_request_id=business_request_id,
        work_type=work_type,
        assigned_to=assigned_to,
        priority=priority,
        deadline_at=deadline_at,
        status="pending",
        exception_reason=exception_reason,
    )
    db.add(work_item)
    await db.flush()

    # 记录分配历史
    if assigned_to:
        db.add(WorkItemAssignment(
            work_item_id=work_item.id,
            from_user_id=None,
            to_user_id=assigned_to,
            action="assign",
            reason="初始分配",
        ))
    await db.flush()
    return work_item


async def assign_work_item(
    db: AsyncSession,
    work_item: WorkItem,
    to_user_id: str,
    from_user_id: str | None = None,
    reason: str | None = None,
) -> WorkItem:
    """分配工作项。"""
    work_item.assigned_to = to_user_id
    if work_item.status == "pending":
        work_item.status = "in_progress"

    db.add(WorkItemAssignment(
        work_item_id=work_item.id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        action="assign",
        reason=reason,
    ))
    await db.flush()
    return work_item


async def transfer_work_item(
    db: AsyncSession,
    work_item: WorkItem,
    to_user_id: str,
    from_user_id: str | None = None,
    reason: str | None = None,
) -> WorkItem:
    """转派工作项。"""
    old_assignee = work_item.assigned_to
    work_item.assigned_to = to_user_id

    db.add(WorkItemAssignment(
        work_item_id=work_item.id,
        from_user_id=from_user_id or old_assignee,
        to_user_id=to_user_id,
        action="transfer",
        reason=reason,
    ))
    await db.flush()
    return work_item


async def escalate_work_item(
    db: AsyncSession,
    work_item: WorkItem,
    to_user_id: str,
    from_user_id: str | None = None,
    reason: str | None = None,
) -> WorkItem:
    """升级工作项。"""
    work_item.assigned_to = to_user_id
    work_item.status = "escalated"
    if work_item.priority in ("low", "normal"):
        work_item.priority = "high"

    db.add(WorkItemAssignment(
        work_item_id=work_item.id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        action="escalate",
        reason=reason,
    ))
    await db.flush()
    return work_item


async def resolve_work_item(
    db: AsyncSession,
    work_item: WorkItem,
    handling_note: str | None = None,
    resolved_by: str | None = None,
) -> WorkItem:
    """处理完成工作项。"""
    work_item.status = "resolved"
    work_item.handling_note = handling_note

    db.add(WorkItemAssignment(
        work_item_id=work_item.id,
        from_user_id=resolved_by,
        to_user_id=resolved_by,
        action="return",
        reason="处理完成",
    ))
    await db.flush()
    return work_item


async def get_my_work_items(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[WorkItem], int]:
    """获取我的待办工作项。"""
    from sqlalchemy import func

    stmt = select(WorkItem).where(
        WorkItem.tenant_id == tenant_id,
        WorkItem.assigned_to == user_id,
    )
    if status_filter:
        stmt = stmt.where(WorkItem.status == status_filter)
    else:
        # 默认查未完成
        stmt = stmt.where(WorkItem.status.in_(["pending", "in_progress", "escalated"]))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = (
        stmt.order_by(
            # urgent 优先
            WorkItem.priority.desc(),
            WorkItem.created_at.asc(),
        )
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total
