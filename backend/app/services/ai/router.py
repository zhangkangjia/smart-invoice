"""AI 识别路由器，实现模型分级路由。"""

import logging
from typing import Any

from app.core.config import settings
from app.services.ai.base import (
    AIRecognizer,
    FieldExtraction,
    RecognitionResult,
)

logger = logging.getLogger(__name__)


class AIRecognitionRouter:
    """AI 识别路由器。

    根据输入类型和置信度，自动选择合适的识别器。
    """

    def __init__(
        self,
        text_recognizer: AIRecognizer,
        image_recognizer: AIRecognizer,
        multimodal_recognizer: AIRecognizer,
    ):
        self.text_recognizer = text_recognizer
        self.image_recognizer = image_recognizer
        self.multimodal_recognizer = multimodal_recognizer
        self.confidence_threshold = settings.AI_CONFIDENCE_THRESHOLD

    def _is_complex_content(self, content: bytes | str) -> bool:
        """判断内容是否复杂（需要多模态）。

        复杂内容包括：聊天记录截图、多信息图片等。
        """
        if isinstance(content, str):
            # 文本：如果包含多行对话模式（如 "A:", "B:" 等），视为复杂
            import re

            if re.search(r"(?:^|\n)\s*[\w\u4e00-\u9fff]{1,20}\s*[:：]\s*", content):
                return True
            # 超过500字的文本也视为复杂
            if len(content) > 500:
                return True
        return False

    async def recognize(
        self,
        source_type: str,
        content: bytes | str,
        context: dict[str, Any] | None = None,
    ) -> RecognitionResult:
        """路由识别请求。

        Args:
            source_type: "text" / "image" / "multimodal"
            content: 文本字符串或图片字节数据
            context: 额外上下文
        """
        if source_type == "text":
            if self._is_complex_content(content):
                # 复杂文本 -> 多模态
                result = await self.multimodal_recognizer.recognize_text(
                    str(content), context
                )
                if result.success and result.average_confidence() >= self.confidence_threshold:
                    return result
                # 降级到文本识别器
                logger.info("多模态文本识别置信度低，降级到文本识别器")
                return await self.text_recognizer.recognize_text(
                    str(content), context
                )
            # 标准文本 -> text_recognizer
            return await self.text_recognizer.recognize_text(
                str(content), context
            )

        if source_type == "image":
            # 先尝试多模态识别（更强）
            result = await self.multimodal_recognizer.recognize_image(
                content, context
            )
            if result.success and result.average_confidence() >= self.confidence_threshold:
                return result
            # 降级到 OCR
            logger.info("多模态图片识别置信度低，降级到 OCR 识别器")
            return await self.image_recognizer.recognize_image(content, context)

        if source_type == "multimodal":
            return await self.multimodal_recognizer.recognize_image(content, context)

        return RecognitionResult(
            success=False,
            errors=[f"不支持的 source_type: {source_type}"],
        )

    async def recognize_with_fallback(
        self,
        source_type: str,
        content: bytes | str,
        context: dict[str, Any] | None = None,
    ) -> RecognitionResult:
        """带降级的识别。

        第一轮：首选识别器
        置信度低或失败：换备用识别器
        仍失败：返回低置信度结果或错误
        """
        # 第一轮
        primary = await self.recognize(source_type, content, context)

        if primary.success and primary.average_confidence() >= self.confidence_threshold:
            return primary

        # 第二轮：备用识别器
        if source_type == "text":
            # 如果主识别器是多模态，备用用文本
            if self._is_complex_content(content):
                backup = await self.text_recognizer.recognize_text(
                    str(content), context
                )
                if backup.success:
                    return backup
            else:
                # 主识别器是文本，备用用多模态
                backup = await self.multimodal_recognizer.recognize_text(
                    str(content), context
                )
                if backup.success:
                    return backup

        elif source_type == "image":
            # 如果多模态失败，尝试纯 OCR
            if not primary.success:
                ocr_result = await self.image_recognizer.recognize_image(
                    content, context
                )
                if ocr_result.success:
                    return ocr_result
            # 如果 OCR 也失败，尝试多模态
            else:
                mm_result = await self.multimodal_recognizer.recognize_image(
                    content, context
                )
                if mm_result.success and mm_result.average_confidence() > primary.average_confidence():
                    return mm_result

        # 如果至少有部分结果，返回
        if primary.success and primary.fields:
            return primary

        # 最终返回错误
        return RecognitionResult(
            success=False,
            errors=primary.errors or ["所有识别器均未能提取有效信息"],
            fields=primary.fields,
        )


def get_router() -> AIRecognitionRouter:
    """根据配置创建路由器实例。"""
    from app.services.ai.image_recognizer import get_image_recognizer
    from app.services.ai.multimodal_recognizer import (
        MultimodalRecognizer,
        get_multimodal_recognizer,
    )
    from app.services.ai.text_recognizer import get_text_recognizer

    text_recognizer = get_text_recognizer()
    image_recognizer = get_image_recognizer()

    # 多模态识别器：如果未配置 API，也使用文本/图片识别器的 Mock
    multimodal_recognizer = get_multimodal_recognizer()

    return AIRecognitionRouter(
        text_recognizer=text_recognizer,
        image_recognizer=image_recognizer,
        multimodal_recognizer=multimodal_recognizer,
    )
