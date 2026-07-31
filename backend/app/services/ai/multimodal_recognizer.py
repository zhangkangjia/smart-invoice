"""多模态识别器，处理复杂截图、聊天记录等。"""

import base64
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

# 复用文本识别器的字段定义
from app.services.ai.text_recognizer import INVOICE_FIELDS

MULTIMODAL_SYSTEM_PROMPT = """你是一个专业的发票信息提取助手。你的任务是从用户提供的图片（截图、聊天记录、单据照片等）中提取开票所需字段。

你只能从图片中提取可见的信息，不能编造税号和银行账号。如果图片中某项信息不可见，对应值留 null。

请输出严格的 JSON 格式（不要包含 markdown 代码块标记），包含以下字段：
- buyer_name: 购方名称（string | null）
- buyer_tax_no: 购方税号（string | null）
- product_name: 商品或服务名称（string | null）
- spec: 规格型号（string | null）
- unit: 单位（string | null）
- quantity: 数量（number | null）
- unit_price: 单价（number | null）
- tax_rate: 税率，0-1之间的小数（number | null）
- total_with_tax: 含税总金额（number | null）
- invoice_type: 发票类型 "special"/"normal"/"electronic_special"/"electronic_normal"（string | null）
- receiver_email: 接收邮箱（string | null）
- receiver_mobile: 接收手机号（string | null）
- remark: 备注（string | null）
- external_order_no: 外部订单号（string | null）

注意：
1. 不要包含任何 markdown 标记或额外文本
2. 税率必须是 0-1 之间的小数
3. 金额必须为正数
4. 如果是聊天记录截图，注意提取多条消息中的信息"""


class MultimodalRecognizer(AIRecognizer):
    """多模态识别器，支持 OpenAI 兼容的多模态 API。"""

    provider_name = "multimodal"

    def __init__(
        self,
        api_url: str = "",
        api_key: str = "",
        model_name: str = "",
        timeout: int = 60,
    ):
        self.api_url = api_url or settings.AI_MULTIMODAL_API_URL
        self.api_key = api_key or settings.AI_MULTIMODAL_API_KEY
        self.model_name = model_name or settings.AI_MULTIMODAL_MODEL or "gpt-4o"
        self.timeout = timeout or (settings.AI_TIMEOUT_SECONDS * 2)

    def _build_image_content(
        self, image_bytes: bytes, text_instruction: str | None = None
    ) -> list[dict[str, Any]]:
        """构建多模态消息内容。"""
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        content: list[dict[str, Any]] = []

        instruction = text_instruction or "请从这张图片中提取开票所需信息。"
        content.append({"type": "text", "text": instruction})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64}",
                    "detail": "high",
                },
            }
        )
        return content

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        """从 LLM 响应中提取 JSON 对象。"""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3].rstrip()
        return json.loads(cleaned)

    def _build_result_from_data(
        self, data: dict[str, Any], elapsed_ms: int
    ) -> RecognitionResult:
        """从解析的字典构建 RecognitionResult。"""
        fields: list[FieldExtraction] = []
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
            if isinstance(value, str) and not value.strip():
                continue
            confidence = 0.95 if field_name in explicit_fields else 0.7
            fields.append(
                FieldExtraction(
                    field_name=field_name,
                    value=value,
                    confidence=confidence,
                    source="multimodal",
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

    async def recognize_image(
        self, image_bytes: bytes, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """识别图片，使用多模态模型理解字段关系。"""
        start = time.monotonic()

        if not self.api_url or not self.api_key:
            return RecognitionResult(
                success=False,
                errors=[
                    "未配置多模态识别 API (AI_MULTIMODAL_API_URL / AI_MULTIMODAL_API_KEY)"
                ],
            )

        text_instruction = None
        if context and context.get("instruction"):
            text_instruction = str(context["instruction"])

        content = self._build_image_content(image_bytes, text_instruction)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": MULTIMODAL_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
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

            response_content = body["choices"][0]["message"]["content"]
            elapsed_ms = int((time.monotonic() - start) * 1000)

            try:
                data = self._extract_json(response_content)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("多模态 JSON 解析失败: %s", e)
                return RecognitionResult(
                    success=False,
                    errors=[f"多模态响应 JSON 解析失败: {e}"],
                    model_name=self.model_name,
                    processing_time_ms=elapsed_ms,
                    raw_response={"content": response_content},
                )

            return self._build_result_from_data(data, elapsed_ms)

        except httpx.TimeoutException:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("多模态识别超时")
            return RecognitionResult(
                success=False,
                errors=["多模态请求超时"],
                model_name=self.model_name,
                processing_time_ms=elapsed_ms,
            )
        except httpx.HTTPStatusError as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("多模态识别 HTTP 错误: %s", e)
            return RecognitionResult(
                success=False,
                errors=[f"多模态服务返回错误: {e.response.status_code}"],
                model_name=self.model_name,
                processing_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("多模态识别异常")
            return RecognitionResult(
                success=False,
                errors=[f"多模态识别异常: {e}"],
                model_name=self.model_name,
                processing_time_ms=elapsed_ms,
            )

    async def recognize_text(
        self, text: str, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """支持复杂聊天记录解析。

        使用多模态 LLM 的文本理解能力来解析复杂聊天记录。
        如果未配置 API，降级到文本识别器。
        """
        start = time.monotonic()

        if not self.api_url or not self.api_key:
            # 降级到文本识别器
            from app.services.ai.text_recognizer import get_text_recognizer

            text_recognizer = get_text_recognizer()
            return await text_recognizer.recognize_text(text, context)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        system_msg = (
            "你是一个专业的发票信息提取助手。你的任务是从复杂的聊天记录或文本中提取开票所需字段。"
            "聊天记录中可能包含多条消息，请综合所有消息提取信息。"
            "你只能从文本中提取信息，不能编造税号和银行账号。"
            "请输出严格的 JSON 格式，不要包含 markdown 代码块标记。"
        )
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text},
            ],
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
                data = self._extract_json(content)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("多模态文本 JSON 解析失败: %s", e)
                return RecognitionResult(
                    success=False,
                    errors=[f"响应 JSON 解析失败: {e}"],
                    model_name=self.model_name,
                    processing_time_ms=elapsed_ms,
                )

            return self._build_result_from_data(data, elapsed_ms)

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("多模态文本识别异常")
            return RecognitionResult(
                success=False,
                errors=[f"多模态文本识别异常: {e}"],
                model_name=self.model_name,
                processing_time_ms=elapsed_ms,
            )


def get_multimodal_recognizer() -> MultimodalRecognizer:
    """根据配置返回多模态识别器实例。"""
    return MultimodalRecognizer()
