"""企业服务。"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import ChannelBinding
from app.models.enterprise import Enterprise, EnterpriseConfig, ServiceAssignment
from app.models.invoice_task import ExceptionCase, InvoiceTask
from app.models.product import ProductRule
from app.models.user import User

logger = logging.getLogger(__name__)

# 企业状态机
ENTERPRISE_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["configuring"],
    "configuring": ["observing"],
    "observing": ["simulating", "active", "configuring"],
    "simulating": ["pending_approval", "observing"],
    "pending_approval": ["active", "simulating"],
    "active": ["suspended", "terminated"],
    "suspended": ["active", "terminated"],
    "terminated": ["archived"],
    "archived": [],
}


async def create_enterprise(
    db: AsyncSession,
    tenant_id: str,
    data: dict[str, Any],
    created_by: str | None = None,
) -> Enterprise:
    """创建企业并初始化配置。"""
    enterprise = Enterprise(
        tenant_id=tenant_id,
        name=data["name"],
        tax_no=data.get("tax_no"),
        address=data.get("address"),
        phone=data.get("phone"),
        bank_name=data.get("bank_name"),
        bank_account=data.get("bank_account"),
        status="pending",
        agency_id=data.get("agency_id"),
        branch_id=data.get("branch_id"),
        service_level=data.get("service_level", "standard"),
    )
    db.add(enterprise)
    await db.flush()

    # 初始化空配置
    config = EnterpriseConfig(
        tenant_id=tenant_id,
        enterprise_id=enterprise.id,
        invoice_types=["electronic_normal"],
    )
    db.add(config)
    await db.flush()
    return enterprise


async def update_enterprise(
    db: AsyncSession,
    enterprise: Enterprise,
    data: dict[str, Any],
) -> Enterprise:
    """更新企业基本信息。"""
    for field in ("name", "tax_no", "address", "phone", "bank_name", "bank_account", "agency_id", "branch_id", "service_level"):
        if field in data and data[field] is not None:
            setattr(enterprise, field, data[field])
    await db.flush()
    return enterprise


async def get_enterprises(
    db: AsyncSession,
    tenant_id: str,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    keyword: str | None = None,
) -> tuple[list[Enterprise], int]:
    """分页查询企业列表。"""
    stmt = select(Enterprise).where(Enterprise.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(Enterprise.status == status_filter)
    if keyword:
        stmt = stmt.where(
            Enterprise.name.ilike(f"%{keyword}%")
            | Enterprise.tax_no.ilike(f"%{keyword}%")
        )
    stmt = stmt.order_by(Enterprise.created_at.desc())

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def update_enterprise_status(
    db: AsyncSession,
    enterprise: Enterprise,
    new_status: str,
) -> Enterprise:
    """更新企业状态（带状态机校验）。"""
    current = enterprise.status
    allowed = ENTERPRISE_STATUS_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不允许从 '{current}' 转换到 '{new_status}'，允许的状态: {allowed}",
        )
    enterprise.status = new_status
    await db.flush()
    return enterprise


async def get_or_create_config(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
) -> EnterpriseConfig:
    """获取或创建企业配置。"""
    result = await db.execute(
        select(EnterpriseConfig).where(EnterpriseConfig.enterprise_id == enterprise_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = EnterpriseConfig(
            tenant_id=tenant_id,
            enterprise_id=enterprise_id,
        )
        db.add(config)
        await db.flush()
    return config


async def update_enterprise_config(
    db: AsyncSession,
    config: EnterpriseConfig,
    data: dict[str, Any],
) -> EnterpriseConfig:
    """更新企业开票配置。"""
    for field in (
        "invoice_types",
        "default_tax_rate",
        "single_amount_limit",
        "daily_limit",
        "max_concurrency",
        "auto_approve_threshold",
        "split_rules",
        "merge_rules",
        "remark_template",
        "enabled_time_windows",
    ):
        if field in data and data[field] is not None:
            setattr(config, field, data[field])
    await db.flush()
    return config


async def calculate_enterprise_health(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
) -> dict[str, Any]:
    """计算企业健康度评分。

    评分维度：
    - 配置完整度（是否有配置、客户抬头、商品规则）
    - 通道绑定状态
    - 近期异常率
    """
    scores: dict[str, Any] = {}

    # 配置
    config_result = await db.execute(
        select(EnterpriseConfig).where(EnterpriseConfig.enterprise_id == enterprise_id)
    )
    has_config = config_result.scalar_one_or_none() is not None

    # 客户抬头数量
    from app.models.customer import CustomerTitle

    title_count = (
        await db.execute(
            select(func.count())
            .select_from(CustomerTitle)
            .where(
                CustomerTitle.tenant_id == tenant_id,
                CustomerTitle.enterprise_id == enterprise_id,
                CustomerTitle.status == "active",
            )
        )
    ).scalar_one()

    # 商品规则数量
    rule_count = (
        await db.execute(
            select(func.count())
            .select_from(ProductRule)
            .where(
                ProductRule.tenant_id == tenant_id,
                ProductRule.enterprise_id == enterprise_id,
                ProductRule.status == "active",
            )
        )
    ).scalar_one()

    # 通道绑定
    binding_result = await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.tenant_id == tenant_id,
            ChannelBinding.enterprise_id == enterprise_id,
            ChannelBinding.status == "authorized",
        )
    )
    has_channel = binding_result.scalar_one_or_none() is not None

    # 近期异常
    exception_count = (
        await db.execute(
            select(func.count())
            .select_from(ExceptionCase)
            .where(
                ExceptionCase.tenant_id == tenant_id,
                ExceptionCase.enterprise_id == enterprise_id,
                ExceptionCase.status.in_(["open", "processing"]),
            )
        )
    ).scalar_one()

    # 计算各维度分数（0-100）
    config_score = 0
    if has_config:
        config_score += 30
    if title_count > 0:
        config_score += 20
    if rule_count > 0:
        config_score += 20

    channel_score = 50 if has_channel else 0

    task_count = (
        await db.execute(
            select(func.count())
            .select_from(InvoiceTask)
            .where(
                InvoiceTask.tenant_id == tenant_id,
                InvoiceTask.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one()

    if task_count > 0:
        exception_rate = exception_count / task_count
        health_score = max(0, 100 - int(exception_rate * 100))
    else:
        health_score = 100 if exception_count == 0 else max(0, 100 - exception_count * 10)

    overall = (config_score + channel_score + health_score) / 3

    return {
        "overall": round(overall, 1),
        "config_score": config_score,
        "channel_score": channel_score,
        "health_score": health_score,
        "customer_title_count": title_count,
        "product_rule_count": rule_count,
        "open_exception_count": exception_count,
        "has_channel": has_channel,
    }


async def get_service_assignments(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
) -> list[ServiceAssignment]:
    result = await db.execute(
        select(ServiceAssignment)
        .where(
            ServiceAssignment.tenant_id == tenant_id,
            ServiceAssignment.enterprise_id == enterprise_id,
        )
        .order_by(ServiceAssignment.created_at.desc())
    )
    return list(result.scalars().all())


async def assign_service_person(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
    user_id: str,
    role: str,
    assigned_by: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ServiceAssignment:
    """分配服务人员到企业。"""
    assignment = ServiceAssignment(
        tenant_id=tenant_id,
        enterprise_id=enterprise_id,
        user_id=user_id,
        role=role,
        start_at=start_at,
        end_at=end_at,
        assigned_by=assigned_by,
        status="active",
    )
    db.add(assignment)
    await db.flush()
    return assignment
