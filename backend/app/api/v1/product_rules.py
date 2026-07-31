"""商品规则路由。"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.product import ProductRule
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.product import ProductRuleCreate, ProductRuleResponse, ProductRuleUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/product-rules", tags=["商品规则"])


@router.get("", response_model=PaginatedResponse[ProductRuleResponse], summary="商品规则列表")
async def list_product_rules(
    enterprise_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询商品规则列表。"""
    stmt = select(ProductRule).where(ProductRule.tenant_id == current_user.tenant_id)
    if enterprise_id:
        stmt = stmt.where(ProductRule.enterprise_id == enterprise_id)
    if keyword:
        stmt = stmt.where(
            ProductRule.original_name.ilike(f"%{keyword}%")
            | ProductRule.standard_name.ilike(f"%{keyword}%")
        )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.order_by(ProductRule.created_at.desc()).offset(offset).limit(page_size)
    )
    items = [ProductRuleResponse.model_validate(r) for r in result.scalars().all()]
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("", response_model=ProductRuleResponse, status_code=status.HTTP_201_CREATED, summary="创建商品规则")
async def create_product_rule(
    body: ProductRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建商品映射规则。"""
    rule = ProductRule(
        id=uuid.uuid4().hex,
        tenant_id=current_user.tenant_id,
        enterprise_id=body.enterprise_id,
        original_name=body.original_name,
        aliases=body.aliases,
        standard_name=body.standard_name,
        tax_code=body.tax_code,
        default_tax_rate=body.default_tax_rate,
        unit=body.unit,
        spec=body.spec,
        remark_template=body.remark_template,
        status="active",
    )
    db.add(rule)
    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="create_product_rule",
        entity_type="product_rule",
        entity_id=rule.id,
    )
    await db.commit()
    await db.refresh(rule)
    return ProductRuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=ProductRuleResponse, summary="更新商品规则")
async def update_product_rule(
    rule_id: str,
    body: ProductRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新商品映射规则。"""
    result = await db.execute(
        select(ProductRule).where(
            ProductRule.id == rule_id,
            ProductRule.tenant_id == current_user.tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="商品规则不存在")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="update_product_rule",
        entity_type="product_rule",
        entity_id=rule.id,
    )
    await db.commit()
    await db.refresh(rule)
    return ProductRuleResponse.model_validate(rule)


@router.post("/batch-import", summary="批量导入商品规则")
async def batch_import_product_rules(
    enterprise_id: str = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """批量导入商品规则（Excel）。"""
    from app.services.excel_service import parse_standard_excel

    file_bytes = await file.read()
    rows = parse_standard_excel(file_bytes)

    success_count = 0
    failure_count = 0
    errors: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):
        original_name = row.get("original_name") or row.get("商品名称")
        standard_name = row.get("standard_name") or row.get("标准名称") or original_name

        if not original_name:
            errors.append({"row": idx, "error": "原始商品名称为空"})
            failure_count += 1
            continue

        rule = ProductRule(
            id=uuid.uuid4().hex,
            tenant_id=current_user.tenant_id,
            enterprise_id=enterprise_id,
            original_name=str(original_name),
            standard_name=str(standard_name),
            tax_code=str(row.get("tax_code")) if row.get("tax_code") else None,
            unit=str(row.get("unit")) if row.get("unit") else None,
            spec=str(row.get("spec")) if row.get("spec") else None,
            status="active",
        )
        db.add(rule)
        success_count += 1

    await db.commit()
    return {
        "total": len(rows),
        "success": success_count,
        "failure": failure_count,
        "errors": errors,
    }


@router.delete("/{rule_id}", summary="删除商品规则")
async def delete_product_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """删除商品映射规则（软删除：标记 status=inactive）。"""
    result = await db.execute(
        select(ProductRule).where(
            ProductRule.id == rule_id,
            ProductRule.tenant_id == current_user.tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="商品规则不存在")

    rule.status = "inactive"
    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="delete_product_rule",
        entity_type="product_rule",
        entity_id=rule.id,
    )
    await db.commit()
    return {"success": True, "id": rule_id}
