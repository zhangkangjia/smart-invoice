"""图片识别器，基于 OCR 提取开票字段。"""

import logging
import time
from typing import Any

from app.services.ai.base import (
    AIRecognizer,
    FieldExtraction,
    RecognitionResult,
)

logger = logging.getLogger(__name__)

# 支持的图片格式魔数
_IMAGE_MAGIC = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"RIFF": "webp",  # 需进一步检查
    b"\x42\x4d": "bmp",
}

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


class ImageRecognizer(AIRecognizer):
    """基于 PaddleOCR 的图片识别器。

    PaddleOCR 使用延迟导入，不可用时降级到 MockImageRecognizer。
    """

    provider_name = "image_ocr"

    def __init__(self, use_angle_cls: bool = True, lang: str = "ch"):
        self.use_angle_cls = use_angle_cls
        self.lang = lang
        self._ocr = None
        self._initialized = False

    def _init_ocr(self) -> bool:
        """延迟初始化 PaddleOCR。返回是否成功。"""
        if self._initialized:
            return self._ocr is not None
        self._initialized = True
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=self.use_angle_cls, lang=self.lang)
            logger.info("PaddleOCR 初始化成功")
            return True
        except ImportError:
            logger.warning("PaddleOCR 未安装，图片识别将降级")
            return False
        except Exception:
            logger.exception("PaddleOCR 初始化失败")
            return False

    @staticmethod
    def _check_image(image_bytes: bytes) -> tuple[bool, str]:
        """检查图片是否合法。"""
        if not image_bytes:
            return False, "图片数据为空"
        if len(image_bytes) > MAX_IMAGE_SIZE:
            return False, f"图片过大: {len(image_bytes)} > {MAX_IMAGE_SIZE}"
        # 检查魔数
        for magic, fmt in _IMAGE_MAGIC.items():
            if image_bytes.startswith(magic):
                return True, fmt
        # WEBP 需要额外检查
        if image_bytes.startswith(b"RIFF") and len(image_bytes) > 12 and image_bytes[8:12] == b"WEBP":
            return True, "webp"
        return False, "不支持的图片格式"

    def _parse_ocr_result(self, ocr_result: list) -> list[FieldExtraction]:
        """解析 PaddleOCR 输出，构建字段列表。"""
        fields: list[FieldExtraction] = []
        if not ocr_result:
            return fields

        all_texts: list[str] = []
        for page in ocr_result:
            if page is None:
                continue
            for line in page:
                # line = [box_coords, (text, confidence)]
                if not line or len(line) < 2:
                    continue
                box = line[0]
                text_info = line[1]
                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                    text = str(text_info[0])
                    conf = float(text_info[1])
                else:
                    text = str(text_info)
                    conf = 0.8

                all_texts.append(text)

                # 计算坐标边界
                positions: dict[str, Any] = {}
                if box and len(box) >= 4:
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    positions = {
                        "x": min(xs),
                        "y": min(ys),
                        "w": max(xs) - min(xs),
                        "h": max(ys) - min(ys),
                    }

                # 简单关键词匹配
                text_lower = text.lower()
                if "税号" in text or "纳税人识别号" in text:
                    # 尝试提取税号
                    import re

                    m = re.search(r"([0-9A-Za-z]{15,20})", text)
                    if m:
                        fields.append(
                            FieldExtraction(
                                field_name="buyer_tax_no",
                                value=m.group(1).upper(),
                                confidence=conf,
                                source="ocr",
                                position=positions,
                                raw_text=text,
                            )
                        )
                elif re.search(r"[\d,]+\.?\d*\s*元", text):
                    m = re.search(r"([\d,]+(?:\.\d{1,2})?)\s*元", text)
                    if m:
                        amount = float(m.group(1).replace(",", ""))
                        if amount > 0:
                            fields.append(
                                FieldExtraction(
                                    field_name="total_with_tax",
                                    value=amount,
                                    confidence=conf,
                                    source="ocr",
                                    position=positions,
                                    raw_text=text,
                                )
                            )

        # 将所有文本作为 raw_response 保存
        if all_texts:
            fields.append(
                FieldExtraction(
                    field_name="_ocr_full_text",
                    value="\n".join(all_texts),
                    confidence=1.0,
                    source="ocr",
                    raw_text="\n".join(all_texts),
                )
            )

        return fields

    async def recognize_image(
        self, image_bytes: bytes, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """识别图片，提取开票字段。"""
        import asyncio

        start = time.monotonic()

        # 图片检查
        ok, msg = self._check_image(image_bytes)
        if not ok:
            return RecognitionResult(
                success=False,
                errors=[f"图片检查失败: {msg}"],
            )

        # 初始化 OCR
        if not self._init_ocr():
            # 降级到 Mock
            mock = MockImageRecognizer()
            result = await mock.recognize_image(image_bytes, context)
            result.model_name = "mock-image-recognizer (降级)"
            return result

        try:
            # PaddleOCR 的 predict 是同步方法，需要在线程池中运行
            import tempfile
            import os

            # 写入临时文件
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name

            try:
                result_raw = await asyncio.to_thread(self._ocr.predict, tmp_path)
            finally:
                os.unlink(tmp_path)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            fields = self._parse_ocr_result(result_raw)

            return RecognitionResult(
                success=True,
                fields=fields,
                model_name="paddleocr",
                model_version="1.0",
                processing_time_ms=elapsed_ms,
                raw_response={"ocr_lines": len(fields)},
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception("PaddleOCR 识别失败")
            return RecognitionResult(
                success=False,
                errors=[f"OCR 识别异常: {e}"],
                model_name="paddleocr",
                processing_time_ms=elapsed_ms,
            )

    async def recognize_text(
        self, text: str, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """图片识别器不处理文本。"""
        raise NotImplementedError("ImageRecognizer 不支持文本识别")


class MockImageRecognizer(AIRecognizer):
    """Mock 图片识别器，返回模拟结果。"""

    provider_name = "image_mock"

    async def recognize_image(
        self, image_bytes: bytes, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """返回模拟识别结果。"""
        import asyncio

        start = time.monotonic()
        await asyncio.sleep(0.1)

        fields = [
            FieldExtraction(
                field_name="buyer_name",
                value="测试科技有限公司",
                confidence=0.85,
                source="ocr",
                position={"page": 1, "x": 100, "y": 50, "w": 300, "h": 40},
                raw_text="测试科技有限公司",
            ),
            FieldExtraction(
                field_name="buyer_tax_no",
                value="91110108TEST00000X",
                confidence=0.8,
                source="ocr",
                position={"page": 1, "x": 100, "y": 100, "w": 250, "h": 30},
                raw_text="91110108TEST00000X",
            ),
            FieldExtraction(
                field_name="product_name",
                value="技术服务费",
                confidence=0.75,
                source="ocr",
                position={"page": 1, "x": 50, "y": 200, "w": 200, "h": 30},
                raw_text="技术服务费",
            ),
            FieldExtraction(
                field_name="total_with_tax",
                value=10000.00,
                confidence=0.9,
                source="ocr",
                position={"page": 1, "x": 400, "y": 200, "w": 150, "h": 30},
                raw_text="10,000.00",
            ),
            FieldExtraction(
                field_name="tax_rate",
                value=0.06,
                confidence=0.7,
                source="ocr",
                position={"page": 1, "x": 350, "y": 200, "w": 50, "h": 30},
                raw_text="6%",
            ),
        ]

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return RecognitionResult(
            success=True,
            fields=fields,
            model_name="mock-image-recognizer",
            model_version="1.0",
            processing_time_ms=elapsed_ms,
            raw_response={"mock": True, "image_size": len(image_bytes)},
        )

    async def recognize_text(
        self, text: str, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """图片识别器不处理文本。"""
        raise NotImplementedError("MockImageRecognizer 不支持文本识别")


def get_image_recognizer() -> AIRecognizer:
    """根据配置返回图片识别器实例。"""
    from app.core.config import settings

    if settings.AI_USE_MOCK:
        return MockImageRecognizer()
    return ImageRecognizer()
