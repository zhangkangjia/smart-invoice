"""真实数电发票通道适配器。

基于公开API文档实现的通用框架，支持配置不同的服务商端点。
使用时需要配置服务商提供的 API 地址、AppKey 和 AppSecret。
"""

import hashlib
import hmac
import logging
import random
import string
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.channels.base import (
    ChannelCapability,
    InvoiceChannel,
    IssueResult,
    QueryResult,
)

logger = logging.getLogger(__name__)


class RealInvoiceChannel(InvoiceChannel):
    """真实数电发票通道适配器。

    基于公开API文档实现，支持配置不同的服务商端点。
    使用时需要配置服务商提供的API地址、AppKey和AppSecret。
    """

    provider_code = "real"
    provider_name = "Real Digital Invoice Channel"

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: {
                "api_base_url": "https://api.example.com",
                "app_key": "xxx",
                "app_secret": "xxx",
                "timeout_seconds": 30,
                "max_retries": 3,
            }
        """
        self.api_base_url = config.get("api_base_url", "").rstrip("/")
        self.app_key = config.get("app_key", "")
        self.app_secret = config.get("app_secret", "")
        self.timeout_seconds = config.get("timeout_seconds", 30)
        self.max_retries = config.get("max_retries", 3)

        self._capabilities = ChannelCapability(
            supports_electronic_special=True,
            supports_electronic_normal=True,
            supports_special=True,
            supports_normal=True,
            supports_red_invoice=True,
            supports_batch=True,
            supports_split=True,
            max_items_per_invoice=200,
            max_amount=99999999.99,
            requires_tax_no=True,
        )

    def _generate_signature(self, params: dict[str, Any], timestamp: str, random_str: str) -> str:
        """生成请求签名。

        签名算法：
        1. 按key升序排序参数
        2. 拼接 key=value&key=value 格式字符串
        3. 追加 timestamp 和 random_str
        4. HMAC-SHA256 签名，输出十六进制
        """
        sorted_items = sorted(params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_items)
        sign_content = f"{param_str}&timestamp={timestamp}&nonce={random_str}&app_key={self.app_key}"
        signature = hmac.new(
            self.app_secret.encode("utf-8"),
            sign_content.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    @staticmethod
    def _generate_nonce(length: int = 16) -> str:
        """生成随机字符串。"""
        chars = string.ascii_letters + string.digits
        return "".join(random.choice(chars) for _ in range(length))

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """构建请求头，包含签名、时间戳、随机数。"""
        timestamp = str(int(time.time()))
        nonce = self._generate_nonce()
        # 签名所需的参数（不含文件类参数）
        sign_params: dict[str, Any] = {
            "app_key": self.app_key,
            "timestamp": timestamp,
            "nonce": nonce,
        }
        signature = self._generate_signature(sign_params, timestamp, nonce)

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-App-Key": self.app_key,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
        }
        if extra:
            headers.update(extra)
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """发送请求到通道API。

        Returns:
            响应JSON dict

        Raises:
            httpx.TimeoutException: 超时
            httpx.HTTPStatusError: HTTP错误
            ValueError: 响应解析错误
        """
        url = f"{self.api_base_url}{path}"
        headers = self._build_headers()

        # 将业务参数加入签名
        if json_data or extra_params:
            sign_payload = {}
            if json_data:
                sign_payload.update(json_data)
            if extra_params:
                sign_payload.update(extra_params)
            timestamp = headers["X-Timestamp"]
            nonce = headers["X-Nonce"]
            headers["X-Signature"] = self._generate_signature(sign_payload, timestamp, nonce)

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    if method.upper() == "GET":
                        resp = await client.get(url, headers=headers, params=extra_params)
                    else:
                        resp = await client.request(method, url, headers=headers, json=json_data)

                    resp.raise_for_status()
                    return resp.json()

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning("通道请求超时 attempt=%d/%d url=%s", attempt, self.max_retries, url)
                if attempt < self.max_retries:
                    await _sleep_backoff(attempt)
                continue

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status_code = exc.response.status_code
                # 4xx 错误不重试（认证错误、参数错误等）
                if 400 <= status_code < 500:
                    logger.error("通道请求客户端错误 status=%d url=%s", status_code, url)
                    try:
                        error_body = exc.response.json()
                    except Exception:
                        error_body = {"raw": exc.response.text}
                    return {
                        "_error": True,
                        "_error_type": "client_error",
                        "status_code": status_code,
                        "body": error_body,
                    }
                # 5xx 错误重试
                logger.warning("通道请求服务端错误 status=%d attempt=%d/%d", status_code, attempt, self.max_retries)
                if attempt < self.max_retries:
                    await _sleep_backoff(attempt)
                continue

            except (httpx.RequestError, ValueError) as exc:
                last_exc = exc
                logger.warning("通道请求异常 attempt=%d/%d err=%s", attempt, self.max_retries, str(exc))
                if attempt < self.max_retries:
                    await _sleep_backoff(attempt)
                continue

        # 所有重试失败
        if isinstance(last_exc, httpx.TimeoutException):
            raise last_exc
        if last_exc:
            raise last_exc
        raise RuntimeError("通道请求失败，未知原因")

    async def issue_invoice(
        self,
        invoice_request: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> IssueResult:
        """提交蓝票开具。

        Args:
            invoice_request: 开票请求数据
            config: 通道特定配置（覆盖默认配置）

        Returns:
            IssueResult
        """
        try:
            response = await self._request(
                "POST",
                "/v1/invoices/issue",
                json_data=invoice_request,
            )
        except httpx.TimeoutException:
            logger.error("开票请求超时")
            return IssueResult(
                success=False,
                error_message="通道请求超时",
                is_unknown=True,
            )
        except Exception as exc:
            logger.error("开票请求异常: %s", str(exc))
            return IssueResult(
                success=False,
                error_message=f"通道请求异常: {exc}",
                is_unknown=True,
            )

        # 检查错误响应
        if response.get("_error"):
            error_type = response.get("_error_type", "")
            if error_type == "client_error":
                body = response.get("body", {})
                error_msg = body.get("message") or body.get("error") or "请求参数错误"
                return IssueResult(
                    success=False,
                    error_message=error_msg,
                    raw_response=response,
                )
            return IssueResult(
                success=False,
                error_message="通道服务不可用",
                raw_response=response,
            )

        # 解析正常响应
        code = response.get("code", response.get("return_code", -1))
        if code in (0, "0", "0000", "SUCCESS"):
            data = response.get("data", response)
            return IssueResult(
                success=True,
                channel_business_no=data.get("channel_business_no") or data.get("fpqqlsh"),
                request_no=data.get("request_no") or data.get("fpqqlsh"),
                raw_response=response,
            )
        elif code in ("processing", "PROCESSING", "2001", "2003"):
            # 处理中 —— 结果未知
            data = response.get("data", {})
            return IssueResult(
                success=True,
                channel_business_no=data.get("channel_business_no") or data.get("fpqqlsh"),
                request_no=data.get("request_no"),
                is_unknown=True,
                raw_response=response,
            )
        else:
            error_msg = response.get("message") or response.get("msg") or "开票失败"
            return IssueResult(
                success=False,
                error_message=error_msg,
                raw_response=response,
            )

    async def query_result(self, channel_business_no: str) -> QueryResult:
        """查询开票结果。

        Args:
            channel_business_no: 通道返回的业务编号

        Returns:
            QueryResult
        """
        try:
            response = await self._request(
                "GET",
                f"/v1/invoices/query/{channel_business_no}",
            )
        except httpx.TimeoutException:
            logger.error("查询开票结果超时 no=%s", channel_business_no)
            return QueryResult(found=False, status="unknown")
        except Exception as exc:
            logger.error("查询开票结果异常 no=%s err=%s", channel_business_no, str(exc))
            return QueryResult(found=False, status="unknown")

        if response.get("_error"):
            return QueryResult(found=False, status="unknown", raw_response=response)

        code = response.get("code", response.get("return_code", -1))
        if code not in (0, "0", "0000", "SUCCESS"):
            return QueryResult(found=False, status="unknown", raw_response=response)

        data = response.get("data", response)
        inv_status = str(data.get("status", data.get("fpzt", ""))).upper()

        if inv_status in ("SUCCESS", "00", "0", "VALID", "有效"):
            invoice_date_str = data.get("kprq") or data.get("invoice_date")
            invoice_date = None
            if invoice_date_str:
                try:
                    invoice_date = datetime.fromisoformat(invoice_date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    try:
                        invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        pass

            return QueryResult(
                found=True,
                invoice_number=data.get("fphm") or data.get("invoice_number"),
                invoice_code=data.get("fpdm") or data.get("invoice_code"),
                invoice_date=invoice_date,
                file_url=data.get("pdf_url") or data.get("file_url"),
                file_key=data.get("file_key") or data.get("ofd_url"),
                status="success",
                raw_response=response,
            )
        elif inv_status in ("FAILED", "02", "2", "INVALID", "作废"):
            return QueryResult(
                found=True,
                status="failed",
                raw_response=response,
            )
        elif inv_status in ("PROCESSING", "01", "1", "PENDING"):
            return QueryResult(
                found=True,
                status="processing",
                raw_response=response,
            )
        else:
            return QueryResult(
                found=True,
                status="unknown",
                raw_response=response,
            )

    async def download_file(self, file_key: str) -> bytes:
        """下载版式文件。

        Args:
            file_key: 文件标识

        Returns:
            文件二进制内容
        """
        url = f"{self.api_base_url}/v1/files/download"
        headers = self._build_headers()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(
                    url,
                    headers=headers,
                    params={"file_key": file_key},
                )
                resp.raise_for_status()
                return resp.content
        except httpx.TimeoutException:
            logger.error("下载文件超时 key=%s", file_key)
            raise
        except Exception as exc:
            logger.error("下载文件异常 key=%s err=%s", file_key, str(exc))
            raise

    async def check_health(self) -> bool:
        """检查通道健康状态。"""
        try:
            response = await self._request("GET", "/v1/health")
            if response.get("_error"):
                return False
            code = response.get("code", -1)
            return code in (0, "0", "0000", "SUCCESS")
        except Exception:
            return False

    def get_capabilities(self) -> ChannelCapability:
        """返回通道能力。"""
        return self._capabilities

    async def apply_red_letter(self, original_invoice_no: str, reason: str) -> dict[str, Any]:
        """红字申请。

        Args:
            original_invoice_no: 原蓝字发票号码
            reason: 红字原因

        Returns:
            包含红字信息表编号的dict
        """
        try:
            response = await self._request(
                "POST",
                "/v1/red-letters/apply",
                json_data={
                    "original_invoice_no": original_invoice_no,
                    "reason": reason,
                },
            )
        except Exception as exc:
            logger.error("红字申请异常: %s", str(exc))
            return {"success": False, "error": str(exc)}

        if response.get("_error"):
            return {"success": False, "error": "通道请求失败", "detail": response}

        code = response.get("code", -1)
        if code in (0, "0", "0000", "SUCCESS"):
            data = response.get("data", {})
            return {
                "success": True,
                "red_letter_no": data.get("red_letter_no") or data.get("hxxbh"),
                "raw": response,
            }
        return {
            "success": False,
            "error": response.get("message", "红字申请失败"),
            "raw": response,
        }

    async def issue_red_invoice(self, red_letter_no: str) -> IssueResult:
        """开具负数发票。

        Args:
            red_letter_no: 红字信息表编号

        Returns:
            IssueResult
        """
        try:
            response = await self._request(
                "POST",
                "/v1/invoices/issue-red",
                json_data={"red_letter_no": red_letter_no},
            )
        except httpx.TimeoutException:
            return IssueResult(
                success=False,
                error_message="红字发票请求超时",
                is_unknown=True,
            )
        except Exception as exc:
            return IssueResult(
                success=False,
                error_message=f"红字发票请求异常: {exc}",
                is_unknown=True,
            )

        if response.get("_error"):
            return IssueResult(
                success=False,
                error_message="通道服务不可用",
                raw_response=response,
            )

        code = response.get("code", -1)
        if code in (0, "0", "0000", "SUCCESS"):
            data = response.get("data", {})
            return IssueResult(
                success=True,
                channel_business_no=data.get("channel_business_no"),
                request_no=data.get("request_no"),
                raw_response=response,
            )
        else:
            error_msg = response.get("message", "红字发票开具失败")
            return IssueResult(
                success=False,
                error_message=error_msg,
                raw_response=response,
            )

    async def query_quota(self, tax_no: str) -> dict[str, Any]:
        """查询企业开票额度。

        Args:
            tax_no: 企业税号

        Returns:
            包含额度信息的dict
        """
        try:
            response = await self._request(
                "GET",
                "/v1/quota",
                extra_params={"tax_no": tax_no},
            )
        except Exception as exc:
            logger.error("查询额度异常 tax_no=%s err=%s", tax_no, str(exc))
            return {"success": False, "error": str(exc)}

        if response.get("_error"):
            return {"success": False, "error": "通道请求失败", "detail": response}

        code = response.get("code", -1)
        if code in (0, "0", "0000", "SUCCESS"):
            data = response.get("data", {})
            return {
                "success": True,
                "tax_no": tax_no,
                "total_quota": data.get("total_quota"),
                "used_quota": data.get("used_quota"),
                "remaining_quota": data.get("remaining_quota"),
                "monthly_quota": data.get("monthly_quota"),
                "raw": response,
            }
        return {
            "success": False,
            "error": response.get("message", "查询额度失败"),
            "raw": response,
        }


async def _sleep_backoff(attempt: int) -> None:
    """指数退避等待。"""
    import asyncio

    delay = min(2**attempt, 10)
    await asyncio.sleep(delay)
