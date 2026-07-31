"""异常处理路由。"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.invoice_task import ExceptionCase
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/exceptions", tags=["异常处理"])


class ResolveRequest(BaseModel):
    resolution: str | None = None
    status: str = "resolved"  # resolved / ignored


class BatchFixRequest(BaseModel):
    exception_ids: list[str]
    resolution: str = "批量修复"


@router.get("", summary="异常列表（按类型聚合）")
async def list_exceptions(
    enterprise_id: str | None = Query(None),
    exception_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询异常工单列表。"""
    stmt = select(ExceptionCase).where(ExceptionCase.tenant_id == current_user.tenant_id)
    if enterprise_id:
        stmt = stmt.where(ExceptionCase.enterprise_id == enterprise_id)
    if exception_type:
        stmt = stmt.where(ExceptionCase.exception_type == exception_type)
    if status_filter:
        stmt = stmt.where(ExceptionCase.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.order_by(ExceptionCase.created_at.desc()).offset(offset).limit(page_size)
    )
    cases = result.scalars().all()

    # 按类型聚合统计
    agg_stmt = (
        select(
            ExceptionCase.exception_type,
            ExceptionCase.status,
            func.count().label("count"),
        )
        .where(ExceptionCase.tenant_id == current_user.tenant_id)
        .group_by(ExceptionCase.exception_type, ExceptionCase.status)
    )
    agg_result = await db.execute(agg_stmt)
    summary: dict[str, dict[str, int]] = {}
    for exc_type, exc_status, count in agg_result.all():
        summary.setdefault(exc_type, {})[exc_status] = count

    return {
        "items": [
            {
                "id": c.id,
                "enterprise_id": c.enterprise_id,
                "invoice_task_id": c.invoice_task_id,
                "exception_type": c.exception_type,
                "description": c.description,
                "auto_fixable": c.auto_fixable,
                "affected_count": c.affected_count,
                "status": c.status,
                "resolved_by": c.resolved_by,
                "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cases
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary,
    }


@router.get("/{exception_id}", summary="异常详情")
async def get_exception(
    exception_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取异常工单详情。"""
    result = await db.execute(
        select(ExceptionCase).where(
            ExceptionCase.id == exception_id,
            ExceptionCase.tenant_id == current_user.tenant_id,
        )
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="异常工单不存在")
    return {
        "id": case.id,
        "enterprise_id": case.enterprise_id,
        "invoice_task_id": case.invoice_task_id,
        "exception_type": case.exception_type,
        "description": case.description,
        "auto_fixable": case.auto_fixable,
        "affected_count": case.affected_count,
        "status": case.status,
        "resolved_by": case.resolved_by,
        "resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }


@router.post("/{exception_id}/resolve", summary="处理异常")
async def resolve_exception(
    exception_id: str,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """处理异常工单。"""
    result = await db.execute(
        select(ExceptionCase).where(
            ExceptionCase.id == exception_id,
            ExceptionCase.tenant_id == current_user.tenant_id,
        )
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="异常工单不存在")

    case.status = body.status
    case.resolved_by = current_user.id
    case.resolved_at = datetime.now(timezone.utc)
    if body.resolution:
        case.description = f"{case.description or ''}\n[处理] {body.resolution}"

    await db.commit()
    return {"message": "异常已处理", "status": case.status}


@router.post("/batch-fix", summary="批量修复")
async def batch_fix_exceptions(
    body: BatchFixRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """批量修复异常工单。"""
    result = await db.execute(
        select(ExceptionCase).where(
            ExceptionCase.tenant_id == current_user.tenant_id,
            ExceptionCase.id.in_(body.exception_ids),
        )
    )
    cases = result.scalars().all()
    now = datetime.now(timezone.utc)
    for case in cases:
        case.status = "resolved"
        case.resolved_by = current_user.id
        case.resolved_at = now
        case.description = f"{case.description or ''}\n[批量修复] {body.resolution}"

    await db.commit()
    return {
        "total": len(body.exception_ids),
        "fixed": len(cases),
        "not_found": len(body.exception_ids) - len(cases),
    }
