"""开票服务。"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import BusinessRequest
from app.models.enterprise import Enterprise, EnterpriseConfig
from app.models.invoice import InvoiceItem, InvoiceRequest
from app.models.invoice_task import InvoiceTask

logger = logging.getLogger(__name__)


def calculate_invoice_amounts(
    items: list[dict[str, Any]],
    is_tax_inclusive: bool = True,
) -> dict[str, Decimal]:
    """计算开票金额。

    - 含税模式: unit_price 包含税额，需要拆分
    - 不含税模式: unit_price 为不含税金额，税额 = 金额 × 税率

    返回:
        {
            "total_amount": 不含税总金额,
            "total_tax": 总税额,
            "total_with_tax": 含税总金额,
            "items": [...],  # 每行的计算结果
        }
    """
    total_amount = Decimal("0")
    total_tax = Decimal("0")
    total_with_tax = Decimal("0")
    computed_items: list[dict[str, Any]] = []

    for item in items:
        quantity = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))
        tax_rate = Decimal(str(item.get("tax_rate") or 0))
        discount = Decimal(str(item.get("discount_amount") or 0))

        if is_tax_inclusive:
            # 含税: line_total = quantity * unit_price, 然后拆分
            line_total = (quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) - discount
            amount = (line_total / (1 + tax_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax_amount = (line_total - amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            with_tax = line_total
        else:
            # 不含税
            amount = (quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) - discount
            tax_amount = (amount * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            with_tax = (amount + tax_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        total_amount += amount
        total_tax += tax_amount
        total_with_tax += with_tax

        computed_items.append({
            "amount": amount,
            "tax_amount": tax_amount,
            "total_with_tax": with_tax,
        })

    return {
        "total_amount": total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "total_tax": total_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "total_with_tax": total_with_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "items": computed_items,
    }


async def validate_invoice_request(
    db: AsyncSession,
    tenant_id: str,
    enterprise: Enterprise,
    config: EnterpriseConfig,
    data: dict[str, Any],
) -> list[str]:
    """校验开票请求，返回错误信息列表（空列表表示通过）。"""
    errors: list[str] = []

    # 校验发票类型
    invoice_type = data.get("invoice_type")
    allowed_types = config.invoice_types or []
    if allowed_types and invoice_type not in allowed_types:
        errors.append(f"发票类型 '{invoice_type}' 不在允许列表: {allowed_types}")

    # 校验单票金额上限
    total_with_tax = data.get("total_with_tax")
    if config.single_amount_limit and total_with_tax and total_with_tax > config.single_amount_limit:
        errors.append(
            f"开票金额 {total_with_tax} 超过单票上限 {config.single_amount_limit}"
        )

    # 校验企业状态
    if enterprise.status != "active":
        errors.append(f"企业状态为 '{enterprise.status}'，不能开票")

    # 校验购方信息
    if not data.get("buyer_name"):
        errors.append("购方名称不能为空")

    # 校验明细
    items = data.get("items", [])
    if not items:
        errors.append("至少需要一条明细")

    for i, item in enumerate(items):
        if not item.get("product_name"):
            errors.append(f"第 {i + 1} 行商品名称为空")
        if Decimal(str(item.get("quantity") or 0)) <= 0:
            errors.append(f"第 {i + 1} 行数量必须大于 0")
        if Decimal(str(item.get("unit_price") or 0)) <= 0:
            errors.append(f"第 {i + 1} 行单价必须大于 0")

    return errors


async def create_invoice_request_from_business_request(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
    business_request: BusinessRequest,
    invoice_data: dict[str, Any],
    created_by: str | None = None,
) -> InvoiceRequest:
    """从业务申请创建开票请求。"""
    items_data = invoice_data.pop("items", [])
    amounts = calculate_invoice_amounts(
        items_data,
        is_tax_inclusive=invoice_data.get("is_tax_inclusive", True),
    )

    invoice_request = InvoiceRequest(
        tenant_id=tenant_id,
        enterprise_id=enterprise_id,
        business_request_id=business_request.id,
        invoice_type=invoice_data["invoice_type"],
        buyer_name=invoice_data["buyer_name"],
        buyer_tax_no=invoice_data.get("buyer_tax_no"),
        buyer_address=invoice_data.get("buyer_address"),
        buyer_phone=invoice_data.get("buyer_phone"),
        buyer_bank_name=invoice_data.get("buyer_bank_name"),
        buyer_bank_account=invoice_data.get("buyer_bank_account"),
        is_tax_inclusive=invoice_data.get("is_tax_inclusive", True),
        total_amount=amounts["total_amount"],
        total_tax=amounts["total_tax"],
        total_with_tax=amounts["total_with_tax"],
        remark=invoice_data.get("remark"),
        receiver_email=invoice_data.get("receiver_email"),
        receiver_mobile=invoice_data.get("receiver_mobile"),
        config_snapshot=invoice_data.get("config_snapshot"),
        status="pending",
    )
    db.add(invoice_request)
    await db.flush()

    # 创建明细
    for item_data, computed in zip(items_data, amounts["items"]):
        item = InvoiceItem(
            invoice_request_id=invoice_request.id,
            product_name=item_data["product_name"],
            tax_code=item_data.get("tax_code"),
            spec=item_data.get("spec"),
            unit=item_data.get("unit"),
            quantity=Decimal(str(item_data["quantity"])),
            unit_price=Decimal(str(item_data["unit_price"])),
            amount=computed["amount"],
            tax_rate=Decimal(str(item_data.get("tax_rate") or 0)),
            tax_amount=computed["tax_amount"],
            total_with_tax=computed["total_with_tax"],
            discount_amount=Decimal(str(item_data.get("discount_amount") or 0)),
        )
        db.add(item)

    await db.flush()
    return invoice_request


async def split_invoice(
    db: AsyncSession,
    tenant_id: str,
    parent_request: InvoiceRequest,
    split_groups: list[list[dict[str, Any]]],
    split_reason: str | None = None,
) -> list[InvoiceRequest]:
    """拆票：将一个开票请求按组拆分为多个子请求。

    Args:
        split_groups: 每组是一个明细列表，每组生成一个子请求
    """
    from app.models.invoice import SplitRelation

    child_requests: list[InvoiceRequest] = []

    for group_items in split_groups:
        amounts = calculate_invoice_amounts(
            group_items,
            is_tax_inclusive=parent_request.is_tax_inclusive,
        )
        child = InvoiceRequest(
            tenant_id=tenant_id,
            enterprise_id=parent_request.enterprise_id,
            business_request_id=parent_request.business_request_id,
            invoice_type=parent_request.invoice_type,
            buyer_name=parent_request.buyer_name,
            buyer_tax_no=parent_request.buyer_tax_no,
            buyer_address=parent_request.buyer_address,
            buyer_phone=parent_request.buyer_phone,
            buyer_bank_name=parent_request.buyer_bank_name,
            buyer_bank_account=parent_request.buyer_bank_account,
            is_tax_inclusive=parent_request.is_tax_inclusive,
            total_amount=amounts["total_amount"],
            total_tax=amounts["total_tax"],
            total_with_tax=amounts["total_with_tax"],
            remark=parent_request.remark,
            receiver_email=parent_request.receiver_email,
            receiver_mobile=parent_request.receiver_mobile,
            status="pending",
        )
        db.add(child)
        await db.flush()

        for item_data, computed in zip(group_items, amounts["items"]):
            item = InvoiceItem(
                invoice_request_id=child.id,
                product_name=item_data["product_name"],
                tax_code=item_data.get("tax_code"),
                spec=item_data.get("spec"),
                unit=item_data.get("unit"),
                quantity=Decimal(str(item_data["quantity"])),
                unit_price=Decimal(str(item_data["unit_price"])),
                amount=computed["amount"],
                tax_rate=Decimal(str(item_data.get("tax_rate") or 0)),
                tax_amount=computed["tax_amount"],
                total_with_tax=computed["total_with_tax"],
                discount_amount=Decimal(str(item_data.get("discount_amount") or 0)),
            )
            db.add(item)

        db.add(SplitRelation(
            tenant_id=tenant_id,
            parent_request_id=parent_request.id,
            child_request_id=child.id,
            split_type="manual",
            split_reason=split_reason,
        ))
        child_requests.append(child)

    await db.flush()
    return child_requests


async def create_invoice_task(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
    invoice_request: InvoiceRequest,
    import_batch_id: str | None = None,
    idempotency_key: str | None = None,
    max_retries: int = 3,
) -> InvoiceTask:
    """为开票请求创建任务。"""
    task = InvoiceTask(
        tenant_id=tenant_id,
        enterprise_id=enterprise_id,
        invoice_request_id=invoice_request.id,
        import_batch_id=import_batch_id,
        idempotency_key=idempotency_key,
        status="pending_validation",
        max_retries=max_retries,
    )
    db.add(task)
    await db.flush()
    return task
