"""AI 安全防护。"""

import re
from typing import Any

from app.core.config import settings

# 文件类型与魔数映射
_FILE_MAGIC = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"\x42\x4d": "bmp",
}

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# 提示注入危险模式
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:previous|above|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(?:previous|above|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(?:previous|above|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+(?:now|actually)\s+(?:a|an)\s+", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"</?system>", re.IGNORECASE),
    re.compile(r"</?assistant>", re.IGNORECASE),
    re.compile(r"</?user>", re.IGNORECASE),
]


def validate_json_schema(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """验证 AI 输出是否符合预期 Schema。

    Returns:
        (是否通过, 错误列表)
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return False, ["输出必须是 JSON 对象"]

    # 税号格式验证（15 或 18 位，字母+数字）
    tax_no = data.get("buyer_tax_no")
    if tax_no is not None:
        if not isinstance(tax_no, str):
            errors.append("buyer_tax_no 必须是字符串")
        elif not re.match(r"^[0-9A-Za-z]{15,18}$", tax_no):
            errors.append(
                f"税号格式不正确: {tax_no} (应为15-18位字母数字)"
            )

    # 金额必须为正数
    for amount_field in ("unit_price", "total_with_tax"):
        val = data.get(amount_field)
        if val is not None:
            try:
                num = float(val)
                if num <= 0:
                    errors.append(f"{amount_field} 必须为正数, 当前值: {val}")
            except (ValueError, TypeError):
                errors.append(f"{amount_field} 必须是数字, 当前值: {val}")

    # 数量必须为正数
    quantity = data.get("quantity")
    if quantity is not None:
        try:
            num = float(quantity)
            if num <= 0:
                errors.append(f"quantity 必须为正数, 当前值: {quantity}")
        except (ValueError, TypeError):
            errors.append(f"quantity 必须是数字, 当前值: {quantity}")

    # 税率在 0-1 之间
    tax_rate = data.get("tax_rate")
    if tax_rate is not None:
        try:
            num = float(tax_rate)
            if num < 0 or num > 1:
                errors.append(f"tax_rate 必须在 0-1 之间, 当前值: {tax_rate}")
        except (ValueError, TypeError):
            errors.append(f"tax_rate 必须是数字, 当前值: {tax_rate}")

    # 发票类型验证
    invoice_type = data.get("invoice_type")
    if invoice_type is not None:
        allowed_types = {"special", "normal", "electronic_special", "electronic_normal"}
        if invoice_type not in allowed_types:
            errors.append(
                f"invoice_type 不在允许列表 {allowed_types}, 当前值: {invoice_type}"
            )

    # 字符串字段长度验证
    length_limits = {
        "buyer_name": 300,
        "product_name": 500,
        "spec": 200,
        "unit": 50,
        "receiver_email": 200,
        "receiver_mobile": 50,
        "remark": 500,
        "external_order_no": 100,
    }
    for field_name, max_len in length_limits.items():
        val = data.get(field_name)
        if val is not None and isinstance(val, str) and len(val) > max_len:
            errors.append(f"{field_name} 长度超过 {max_len}: {len(val)}")

    # 邮箱格式验证
    email = data.get("receiver_email")
    if email is not None and isinstance(email, str) and email:
        if not re.match(r"^[\w.+-]+@[\w-]+\.[\w.-]+$", email):
            errors.append(f"邮箱格式不正确: {email}")

    # 手机号格式验证
    mobile = data.get("receiver_mobile")
    if mobile is not None and isinstance(mobile, str) and mobile:
        if not re.match(r"^1[3-9]\d{9}$", mobile):
            errors.append(f"手机号格式不正确: {mobile}")

    return (len(errors) == 0, errors)


def sanitize_input(text: str) -> str:
    """清理输入文本，移除可能的提示注入内容。

    - 移除提示注入模式
    - 限制输入长度
    - 过滤危险字符
    """
    if not text:
        return ""

    # 限制长度
    max_len = settings.AI_MAX_INPUT_LENGTH
    if len(text) > max_len:
        text = text[:max_len]

    # 移除提示注入模式
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("[FILTERED]", text)

    # 移除 null 字节
    text = text.replace("\x00", "")

    # 移除其他控制字符（保留换行、回车、制表符）
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text.strip()


def check_file_safety(file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """检查文件安全性。

    Returns:
        (是否安全, 错误消息)
    """
    if not file_bytes:
        return False, "文件内容为空"

    # 文件大小检查
    if len(file_bytes) > _MAX_FILE_SIZE:
        return False, f"文件过大: {len(file_bytes)} > {_MAX_FILE_SIZE} bytes"

    # 扩展名检查
    import os

    ext = os.path.splitext(filename.lower())[1]
    if ext and ext not in _ALLOWED_EXTENSIONS:
        return False, f"不支持的文件扩展名: {ext}, 允许: {_ALLOWED_EXTENSIONS}"

    # 魔数检查
    detected = None
    for magic, fmt in _FILE_MAGIC.items():
        if file_bytes.startswith(magic):
            detected = fmt
            break

    # WEBP 特殊处理
    if not detected and file_bytes.startswith(b"RIFF") and len(file_bytes) > 12:
        if file_bytes[8:12] == b"WEBP":
            detected = "webp"

    if not detected:
        return False, "无法识别文件类型（魔数检查失败）"

    return True, detected
