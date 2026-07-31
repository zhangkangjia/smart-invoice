"""Excel 解析服务。"""

import asyncio
import hashlib
import logging
from io import BytesIO
from typing import Any, AsyncGenerator

import openpyxl
from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)

# 标准模板列名映射
STANDARD_COLUMNS = {
    "企业名称": "enterprise_name",
    "购方名称": "buyer_name",
    "购方税号": "buyer_tax_no",
    "购方地址": "buyer_address",
    "购方电话": "buyer_phone",
    "购方银行": "buyer_bank_name",
    "购方账号": "buyer_bank_account",
    "商品名称": "product_name",
    "规格": "spec",
    "单位": "unit",
    "数量": "quantity",
    "单价": "unit_price",
    "税率": "tax_rate",
    "发票类型": "invoice_type",
    "备注": "remark",
    "接收邮箱": "receiver_email",
    "接收手机": "receiver_mobile",
    "外部订单号": "external_order_no",
}


def parse_standard_excel(file_bytes: bytes) -> list[dict[str, Any]]:
    """解析标准模板 Excel 文件，返回行数据列表。

    每一行对应一条开票请求。
    """
    wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Excel 文件为空",
        )

    header_row = rows[0]
    # 构建列名 -> 列索引映射
    col_map: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        header = str(cell).strip()
        if header in STANDARD_COLUMNS:
            col_map[STANDARD_COLUMNS[header]] = idx

    if "buyer_name" not in col_map or "product_name" not in col_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Excel 缺少必需列: 购方名称、商品名称",
        )

    result: list[dict[str, Any]] = []
    for row_idx, row in enumerate(rows[1:], start=2):
        if all(cell is None for cell in row):
            continue

        row_data: dict[str, Any] = {"_row_number": row_idx}
        for col_name, col_idx in col_map.items():
            value = row[col_idx] if col_idx < len(row) else None
            if value is not None:
                row_data[col_name] = value
        result.append(row_data)

    wb.close()
    return result


async def stream_parse_excel(file_bytes: bytes, batch_size: int = 100) -> AsyncGenerator[list[dict[str, Any]], None]:
    """流式解析 Excel，每次 yield batch_size 条记录。

    适合大文件场景。
    """
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, parse_standard_excel, file_bytes)

    for i in range(0, len(rows), batch_size):
        yield rows[i : i + batch_size]
        # 让出控制权
        await asyncio.sleep(0)


def validate_excel_row(row: dict[str, Any]) -> list[str]:
    """校验单行数据，返回错误信息列表。"""
    errors: list[str] = []
    row_num = row.get("_row_number", "?")

    if not row.get("buyer_name"):
        errors.append(f"第 {row_num} 行: 购方名称为空")

    if not row.get("product_name"):
        errors.append(f"第 {row_num} 行: 商品名称为空")

    quantity = row.get("quantity")
    if quantity is None or float(quantity) <= 0:
        errors.append(f"第 {row_num} 行: 数量必须大于 0")

    unit_price = row.get("unit_price")
    if unit_price is None or float(unit_price) <= 0:
        errors.append(f"第 {row_num} 行: 单价必须大于 0")

    tax_rate = row.get("tax_rate")
    if tax_rate is not None:
        try:
            rate = float(tax_rate)
            if rate < 0 or rate > 1:
                # 如果用户输入的是百分比如 13 而非 0.13，尝试转换
                if rate > 1:
                    row["tax_rate"] = rate / 100
        except (ValueError, TypeError):
            errors.append(f"第 {row_num} 行: 税率格式不正确")

    return errors


async def parse_excel_to_business_requests(
    file: UploadFile,
    tenant_id: str,
    default_enterprise_id: str,
    created_by: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """将 Excel 文件解析为业务请求列表。

    返回:
        (valid_requests, invalid_rows)
    """
    file_bytes = await file.read()
    rows = parse_standard_excel(file_bytes)

    valid_requests: list[dict[str, Any]] = []
    invalid_rows: list[dict[str, Any]] = []

    for row in rows:
        errors = validate_excel_row(row)
        if errors:
            invalid_rows.append({
                "row": row.get("_row_number"),
                "errors": errors,
                "data": {k: v for k, v in row.items() if not k.startswith("_")},
            })
            continue

        # 构造业务请求
        buyer_name = str(row["buyer_name"])
        product_name = str(row["product_name"])
        quantity = str(row["quantity"])
        unit_price = str(row["unit_price"])
        tax_rate = row.get("tax_rate")

        content = (
            f"购方: {buyer_name}\n"
            f"商品: {product_name}, 数量: {quantity}, 单价: {unit_price}\n"
            f"税率: {tax_rate or '默认'}"
        )

        request_data = {
            "enterprise_id": default_enterprise_id,
            "source_type": "excel",
            "external_order_no": row.get("external_order_no"),
            "customer_remark": row.get("remark"),
            "urgency": "normal",
            "content": content,
            "invoice_data": {
                "invoice_type": row.get("invoice_type", "electronic_normal"),
                "buyer_name": buyer_name,
                "buyer_tax_no": row.get("buyer_tax_no"),
                "buyer_address": row.get("buyer_address"),
                "buyer_phone": row.get("buyer_phone"),
                "buyer_bank_name": row.get("buyer_bank_name"),
                "buyer_bank_account": row.get("buyer_bank_account"),
                "receiver_email": row.get("receiver_email"),
                "receiver_mobile": row.get("receiver_mobile"),
                "is_tax_inclusive": True,
                "items": [{
                    "product_name": product_name,
                    "spec": row.get("spec"),
                    "unit": row.get("unit"),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "tax_rate": str(tax_rate) if tax_rate else None,
                }],
            },
        }
        valid_requests.append(request_data)

    return valid_requests, invalid_rows


async def compute_file_hash(file_bytes: bytes) -> str:
    """计算文件 hash。"""
    return hashlib.sha256(file_bytes).hexdigest()
