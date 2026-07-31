"""模拟开票通道。

用于开发、测试和「模拟」运行模式。
可配置成功率、延迟等参数以模拟真实场景。
"""

import asyncio
import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any

from app.services.channels.base import (
    ChannelCapability,
    InvoiceChannel,
    IssueResult,
    QueryResult,
)

logger = logging.getLogger(__name__)


class MockInvoiceChannel(InvoiceChannel):
    """模拟开票通道。"""

    provider_code = "mock"
    provider_name = "Mock Channel (开发测试用)"

    def __init__(
        self,
        success_rate: float = 1.0,
        min_delay_ms: int = 100,
        max_delay_ms: int = 300,
        unknown_rate: float = 0.0,
        timeout_rate: float = 0.0,
    ):
        """
        Args:
            success_rate: 成功率 (0-1)
            min_delay_ms: 最小延迟毫秒
            max_delay_ms: 最大延迟毫秒
            unknown_rate: 结果未知比例 (0-1)
            timeout_rate: 超时比例 (0-1)
        """
        self.success_rate = success_rate
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.unknown_rate = unknown_rate
        self.timeout_rate = timeout_rate
        self._capabilities = ChannelCapability(
            supports_electronic_special=True,
            supports_electronic_normal=True,
            supports_special=False,
            supports_normal=False,
            supports_red_invoice=False,
            supports_batch=False,
            supports_split=True,
            max_items_per_invoice=100,
            max_amount=99999999.99,
            requires_tax_no=True,
        )
        # 内存存储：channel_business_no -> result data
        self._store: dict[str, dict[str, Any]] = {}

    async def _delay(self) -> None:
        delay = random.randint(self.min_delay_ms, self.max_delay_ms) / 1000
        await asyncio.sleep(delay)

    async def issue_invoice(
        self,
        invoice_request: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> IssueResult:
        """提交开票请求。"""
        await self._delay()

        # 模拟超时
        if random.random() < self.timeout_rate:
            logger.warning("MockChannel: 模拟超时")
            return IssueResult(
                success=False,
                error_message="通道请求超时",
                is_unknown=False,
            )

        # 生成业务编号
        buyer = invoice_request.get("buyer_name", "")
        total = str(invoice_request.get("total_with_tax", ""))
        request_no = hashlib.sha256(
            f"{buyer}{total}{random.random()}".encode()
        ).hexdigest()[:16]
        channel_business_no = f"MOCK-{request_no}"

        # 模拟结果未知
        if random.random() < self.unknown_rate:
            logger.info("MockChannel: 模拟结果未知 channel_business_no=%s", channel_business_no)
            # 仍然存储，稍后可查询
            self._store[channel_business_no] = {
                "status": "processing",
                "invoice_request": invoice_request,
            }
            return IssueResult(
                success=True,
                channel_business_no=channel_business_no,
                request_no=request_no,
                is_unknown=True,
            )

        # 模拟成功/失败
        if random.random() < self.success_rate:
            # 成功
            invoice_number = f"{random.randint(10000000, 99999999)}"
            invoice_code = f"{random.randint(10000000, 99999999)}"
            self._store[channel_business_no] = {
                "status": "success",
                "invoice_number": invoice_number,
                "invoice_code": invoice_code,
                "invoice_date": datetime.now(timezone.utc).isoformat(),
                "total_amount": invoice_request.get("total_amount"),
                "total_tax": invoice_request.get("total_tax"),
                "total_with_tax": invoice_request.get("total_with_tax"),
                "buyer_name": invoice_request.get("buyer_name"),
                "seller_name": "Mock Enterprise Co., Ltd.",
                "file_key": f"mock/{channel_business_no}.pdf",
            }
            logger.info("MockChannel: 开票成功 no=%s", channel_business_no)
            return IssueResult(
                success=True,
                channel_business_no=channel_business_no,
                request_no=request_no,
            )
        else:
            # 失败
            error_msgs = [
                "购方税号校验失败",
                "商品编码不在允许范围",
                "开票金额超过单张限额",
                "通道服务暂时不可用",
                "企业授权已过期",
            ]
            error = random.choice(error_msgs)
            self._store[channel_business_no] = {
                "status": "failed",
                "error_message": error,
            }
            logger.warning("MockChannel: 开票失败 no=%s err=%s", channel_business_no, error)
            return IssueResult(
                success=False,
                channel_business_no=channel_business_no,
                request_no=request_no,
                error_message=error,
            )

    async def query_result(
        self,
        channel_business_no: str,
    ) -> QueryResult:
        """查询开票结果。"""
        await self._delay()

        data = self._store.get(channel_business_no)
        if data is None:
            return QueryResult(found=False, status="unknown")

        status = data.get("status", "unknown")
        if status == "success":
            return QueryResult(
                found=True,
                invoice_number=data.get("invoice_number"),
                invoice_code=data.get("invoice_code"),
                invoice_date=datetime.fromisoformat(data["invoice_date"]) if data.get("invoice_date") else None,
                file_key=data.get("file_key"),
                status="success",
            )
        elif status == "failed":
            return QueryResult(
                found=True,
                status="failed",
            )
        else:
            # processing -> 模拟一定概率转为成功
            if random.random() < 0.7:
                invoice_number = f"{random.randint(10000000, 99999999)}"
                invoice_code = f"{random.randint(10000000, 99999999)}"
                data["status"] = "success"
                data["invoice_number"] = invoice_number
                data["invoice_code"] = invoice_code
                data["invoice_date"] = datetime.now(timezone.utc).isoformat()
                data["file_key"] = f"mock/{channel_business_no}.pdf"
                return QueryResult(
                    found=True,
                    invoice_number=invoice_number,
                    invoice_code=invoice_code,
                    invoice_date=datetime.fromisoformat(data["invoice_date"]),
                    file_key=data["file_key"],
                    status="success",
                )
            return QueryResult(found=True, status="processing")

    async def download_file(
        self,
        file_key: str,
    ) -> bytes:
        """下载发票文件（返回模拟 PDF 内容）。"""
        await self._delay()
        # 生成一个最小的合法 PDF
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
            b"xref\n0 3\n0000000000 65535 f \n"
            b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
        )
        logger.info("MockChannel: 下载文件 key=%s size=%d", file_key, len(pdf_content))
        return pdf_content

    async def check_health(self) -> bool:
        """检查通道健康状态（总是返回 True）。"""
        return True

    def get_capabilities(self) -> ChannelCapability:
        return self._capabilities
