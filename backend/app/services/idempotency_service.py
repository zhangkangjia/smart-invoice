"""幂等性服务。"""

import hashlib
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice_task import InvoiceTask

logger = logging.getLogger(__name__)


def generate_idempotency_key(
    tenant_id: str,
    enterprise_id: str,
    external_order_no: str | None,
    buyer_name: str,
    total_amount: str,
    product_summary: str,
) -> str:
    """生成幂等 key。

    基于 tenant + enterprise + external_order_no + buyer + amount + products 的摘要。
    使用 SHA-256 截断作为 key。
    """
    raw = "|".join([
        tenant_id,
        enterprise_id,
        external_order_no or "",
        buyer_name,
        str(total_amount),
        product_summary,
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


async def check_duplicate(
    db: AsyncSession,
    tenant_id: str,
    idempotency_key: str,
) -> InvoiceTask | None:
    """检查是否存在相同幂等 key 的任务。

    返回已存在的任务（如果状态非 terminated），否则 None。
    """
    result = await db.execute(
        select(InvoiceTask).where(
            InvoiceTask.tenant_id == tenant_id,
            InvoiceTask.idempotency_key == idempotency_key,
            InvoiceTask.status != "terminated",
        )
    )
    return result.scalar_one_or_none()


def build_product_summary(items: list[dict[str, Any]]) -> str:
    """构建商品摘要用于幂等 key。"""
    parts: list[str] = []
    for item in items:
        name = item.get("product_name", "")
        qty = str(item.get("quantity", ""))
        price = str(item.get("unit_price", ""))
        parts.append(f"{name}:{qty}:{price}")
    return ",".join(sorted(parts))
