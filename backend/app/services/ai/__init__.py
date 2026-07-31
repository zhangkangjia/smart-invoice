"""AI 识别服务包。"""

from app.services.ai.base import (
    AIRecognizer,
    FieldExtraction,
    RecognitionResult,
)
from app.services.ai.image_recognizer import (
    ImageRecognizer,
    MockImageRecognizer,
    get_image_recognizer,
)
from app.services.ai.knowledge_matcher import (
    enrich_recognition,
    match_customer_title,
    match_product_rule,
)
from app.services.ai.multimodal_recognizer import (
    MultimodalRecognizer,
    get_multimodal_recognizer,
)
from app.services.ai.router import AIRecognitionRouter, get_router
from app.services.ai.safety import (
    check_file_safety,
    sanitize_input,
    validate_json_schema,
)
from app.services.ai.text_recognizer import (
    MockTextRecognizer,
    TextLLMRecognizer,
    get_text_recognizer,
)

__all__ = [
    # base
    "AIRecognizer",
    "FieldExtraction",
    "RecognitionResult",
    # router
    "AIRecognitionRouter",
    "get_router",
    # text
    "TextLLMRecognizer",
    "MockTextRecognizer",
    "get_text_recognizer",
    # image
    "ImageRecognizer",
    "MockImageRecognizer",
    "get_image_recognizer",
    # multimodal
    "MultimodalRecognizer",
    "get_multimodal_recognizer",
    # knowledge_matcher
    "match_customer_title",
    "match_product_rule",
    "enrich_recognition",
    # safety
    "validate_json_schema",
    "sanitize_input",
    "check_file_safety",
]
