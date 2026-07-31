"""企业知识库匹配器，在 AI 识别后补全字段。"""

import logging
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import CustomerTitle
from app.models.product import ProductRule
from app.services.ai.base import (
    FieldExtraction,
    RecognitionResult,
)

logger = logging.getLogger(__name__)

# 模糊匹配阈值
_FUZZY_THRESHOLD = 0.8
# AI 高置信度阈值，高于此值不覆盖
_HIGH_CONFIDENCE = 0.9


def _similarity(a: str, b: str) -> float:
    """计算两个字符串的相似度（0-1）。"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def match_customer_title(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
    buyer_name: str,
) -> CustomerTitle | None:
    """匹配客户抬头。

    优先精确匹配，其次模糊匹配（相似度 > 0.8）。
    唯一匹配返回，多个匹配返回 None。
    """
    if not buyer_name:
        return None

    # 精确匹配
    result = await db.execute(
        select(CustomerTitle).where(
            CustomerTitle.tenant_id == tenant_id,
            CustomerTitle.enterprise_id == enterprise_id,
            CustomerTitle.status == "active",
            CustomerTitle.name == buyer_name,
        )
    )
    exact = result.scalars().all()
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        logger.warning("精确匹配到多个客户抬头: %s", buyer_name)
        return None

    # 模糊匹配
    result = await db.execute(
        select(CustomerTitle).where(
            CustomerTitle.tenant_id == tenant_id,
            CustomerTitle.enterprise_id == enterprise_id,
            CustomerTitle.status == "active",
        )
    )
    all_titles = result.scalars().all()

    fuzzy_matches: list[tuple[float, CustomerTitle]] = []
    for title in all_titles:
        score = _similarity(buyer_name, title.name)
        if score >= _FUZZY_THRESHOLD:
            fuzzy_matches.append((score, title))
        # 也检查别名
        if title.alias:
            alias_score = _similarity(buyer_name, title.alias)
            if alias_score >= _FUZZY_THRESHOLD:
                fuzzy_matches.append((alias_score, title))

    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0][1]
    if len(fuzzy_matches) > 1:
        logger.warning(
            "模糊匹配到多个客户抬头: %s, matches=%s",
            buyer_name,
            [(s, t.name) for s, t in fuzzy_matches],
        )
        return None

    return None


async def match_product_rule(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
    product_name: str,
) -> ProductRule | None:
    """匹配商品规则。

    精确匹配 -> 别名匹配 -> 模糊匹配。
    返回标准商品名称、编码、默认税率。
    """
    if not product_name:
        return None

    # 精确匹配
    result = await db.execute(
        select(ProductRule).where(
            ProductRule.tenant_id == tenant_id,
            ProductRule.enterprise_id == enterprise_id,
            ProductRule.status == "active",
            ProductRule.original_name == product_name,
        )
    )
    exact = result.scalars().all()
    if exact:
        return exact[0]

    # 别名匹配
    result = await db.execute(
        select(ProductRule).where(
            ProductRule.tenant_id == tenant_id,
            ProductRule.enterprise_id == enterprise_id,
            ProductRule.status == "active",
        )
    )
    all_rules = result.scalars().all()

    for rule in all_rules:
        if rule.aliases:
            aliases = rule.aliases if isinstance(rule.aliases, list) else []
            if product_name in aliases:
                return rule

    # 模糊匹配
    fuzzy_matches: list[tuple[float, ProductRule]] = []
    for rule in all_rules:
        score = _similarity(product_name, rule.original_name)
        if score >= _FUZZY_THRESHOLD:
            fuzzy_matches.append((score, rule))
        # 也检查标准名
        if rule.standard_name:
            std_score = _similarity(product_name, rule.standard_name)
            if std_score >= _FUZZY_THRESHOLD:
                fuzzy_matches.append((std_score, rule))

    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0][1]
    if len(fuzzy_matches) > 1:
        logger.warning(
            "模糊匹配到多个商品规则: %s, matches=%s",
            product_name,
            [(s, r.original_name) for s, r in fuzzy_matches],
        )
        return None

    return None


async def enrich_recognition(
    db: AsyncSession,
    recognition: RecognitionResult,
    tenant_id: str,
    enterprise_id: str,
) -> RecognitionResult:
    """用知识库补全识别结果。

    - 对每个字段尝试用知识库补全
    - 更新字段来源为 "knowledge_base"
    - 提升置信度
    - 不覆盖 AI 明确提取的高置信度值
    """
    if not recognition.success:
        return recognition

    fields_by_name: dict[str, FieldExtraction] = {}
    for f in recognition.fields:
        fields_by_name[f.field_name] = f

    # 补全客户抬头相关字段
    buyer_name_field = fields_by_name.get("buyer_name")
    buyer_name = buyer_name_field.value if buyer_name_field else None

    title = await match_customer_title(db, tenant_id, enterprise_id, buyer_name)
    if title:
        # 补全税号
        _enrich_field(
            fields_by_name,
            "buyer_tax_no",
            title.tax_no,
            buyer_name_field,
        )
        # 补全地址
        _enrich_field(
            fields_by_name,
            "buyer_address",
            title.address,
            buyer_name_field,
        )
        # 补全电话
        _enrich_field(
            fields_by_name,
            "buyer_phone",
            title.phone,
            buyer_name_field,
        )
        # 补全银行
        _enrich_field(
            fields_by_name,
            "buyer_bank_name",
            title.bank_name,
            buyer_name_field,
        )
        _enrich_field(
            fields_by_name,
            "buyer_bank_account",
            title.bank_account,
            buyer_name_field,
        )
        # 补全邮箱
        _enrich_field(
            fields_by_name,
            "receiver_email",
            title.email,
            buyer_name_field,
        )
        # 补全手机
        _enrich_field(
            fields_by_name,
            "receiver_mobile",
            title.mobile,
            buyer_name_field,
        )

    # 补全商品相关字段
    product_field = fields_by_name.get("product_name")
    product_name = product_field.value if product_field else None

    if product_name:
        rule = await match_product_rule(
            db, tenant_id, enterprise_id, str(product_name)
        )
        if rule:
            # 标准商品名
            _enrich_field(
                fields_by_name,
                "product_name",
                rule.standard_name,
                product_field,
            )
            # 税码
            _enrich_field(
                fields_by_name,
                "tax_code",
                rule.tax_code,
                product_field,
            )
            # 默认税率
            _enrich_field(
                fields_by_name,
                "tax_rate",
                float(rule.default_tax_rate) if rule.default_tax_rate else None,
                product_field,
            )
            # 单位
            _enrich_field(
                fields_by_name,
                "unit",
                rule.unit,
                product_field,
            )
            # 规格
            _enrich_field(
                fields_by_name,
                "spec",
                rule.spec,
                product_field,
            )

    # 重建 fields 列表
    recognition.fields = list(fields_by_name.values())
    return recognition


def _enrich_field(
    fields_by_name: dict[str, FieldExtraction],
    field_name: str,
    value: Any,
    related_field: FieldExtraction | None,
) -> None:
    """补全单个字段。

    如果 AI 未提取（字段不存在）或置信度低，用知识库值补全。
    高置信度（>0.9）的 AI 结果不覆盖。
    """
    if value is None:
        return

    existing = fields_by_name.get(field_name)
    if existing is not None:
        # 已存在，如果置信度很高则不覆盖
        if existing.confidence >= _HIGH_CONFIDENCE:
            return
        # 置信度低，用知识库值覆盖
        existing.value = value
        existing.source = "knowledge_base"
        existing.confidence = max(existing.confidence, 0.9)
        return

    # 不存在，新建
    fields_by_name[field_name] = FieldExtraction(
        field_name=field_name,
        value=value,
        confidence=0.9,
        source="knowledge_base",
        raw_text=str(value),
    )
