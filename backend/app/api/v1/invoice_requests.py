"""开票请求路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.invoice import InvoiceItem, InvoiceRequest
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.invoice import InvoiceRequestResponse

router = APIRouter(prefix="/invoice-requests", tags=["开票请求"])


@router.get("", response_model=PaginatedResponse[InvoiceRequestResponse], summary="开票请求列表")
async def list_invoice_requests(
    enterprise_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询开票请求列表。"""
    stmt = select(InvoiceRequest).where(InvoiceRequest.tenant_id == current_user.tenant_id)
    if enterprise_id:
        stmt = stmt.where(InvoiceRequest.enterprise_id == enterprise_id)
    if status_filter:
        stmt = stmt.where(InvoiceRequest.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.options(selectinload(InvoiceRequest.items))
        .order_by(InvoiceRequest.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = [InvoiceRequestResponse.model_validate(r) for r in result.scalars().all()]
    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/{request_id}", response_model=InvoiceRequestResponse, summary="开票请求详情")
async def get_invoice_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取开票请求详情（含明细）。"""
    result = await db.execute(
        select(InvoiceRequest)
        .options(selectinload(InvoiceRequest.items))
        .where(
            InvoiceRequest.id == request_id,
            InvoiceRequest.tenant_id == current_user.tenant_id,
        )
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=404, detail="开票请求不存在")
    return InvoiceRequestResponse.model_validate(req)
