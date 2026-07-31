"""客户抬头路由。"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.customer import CustomerTitle
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.customer import CustomerTitleCreate, CustomerTitleResponse, CustomerTitleUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/customer-titles", tags=["客户抬头"])


@router.get("/lookup/by-tax-no", summary="通过税号查询客户抬头信息")
async def lookup_customer_by_tax_no(
    tax_no: str = Query(..., min_length=6, max_length=20, description="纳税人识别号"),
    enterprise_id: str | None = Query(None, description="关联销方企业ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """通过税号查询客户抬头信息。

    1. 先查本地数据库是否已存在该客户抬头
    2. 若不存在，尝试通过百望云通道查询企业基本信息
    3. 百望云未配置时返回税号格式校验结果
    """
    import re
    import logging
    logger = logging.getLogger(__name__)

    tax_no_clean = tax_no.strip().upper()
    if not re.match(r'^[0-9A-Z]{15,20}$', tax_no_clean):
        raise HTTPException(status_code=400, detail="税号格式不正确（应为15-20位字母数字）")

    result_data: dict = {
        "tax_no": tax_no_clean,
        "found_locally": False,
        "found_remote": False,
        "customer_title": None,
        "suggestion": None,
        "message": "",
    }

    # 1. 查本地
    stmt = select(CustomerTitle).where(
        CustomerTitle.tenant_id == current_user.tenant_id,
        CustomerTitle.tax_no == tax_no_clean,
    )
    if enterprise_id:
        stmt = stmt.where(CustomerTitle.enterprise_id == enterprise_id)
    local_result = await db.execute(stmt)
    local_title = local_result.scalar_one_or_none()
    if local_title:
        result_data["found_locally"] = True
        result_data["customer_title"] = CustomerTitleResponse.model_validate(local_title).model_dump()
        result_data["message"] = "该客户抬头已在系统中存在"
        return result_data

    # 2. 尝试百望云查询
    try:
        from app.services.channels.registry import ChannelRegistry
        bw_channel = ChannelRegistry.get("baiwang")
        if bw_channel and hasattr(bw_channel, 'config') and bw_channel.config.app_key:
            remote_info = await bw_channel.query_enterprise_info(tax_no_clean)
            if remote_info:
                result_data["found_remote"] = True
                result_data["suggestion"] = {
                    "name": remote_info.get("nsrmc", ""),
                    "tax_no": tax_no_clean,
                    "address": remote_info.get("scjydz", ""),
                    "phone": remote_info.get("lxdh", ""),
                    "bank_name": remote_info.get("khyh", ""),
                    "bank_account": remote_info.get("yhzh", ""),
                }
                result_data["message"] = "已从百望云获取企业信息，请确认后保存"
                return result_data
    except Exception as e:
        logger.warning("百望云客户信息查询失败: %s", e)

    # 3. 未配置或查询失败
    result_data["message"] = "未配置百望云通道或查询失败，请手动填写客户信息"
    return result_data


@router.get("", response_model=PaginatedResponse[CustomerTitleResponse], summary="客户抬头列表")
async def list_customer_titles(
    enterprise_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询客户抬头列表。"""
    stmt = select(CustomerTitle).where(CustomerTitle.tenant_id == current_user.tenant_id)
    if enterprise_id:
        stmt = stmt.where(CustomerTitle.enterprise_id == enterprise_id)
    if keyword:
        stmt = stmt.where(
            CustomerTitle.name.ilike(f"%{keyword}%")
            | CustomerTitle.tax_no.ilike(f"%{keyword}%")
        )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.order_by(CustomerTitle.created_at.desc()).offset(offset).limit(page_size)
    )
    items = [CustomerTitleResponse.model_validate(t) for t in result.scalars().all()]
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("", response_model=CustomerTitleResponse, status_code=status.HTTP_201_CREATED, summary="创建客户抬头")
async def create_customer_title(
    body: CustomerTitleCreate,
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建客户抬头。"""
    title = CustomerTitle(
        id=uuid.uuid4().hex,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        name=body.name,
        alias=body.alias,
        tax_no=body.tax_no,
        address=body.address,
        phone=body.phone,
        bank_name=body.bank_name,
        bank_account=body.bank_account,
        email=body.email,
        mobile=body.mobile,
        status="active",
    )
    db.add(title)
    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="create_customer_title",
        entity_type="customer_title",
        entity_id=title.id,
        after={"name": title.name},
    )
    await db.commit()
    await db.refresh(title)
    return CustomerTitleResponse.model_validate(title)


@router.put("/{title_id}", response_model=CustomerTitleResponse, summary="更新客户抬头")
async def update_customer_title(
    title_id: str,
    body: CustomerTitleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新客户抬头。"""
    result = await db.execute(
        select(CustomerTitle).where(
            CustomerTitle.id == title_id,
            CustomerTitle.tenant_id == current_user.tenant_id,
        )
    )
    title = result.scalar_one_or_none()
    if title is None:
        raise HTTPException(status_code=404, detail="客户抬头不存在")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(title, field, value)

    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="update_customer_title",
        entity_type="customer_title",
        entity_id=title.id,
    )
    await db.commit()
    await db.refresh(title)
    return CustomerTitleResponse.model_validate(title)


@router.delete("/{title_id}", summary="删除客户抬头")
async def delete_customer_title(
    title_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """删除客户抬头（软删除，设为 inactive）。"""
    result = await db.execute(
        select(CustomerTitle).where(
            CustomerTitle.id == title_id,
            CustomerTitle.tenant_id == current_user.tenant_id,
        )
    )
    title = result.scalar_one_or_none()
    if title is None:
        raise HTTPException(status_code=404, detail="客户抬头不存在")

    title.status = "inactive"
    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="delete_customer_title",
        entity_type="customer_title",
        entity_id=title.id,
    )
    await db.commit()
    return {"message": "已删除"}


@router.post("/batch-import", summary="批量导入客户抬头")
async def batch_import_customer_titles(
    enterprise_id: str = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """批量导入客户抬头（Excel）。"""
    from app.services.excel_service import parse_standard_excel

    file_bytes = await file.read()
    rows = parse_standard_excel(file_bytes)

    success_count = 0
    failure_count = 0
    errors: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):
        name = row.get("name") or row.get("购方名称")
        if not name:
            errors.append({"row": idx, "error": "名称为空"})
            failure_count += 1
            continue

        title = CustomerTitle(
            id=uuid.uuid4().hex,
            tenant_id=current_user.tenant_id,
            enterprise_id=enterprise_id,
            name=str(name),
            tax_no=str(row.get("tax_no")) if row.get("tax_no") else None,
            address=str(row.get("address")) if row.get("address") else None,
            phone=str(row.get("phone")) if row.get("phone") else None,
            bank_name=str(row.get("bank_name")) if row.get("bank_name") else None,
            bank_account=str(row.get("bank_account")) if row.get("bank_account") else None,
            email=str(row.get("email")) if row.get("email") else None,
            mobile=str(row.get("mobile")) if row.get("mobile") else None,
            status="active",
        )
        db.add(title)
        success_count += 1

    await db.commit()
    return {
        "total": len(rows),
        "success": success_count,
        "failure": failure_count,
        "errors": errors,
    }
