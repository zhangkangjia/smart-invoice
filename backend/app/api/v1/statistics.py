"""数据统计路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.business import BusinessRequest
from app.models.enterprise import Enterprise
from app.models.invoice_task import ExceptionCase, InvoiceTask
from app.models.task import WorkItem
from app.models.user import User

router = APIRouter(prefix="/statistics", tags=["数据统计"])


@router.get("/dashboard", summary="工作台统计数据")
async def get_dashboard_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取工作台统计数据。"""
    tenant_id = current_user.tenant_id

    # 企业数
    enterprise_count = (
        await db.execute(
            select(func.count()).select_from(
                select(Enterprise).where(
                    Enterprise.tenant_id == tenant_id,
                    Enterprise.status == "active",
                ).subquery()
            )
        )
    ).scalar_one()

    # 业务申请数
    br_count = (
        await db.execute(
            select(func.count()).select_from(
                select(BusinessRequest).where(
                    BusinessRequest.tenant_id == tenant_id,
                ).subquery()
            )
        )
    ).scalar_one()

    # 开票任务数（按状态）
    task_status_result = await db.execute(
        select(InvoiceTask.status, func.count().label("count"))
        .where(InvoiceTask.tenant_id == tenant_id)
        .group_by(InvoiceTask.status)
    )
    task_status: dict[str, int] = {}
    for status, count in task_status_result.all():
        task_status[status] = count

    total_tasks = sum(task_status.values())

    # 待办工作项
    pending_work_items = (
        await db.execute(
            select(func.count()).select_from(
                select(WorkItem).where(
                    WorkItem.tenant_id == tenant_id,
                    WorkItem.assigned_to == current_user.id,
                    WorkItem.status.in_(["pending", "in_progress", "escalated"]),
                ).subquery()
            )
        )
    ).scalar_one()

    # 未处理异常
    open_exceptions = (
        await db.execute(
            select(func.count()).select_from(
                select(ExceptionCase).where(
                    ExceptionCase.tenant_id == tenant_id,
                    ExceptionCase.status.in_(["open", "processing"]),
                ).subquery()
            )
        )
    ).scalar_one()

    return {
        "enterprise_count": enterprise_count,
        "business_request_count": br_count,
        "invoice_task_count": total_tasks,
        "task_status_breakdown": task_status,
        "pending_work_items": pending_work_items,
        "open_exceptions": open_exceptions,
    }


@router.get("/enterprise/{enterprise_id}", summary="企业统计")
async def get_enterprise_statistics(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取企业统计数据。"""
    tenant_id = current_user.tenant_id

    # 任务状态分布
    task_status_result = await db.execute(
        select(InvoiceTask.status, func.count().label("count"))
        .where(
            InvoiceTask.tenant_id == tenant_id,
            InvoiceTask.enterprise_id == enterprise_id,
        )
        .group_by(InvoiceTask.status)
    )
    task_status: dict[str, int] = {}
    for status, count in task_status_result.all():
        task_status[status] = count

    total_tasks = sum(task_status.values())
    success_tasks = task_status.get("success", 0)
    success_rate = (success_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # 异常统计
    exc_result = await db.execute(
        select(ExceptionCase.exception_type, func.count().label("count"))
        .where(
            ExceptionCase.tenant_id == tenant_id,
            ExceptionCase.enterprise_id == enterprise_id,
        )
        .group_by(ExceptionCase.exception_type)
    )
    exception_summary: dict[str, int] = {}
    for exc_type, count in exc_result.all():
        exception_summary[exc_type] = count

    return {
        "enterprise_id": enterprise_id,
        "total_tasks": total_tasks,
        "success_tasks": success_tasks,
        "success_rate": round(success_rate, 2),
        "task_status_breakdown": task_status,
        "exception_summary": exception_summary,
    }
