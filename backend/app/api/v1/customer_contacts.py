"""客户联系人路由。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.customer import CustomerContact
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerContactCreate, CustomerContactResponse

router = APIRouter(prefix="/customer-contacts", tags=["客户联系人"])


@router.get("", response_model=PaginatedResponse[CustomerContactResponse], summary="联系人列表")
async def list_contacts(
    enterprise_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询客户联系人列表。"""
    stmt = select(CustomerContact).where(CustomerContact.tenant_id == current_user.tenant_id)
    if enterprise_id:
        stmt = stmt.where(CustomerContact.enterprise_id == enterprise_id)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.order_by(CustomerContact.created_at.desc()).offset(offset).limit(page_size)
    )
    items = [CustomerContactResponse.model_validate(c) for c in result.scalars().all()]
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("", response_model=CustomerContactResponse, status_code=status.HTTP_201_CREATED, summary="创建联系人")
async def create_contact(
    body: CustomerContactCreate,
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建客户联系人。"""
    contact = CustomerContact(
        id=uuid.uuid4().hex,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        customer_title_id=body.customer_title_id,
        name=body.name,
        mobile=body.mobile,
        email=body.email,
        is_primary=body.is_primary,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return CustomerContactResponse.model_validate(contact)


@router.put("/{contact_id}", response_model=CustomerContactResponse, summary="更新联系人")
async def update_contact(
    contact_id: str,
    body: CustomerContactCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新客户联系人。"""
    result = await db.execute(
        select(CustomerContact).where(
            CustomerContact.id == contact_id,
            CustomerContact.tenant_id == current_user.tenant_id,
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")

    contact.customer_title_id = body.customer_title_id
    contact.name = body.name
    contact.mobile = body.mobile
    contact.email = body.email
    contact.is_primary = body.is_primary

    await db.commit()
    await db.refresh(contact)
    return CustomerContactResponse.model_validate(contact)
