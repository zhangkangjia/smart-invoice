"""AI 识别抽象基类和通用数据结构。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldExtraction:
    """单个字段提取结果。"""

    field_name: str
    value: Any
    confidence: float  # 0.0 - 1.0
    source: str  # "ocr" / "llm" / "multimodal" / "rule" / "knowledge_base"
    position: dict[str, Any] | None = None  # {page, x, y, w, h} 图片坐标
    raw_text: str | None = None  # 原始文本


@dataclass
class RecognitionResult:
    """完整识别结果。"""

    success: bool
    fields: list[FieldExtraction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    model_name: str = ""
    model_version: str = ""
    processing_time_ms: int = 0
    raw_response: dict[str, Any] | None = None

    def get_field(self, name: str) -> FieldExtraction | None:
        """按字段名获取单个提取结果。"""
        for f in self.fields:
            if f.field_name == name:
                return f
        return None

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典。"""
        return {
            "success": self.success,
            "fields": [
                {
                    "field_name": f.field_name,
                    "value": f.value,
                    "confidence": f.confidence,
                    "source": f.source,
                    "position": f.position,
                    "raw_text": f.raw_text,
                }
                for f in self.fields
            ],
            "errors": self.errors,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "processing_time_ms": self.processing_time_ms,
        }

    def average_confidence(self) -> float:
        """计算所有字段的平均置信度。"""
        if not self.fields:
            return 0.0
        return sum(f.confidence for f in self.fields) / len(self.fields)


class AIRecognizer(ABC):
    """AI 识别器抽象基类。"""

    provider_name: str = "base"

    @abstractmethod
    async def recognize_text(
        self, text: str, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """识别自然语言文本，提取开票字段。"""
        ...

    @abstractmethod
    async def recognize_image(
        self, image_bytes: bytes, context: dict[str, Any] | None = None
    ) -> RecognitionResult:
        """识别图片，提取开票字段。"""
        ...
