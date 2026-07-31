"""文本识别器，支持自然语言开票描述解析。"""

import json
import logging
import re
import time
from typing import Any

import httpx

from app.core.config import settings
from app.services.ai.base import (
    AIRecognizer,
    FieldExtraction,
    RecognitionResult,
)

logger = logging.getLogger(__name__)


# 预期的开票字段列表
INVOICE_FIELDS = [
    "buyer_name",
    "buyer_tax_no",
    "product_name",
    "spec",
    "unit",
    "quantity",
    "unit_price",
    "tax_rate",
    "total_with_tax",
    "invoice_type",
    "receiver_email",
    "receiver_mobile",
    "remark",
    "external_order_no",
]

SYSTEM_PROMPT = """你是一个专业的发票信息提取助手。你的任务是从用户输入的自然语言文本中提取开票所需字段。

你只能从用户输入中提取信息，不能编造税号和银行账号。如果用户没有提供某项信息，对应的值留 null。

请输出严格的 JSON 格式（不要包含 markdown 代码块标记），包含以下字段：
- buyer_name: 购方名称（string | null）
- buyer_tax_no: 购方税号（string | null）
- product_name: 商品或服务名称（string | null）
- spec: 规格型号（string | null）
- unit: 单位（string | null）
- quantity: 数量（number | null）
- unit_price: 单价（number | null）
- tax_rate: 税率，0-1之间的小数，如 0.13 表示13%（number | null）
- total_with_tax: 含税总金额（number | null）
- invoice_type: 发票类型，"special" 增值税专用发票 / "normal" 增值税普通发票 / "electronic_special" 电子专票 / "electronic_normal" 电子普票（string | null）
- receiver_email: 接收发票的邮箱（string | null）
- receiver_mobile: 接收发票的手机号（string | null）
- remark: 备注（string | null）
- external_order_no: 外部订单号（string | null）

如果输入包含多条开票指令，请将结果放在数组中返回：
[{"buyer_name": "...", ...}, {"buyer_name": "...", ...}]

如果只有一条指令，返回单个 JSON 对象。

注意：
1. 不要包含任何 markdown 标记或额外文本
2. 税率必须是 0-1 之间的小数
3. 金额必须为正数
4. 税号通常为 15 或 18 位"""


class TextLLMRecognizer(AIRecognizer):
    """基于大语言模型的文本识别器。"""

    provider_name = "text_llm"

    def __init__(
        self,
        api_url: str = "",
        api_key: str = "",
        model_name: str = "",
        timeout: int = 30,
        max_input_length: int = 10000,
    ):
        self.api_url = api_url or settings.AI_TEXT_API_URL
        self.api_key = api_key or settings.AI_TEXT_API_KEY
        self.model_name = model_name or settings.AI_TEXT_MODEL or "gpt-4o-mini"
        self.timeout = timeout or settings.AI_TIMEOUT_SECONDS
        self.max_input_length = max_input_length or settings.AI_MAX_INPUT_LENGTH

    def _build_messages(self, text: str) -> list[dict[str, str]]:
        """构建 LLM 消息列表。"""
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]

    def _extract_json(self, content: str) -> list[dict[str, Any]]:
        """从 LLM 响应中提取 JSON（可能是对象或数组）。"""
        # 移除可能的 markdown 代码块标记
        cleaned = content.strip()
        if cleaned.startswith("```"):
            # 移除首行 ```json 或 ```
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].rstrip()

        data = json.loads(cleaned)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
        raise ValueError(f"Unexpected JSON type: {type(data)}")

    def _build_result_from_data(
        self, data: dict[str, Any], elapsed_ms: int
    ) -> RecognitionResult:
        """从解析的字典构建 RecognitionResult。"""
        fields: list[FieldExtraction] = []

        # 明确提取的字段置信度更高
        explicit_fields = {
            "buyer_name",
            "buyer_tax_no",
            "product_name",
            "invoice_type",
            "external_order_no",
            "remark",
        }

        for field_name in INVOICE_FIELDS:
            if field_name not in data:
                continue
            value = data[field_name]
            if value is None:
                continue

            # 空字符串视为未提供
            if isinstance(value, str) and not value.strip():
                continue

            # 确定置信度
            confidence = 0.95 if field_name in explicit_fields else 0.7

            fields.append(
                FieldExtraction(
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    source="llm",
                    raw_text=str(value),
                )
            )

        return RecognitionResult(
            success=True,
            fields=fields,
            model_name=self.model_name,
            processing_time_ms=elapsed_ms,
            raw_response=data,
        )

    async def recognize_text(
        self, text: str, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """识别自然语言文本，提取开票字段。"""
        start = time.monotonic()

        # 输入长度检查
        if len(text) > self.max_input_length:
            return RecognitionResult(
                success=False,
                errors=[
                    f"输入文本过长: {len(text)} > {self.max_input_length}"
                ],
            )

        if not self.api_url or not self.api_key:
            return RecognitionResult(
                success=False,
                errors=["未配置 AI 文本识别 API (AI_TEXT_API_URL / AI_TEXT_API_KEY)"],
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": self._build_messages(text),
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.api_url, json=payload, headers=headers
                )
                resp.raise_for_status()
                body = resp.json()

            content = body["choices"][0]["message"]["content"]
            elapsed_ms = int((time.monotonic() - start) * 1000)

            try:
                items = self._extract_json(content)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("JSON 解析失败: %s; content=%s", e, content[:500])
                return RecognitionResult(
                    success=False,
                    errors=[f"AI 响应 JSON 解析失败: {e}"],
                    model_name=self.model_name,
                    processing_time_ms=elapsed_ms,
                    raw_response={"content": content},
                )

            # 取第一条结果（多条开票指令场景由调用方处理）
            if not items:
                return RecognitionResult(
                    success=False,
                    errors=["AI 未返回有效结果"],
                    model_name=self.model_name,
                    processing_time_ms=elapsed_ms,
                )

            result = self._build_result_from_data(items[0], elapsed_ms)
            # 如果有多条指令，把额外的也放进 raw_response
            if len(items) > 1:
                result.raw_response = {"results": items}
            return result

        except httpx.TimeoutException:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("AI 文本识别超时")
            return RecognitionResult(
                success=False,
                errors=["AI 请求超时"],
                model_name=self.model_name,
                processing_time_ms=elapsed_ms,
            )
        except httpx.HTTPStatusError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("AI 文本识别 HTTP 错误: %s", e)
            return RecognitionResult(
                success=False,
                errors=[f"AI 服务返回错误: {e.response.status_code}"],
                model_name=self.model_name,
                processing_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("AI 文本识别异常")
            return RecognitionResult(
                success=False,
                errors=[f"AI 识别异常: {e}"],
                model_name=self.model_name,
                processing_time_ms=elapsed_ms,
            )

    async def recognize_image(
        self, image_bytes: bytes, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """文本识别器不处理图片。"""
        raise NotImplementedError("TextLLMRecognizer 不支持图片识别")


class MockTextRecognizer(AIRecognizer):
    """Mock 文本识别器，使用正则和关键词匹配，用于测试。"""

    provider_name = "text_mock"

    # 常见开票模式: "给XX公司开XX费XX元"
    _pattern_buyer = re.compile(
        r"(?:给|为|帮|请给)\s*([^\s,，。.的]{2,50}?(?:公司|有限公司|有限责任公司|股份|集团|个体|中心|厂|店|部))\s*"
        r"(?:开|代开|开具|开发票)",
        re.IGNORECASE,
    )
    _pattern_amount = re.compile(
        r"(?:金额|共计|合计|总计|开票金额|发票金额)?\s*[:：]?\s*"
        r"(?:人民币\s*)?(?:￥|¥|RMB\s*)?\s*"
        r"([\d,]+(?:\.\d{1,2})?)\s*(?:元|块钱|元整|RMB)",
        re.IGNORECASE,
    )
    _pattern_tax_rate = re.compile(r"税率\s*[:：]?\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
    _pattern_email = re.compile(
        r"(?<![A-Za-z0-9])([A-Za-z0-9][\w.+-]*@[A-Za-z0-9][\w-]*\.[A-Za-z][\w.-]*)",
        re.IGNORECASE,
    )
    _pattern_mobile = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
    _pattern_tax_no = re.compile(r"税号\s*[:：]?\s*([0-9A-Za-z]{15,20})", re.IGNORECASE)
    _pattern_invoice_type_special = re.compile(r"专[用票]|增值税专用", re.IGNORECASE)
    _pattern_invoice_type_normal = re.compile(r"普[通票]|增值税普通", re.IGNORECASE)
    _pattern_product = re.compile(
        r"(?:商品|项目|内容|服务|明细)\s*[:：]?\s*([^\s,，。]{2,100})", re.IGNORECASE
    )
    _pattern_external_order = re.compile(
        r"(?:订单号|订单编号|外部订单)\s*[:：]?\s*([A-Za-z0-9\-_]{4,50})", re.IGNORECASE
    )
    _pattern_quantity = re.compile(r"数量\s*[:：]?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
    _pattern_unit_price = re.compile(
        r"单价\s*[:：]?\s*(?:￥|¥)?\s*(\d+(?:\.\d{1,2})?)", re.IGNORECASE
    )

    async def recognize_text(
        self, text: str, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """使用正则匹配提取字段。"""
        import asyncio

        start = time.monotonic()
        # 模拟一点处理时间
        await asyncio.sleep(0.05)

        fields: list[FieldExtraction] = []

        # 购方名称
        m = self._pattern_buyer.search(text)
        if m:
            fields.append(
                FieldExtraction(
                    field_name="buyer_name",
                    value=m.group(1).strip(),
                    confidence=0.9,
                    source="rule",
                    raw_text=m.group(0),
                )
            )

        # 金额
        m = self._pattern_amount.search(text)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                amount = float(raw)
                fields.append(
                    FieldExtraction(
                        field_name="total_with_tax",
                        value=amount,
                        confidence=0.9,
                        source="rule",
                        raw_text=m.group(0),
                    )
                )
            except ValueError:
                pass

        # 税率
        m = self._pattern_tax_rate.search(text)
        if m:
            try:
                rate = float(m.group(1)) / 100
                if 0 <= rate <= 1:
                    fields.append(
                        FieldExtraction(
                            field_name="tax_rate",
                            value=rate,
                            confidence=0.9,
                            source="rule",
                            raw_text=m.group(0),
                        )
                    )
            except ValueError:
                pass

        # 邮箱
        m = self._pattern_email.search(text)
        if m:
            fields.append(
                FieldExtraction(
                    field_name="receiver_email",
                    value=m.group(1),
                    confidence=0.95,
                    source="rule",
                    raw_text=m.group(1),
                )
            )

        # 手机号
        m = self._pattern_mobile.search(text)
        if m:
            fields.append(
                FieldExtraction(
                    field_name="receiver_mobile",
                    value=m.group(0),
                    confidence=0.95,
                    source="rule",
                    raw_text=m.group(0),
                )
            )

        # 税号
        m = self._pattern_tax_no.search(text)
        if m:
            fields.append(
                FieldExtraction(
                    field_name="buyer_tax_no",
                    value=m.group(1).upper(),
                    confidence=0.9,
                    source="rule",
                    raw_text=m.group(0),
                )
            )

        # 发票类型
        if self._pattern_invoice_type_special.search(text):
            fields.append(
                FieldExtraction(
                    field_name="invoice_type",
                    value="special",
                    confidence=0.85,
                    source="rule",
                    raw_text=self._pattern_invoice_type_special.search(text).group(0),
                )
            )
        elif self._pattern_invoice_type_normal.search(text):
            fields.append(
                FieldExtraction(
                    field_name="invoice_type",
                    value="normal",
                    confidence=0.85,
                    source="rule",
                    raw_text=self._pattern_invoice_type_normal.search(text).group(0),
                )
            )

        # 商品名称
        m = self._pattern_product.search(text)
        if m:
            fields.append(
                FieldExtraction(
                    field_name="product_name",
                    value=m.group(1).strip(),
                    confidence=0.8,
                    source="rule",
                    raw_text=m.group(0),
                )
            )

        # 外部订单号
        m = self._pattern_external_order.search(text)
        if m:
            fields.append(
                FieldExtraction(
                    field_name="external_order_no",
                    value=m.group(1),
                    confidence=0.9,
                    source="rule",
                    raw_text=m.group(0),
                )
            )

        # 数量
        m = self._pattern_quantity.search(text)
        if m:
            try:
                qty = float(m.group(1))
                fields.append(
                    FieldExtraction(
                        field_name="quantity",
                        value=qty,
                        confidence=0.85,
                        source="rule",
                        raw_text=m.group(0),
                    )
                )
            except ValueError:
                pass

        # 单价
        m = self._pattern_unit_price.search(text)
        if m:
            try:
                price = float(m.group(1))
                fields.append(
                    FieldExtraction(
                        field_name="unit_price",
                        value=price,
                        confidence=0.85,
                        source="rule",
                        raw_text=m.group(0),
                    )
                )
            except ValueError:
                pass

        # 含税判断
        if re.search(r"含税", text):
            # 如果有金额但没有税率，标记含税
            existing_tax = any(f.field_name == "tax_rate" for f in fields)
            if not existing_tax:
                fields.append(
                    FieldExtraction(
                        field_name="remark",
                        value="含税",
                        confidence=0.7,
                        source="rule",
                        raw_text="含税",
                    )
                )

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return RecognitionResult(
            success=True,
            fields=fields,
            model_name="mock-text-recognizer",
            model_version="1.0",
            processing_time_ms=elapsed_ms,
            raw_response={"extracted_count": len(fields)},
        )

    async def recognize_image(
        self, image_bytes: bytes, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """文本识别器不处理图片。"""
        raise NotImplementedError("MockTextRecognizer 不支持图片识别")


def get_text_recognizer() -> AIRecognizer:
    """根据配置返回文本识别器实例（Mock 或 LLM）。"""
    if settings.AI_USE_MOCK:
        return MockTextRecognizer()
    return TextLLMRecognizer()
