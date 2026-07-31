"""开票通道抽象基类。"""

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ChannelCapability:
    """通道能力描述。"""

    supports_electronic_special: bool = False
    supports_electronic_normal: bool = False
    supports_special: bool = False
    supports_normal: bool = False
    supports_red_invoice: bool = False
    supports_batch: bool = False
    supports_split: bool = False
    max_items_per_invoice: int = 0
    max_amount: float = 0.0
    requires_tax_no: bool = True


@dataclass
class IssueResult:
    """开票提交结果。"""

    success: bool
    channel_business_no: str | None = None
    request_no: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None
    is_unknown: bool = False  # 结果未知


@dataclass
class QueryResult:
    """查询开票结果。"""

    found: bool
    invoice_number: str | None = None
    invoice_code: str | None = None
    invoice_date: datetime | None = None
    file_url: str | None = None
    file_key: str | None = None
    status: str = "unknown"  # success / failed / processing / unknown
    raw_response: dict[str, Any] | None = None


class InvoiceChannel(abc.ABC):
    """开票通道抽象基类。

    所有具体通道实现必须继承此类并实现以下方法。
    """

    provider_code: str = "base"
    provider_name: str = "Base Channel"

    @abc.abstractmethod
    async def issue_invoice(
        self,
        invoice_request: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> IssueResult:
        """提交开票请求到通道。

        Args:
            invoice_request: 开票请求数据（包含购方信息、明细等）
            config: 通道特定配置

        Returns:
            IssueResult
        """
        ...

    @abc.abstractmethod
    async def query_result(
        self,
        channel_business_no: str,
    ) -> QueryResult:
        """查询开票结果。

        Args:
            channel_business_no: 通道返回的业务编号

        Returns:
            QueryResult
        """
        ...

    @abc.abstractmethod
    async def download_file(
        self,
        file_key: str,
    ) -> bytes:
        """下载发票版式文件。

        Args:
            file_key: 文件标识

        Returns:
            文件二进制内容
        """
        ...

    @abc.abstractmethod
    async def check_health(self) -> bool:
        """检查通道健康状态。

        Returns:
            True if healthy
        """
        ...

    @abc.abstractmethod
    def get_capabilities(self) -> ChannelCapability:
        """获取通道能力描述。"""
        ...
