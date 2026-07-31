"""工作项路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.task import WorkItem
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.task import WorkItemResponse, WorkItemUpdate
from app.services import task_service

router = APIRouter(prefix="/work-items", tags=["工作项"])


class AssignRequest(BaseModel):
    to_user_id: str
    reason: str | None = None


class ResolveRequest(BaseModel):
    handling_note: str | None = None


@router.get("", response_model=PaginatedResponse[WorkItemResponse], summary="我的待办列表")
async def list_my_work_items(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户的待办工作项列表。"""
    items, total = await task_service.get_my_work_items(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        [WorkItemResponse.model_validate(w) for w in items],
        total,
        page,
        page_size,
    )


@router.get("/{work_item_id}", response_model=WorkItemResponse, summary="工作项详情")
async def get_work_item(
    work_item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取工作项详情。"""
    from sqlalchemy import select

    result = await db.execute(
        select(WorkItem).where(
            WorkItem.id == work_item_id,
            WorkItem.tenant_id == current_user.tenant_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="工作项不存在")
    return WorkItemResponse.model_validate(item)


@router.post("/{work_item_id}/assign", response_model=WorkItemResponse, summary="分配工作项")
async def assign_work_item(
    work_item_id: str,
    body: AssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分配工作项给指定用户。"""
    from sqlalchemy import select

    result = await db.execute(
        select(WorkItem).where(
            WorkItem.id == work_item_id,
            WorkItem.tenant_id == current_user.tenant_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="工作项不存在")

    await task_service.assign_work_item(
        db, item, body.to_user_id,
        from_user_id=current_user.id,
        reason=body.reason,
    )
    await db.commit()
    await db.refresh(item)
    return WorkItemResponse.model_validate(item)


@router.post("/{work_item_id}/transfer", response_model=WorkItemResponse, summary="转派工作项")
async def transfer_work_item(
    work_item_id: str,
    body: AssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """转派工作项给其他用户。"""
    from sqlalchemy import select

    result = await db.execute(
        select(WorkItem).where(
            WorkItem.id == work_item_id,
            WorkItem.tenant_id == current_user.tenant_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="工作项不存在")

    await task_service.transfer_work_item(
        db, item, body.to_user_id,
        from_user_id=current_user.id,
        reason=body.reason,
    )
    await db.commit()
    await db.refresh(item)
    return WorkItemResponse.model_validate(item)


@router.post("/{work_item_id}/resolve", response_model=WorkItemResponse, summary="处理完成")
async def resolve_work_item(
    work_item_id: str,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """标记工作项为已处理。"""
    from sqlalchemy import select

    result = await db.execute(
        select(WorkItem).where(
            WorkItem.id == work_item_id,
            WorkItem.tenant_id == current_user.tenant_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="工作项不存在")

    await task_service.resolve_work_item(
        db, item,
        handling_note=body.handling_note,
        resolved_by=current_user.id,
    )
    await db.commit()
    await db.refresh(item)
    return WorkItemResponse.model_validate(item)
