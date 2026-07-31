"""百望云数电发票通道适配器（生产级别）。

基于百望云开放平台正式 API（router/rest 网关）实现：
- 鉴权：用户名+密码+盐值登录，获取 access_token
- 签名：MD5(请求体JSON + appSecret)，大写
- 开票：method=baiwang.s.outputinvoice.invoice
- 查询：method=baiwang.s.outputinvoice.query
- 重推：method=baiwang.s.outputinvoice.retry
- 交付：method=baiwang.s.outputinvoice.push
- 快捷冲红：method=baiwang.s.outputinvoice.fastRed
- 确认单查询：method=baiwang.s.redconfirm.query
- 确认单操作：method=baiwang.s.redconfirm.operate

API 版本: 6.0
沙箱: https://sandbox-openapi.baiwang.com/router/rest
生产: https://openapi.baiwang.com/router/rest
"""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from app.services.channels.base import (
    ChannelCapability,
    InvoiceChannel,
    IssueResult,
    QueryResult,
)

logger = logging.getLogger(__name__)

# 百望云 API 方法名
METHOD_INVOICE = "baiwang.s.outputinvoice.invoice"
METHOD_QUERY = "baiwang.s.outputinvoice.query"
METHOD_RETRY = "baiwang.s.outputinvoice.retry"
METHOD_PUSH = "baiwang.s.outputinvoice.push"
METHOD_FAST_RED = "baiwang.s.outputinvoice.fastRed"
METHOD_RED_QUERY = "baiwang.s.redconfirm.query"
METHOD_RED_OPERATE = "baiwang.s.redconfirm.operate"

API_VERSION = "6.0"


@dataclass
class BaiwangConfig:
    """百望云通道配置。

    从沙箱环境.txt 获取：
        appkey: 1002948
        盐值: 521c0eea19f04367ad20a3be12c9b4bc
        APP-secret: 223998c6-5b76-4724-b5c9-666ff4215b45
        数电账号: 15888888888
        租户管理员账号: admin_3sylog6ryv8cs
        租户管理员密码: Aa2345678@
        销方税号: 338888888888SMB
    """

    app_key: str
    app_secret: str
    user_salt: str = ""           # 盐值（用户盐值，用于密码登录签名）
    username: str = ""            # 租户管理员账号
    password: str = ""            # 租户管理员密码
    tax_no: str = ""              # 默认销方税号
    invoice_terminal_code: str = ""  # 税控终端/数电账号
    api_base_url: str = "https://sandbox-openapi.baiwang.com/router/rest"
    timeout_seconds: int = 30
    # token 缓存（实例级）
    _access_token: str = field(default="", repr=False)
    _token_expires_at: float = field(default=0.0, repr=False)


class BaiwangChannel(InvoiceChannel):
    """百望云数电发票通道适配器（生产级别）。

    支持能力：
    - 数电蓝票开具（增值税专用/普通发票）
    - 开票结果查询
    - 失败重推
    - 发票再次交付（邮件/短信）
    - 快捷冲红
    - 红字确认单查询/操作
    """

    provider_code = "baiwang"
    provider_name = "百望云数电发票"

    def __init__(self, config: BaiwangConfig | dict):
        if isinstance(config, dict):
            # 兼容旧字段名
            if "account_id" in config and "tax_no" not in config:
                config.setdefault("tax_no", config.get("account_id", ""))
            config = BaiwangConfig(**{k: v for k, v in config.items() if k in BaiwangConfig.__dataclass_fields__})
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
        )

    # ------------------------------------------------------------------ #
    # 鉴权 - 密码登录获取 token
    # ------------------------------------------------------------------ #

    async def _get_access_token(self) -> str:
        """获取 access_token（带缓存，提前5分钟刷新）。

        百望云鉴权流程：
        1. 密码签名 = MD5(password + userSalt).upper()
        2. POST /router/rest?method=baiwang.oauth2.passwordLogin
        3. 返回 access_token
        """
        if self.config._access_token and time.time() < self.config._token_expires_at - 300:
            return self.config._access_token

        # 密码签名: MD5(密码 + 盐值)
        pwd_sign = hashlib.md5(
            f"{self.config.password}{self.config.user_salt}".encode("utf-8")
        ).hexdigest().upper()

        params = {
            "method": "baiwang.oauth2.passwordLogin",
            "version": API_VERSION,
            "appKey": self.config.app_key,
            "format": "json",
            "timestamp": str(int(time.time() * 1000)),
            "type": "sync",
            "requestId": str(uuid.uuid4()),
        }
        body = {
            "username": self.config.username,
            "password": pwd_sign,
        }

        try:
            resp = await self._client.post(
                self.config.api_base_url,
                params=params,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success"):
                err = data.get("errorResponse", {})
                raise Exception(
                    f"百望云登录失败: code={err.get('code')}, msg={err.get('message')}"
                )

            token = data["response"]["accessToken"]
            expires_in = data["response"].get("expiresIn", 7200)
            self.config._access_token = token
            self.config._token_expires_at = time.time() + expires_in
            logger.info("百望云 token 获取成功，有效期 %ss", expires_in)
            return token

        except httpx.HTTPError as e:
            logger.error("百望云鉴权网络错误: %s", e)
            raise

    def _calc_sign(self, body_str: str) -> str:
        """计算请求签名。

        百望云签名规则: MD5(请求体JSON + appSecret) 大写
        """
        raw = f"{body_str}{self.config.app_secret}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    async def _request(self, method: str, business_data: dict) -> dict:
        """发送百望云 API 请求。

        Args:
            method: API方法名（如 baiwang.s.outputinvoice.invoice）
            business_data: 业务参数

        Returns:
            百望云返回的完整 JSON
        """
        token = await self._get_access_token()
        timestamp = str(int(time.time() * 1000))
        request_id = str(uuid.uuid4())

        # 业务参数 JSON（sign 签名的对象）
        body_str = json.dumps(business_data, ensure_ascii=False, separators=(",", ":"))
        sign = self._calc_sign(body_str)

        # 公共参数通过 query string 传递
        params = {
            "method": method,
            "version": API_VERSION,
            "appKey": self.config.app_key,
            "format": "json",
            "timestamp": timestamp,
            "token": token,
            "type": "sync",
            "requestId": request_id,
            "sign": sign,
        }

        try:
            resp = await self._client.post(
                self.config.api_base_url,
                params=params,
                content=body_str,
                headers={"Content-Type": "application/json;charset=UTF-8"},
            )
            resp.raise_for_status()
            result = resp.json()

            if not result.get("success"):
                err = result.get("errorResponse", {})
                error_msg = f"百望云API错误: code={err.get('code')}, msg={err.get('message')}"
                if err.get("subCode"):
                    error_msg += f", subCode={err['subCode']}, subMsg={err.get('subMessage')}"
                raise Exception(error_msg)

            return result

        except httpx.TimeoutException:
            logger.error("百望云API超时: %s", method)
            raise
        except httpx.HTTPError as e:
            logger.error("百望云API网络错误 %s: %s", method, e)
            raise

    # ------------------------------------------------------------------ #
    # 开票（蓝票）
    # ------------------------------------------------------------------ #

    async def issue_invoice(
        self, invoice_request: dict, config: dict | None = None
    ) -> IssueResult:
        """提交数电发票开具。

        Args:
            invoice_request: 平台标准开票请求
            config: 额外配置

        Returns:
            IssueResult
        """
        try:
            baiwang_data = self._convert_to_baiwang_format(invoice_request)
            result = await self._request(METHOD_INVOICE, baiwang_data)

            response = result.get("response", {})
            serial_no = response.get("serialNo", "")

            return IssueResult(
                success=True,
                channel_business_no=serial_no,
                request_no=serial_no,
                raw_response=result,
            )

        except httpx.TimeoutException:
            return IssueResult(
                success=False,
                is_unknown=True,
                error_message="百望云开票请求超时，结果未知，请通过查询接口确认",
            )
        except Exception as e:
            return IssueResult(
                success=False,
                is_unknown=False,
                error_message=str(e),
            )

    def _convert_to_baiwang_format(self, req: dict) -> dict:
        """将平台标准开票请求转换为百望云接口格式。

        按百望云 API 文档构建完整请求体。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tax_no = req.get("seller_tax_no") or self.config.tax_no
        terminal = req.get("invoice_terminal_code") or self.config.invoice_terminal_code

        # 发票类型: 1-蓝票, 2-红票
        invoice_type = req.get("invoice_type", "1")
        # 发票种类编码: 01-数电专票, 02-数电普票（默认）
        invoice_type_code = req.get("invoice_type_code", "02")

        # 构建明细列表
        detail_list = []
        for item in req.get("items", []):
            detail = {
                "goodsName": item.get("product_name", ""),
                "goodsCode": item.get("tax_code", ""),
                "goodsSpecification": item.get("spec", ""),
                "goodsUnit": item.get("unit", ""),
                "goodsQuantity": str(item.get("quantity", "")),
                "goodsPrice": str(item.get("unit_price", "")),
                "goodsTaxRate": str(item.get("tax_rate", "0.03")),
                "goodsTotalPrice": str(item.get("amount", "")),
                "goodsTotalTax": str(item.get("tax_amount", "")),
                "goodsTotalPriceTax": str(item.get("total_with_tax", "")),
                "invoiceLineNature": "0",  # 正常行
            }
            detail_list.append(detail)

        data = {
            # 订单信息
            "orderNo": req.get("external_order_no") or f"INV{int(time.time()*1000)}",
            "orderDateTime": now,
            "invoiceTerminalCode": terminal,
            # 销方信息
            "taxNo": tax_no,
            "sellerName": req.get("seller_name", ""),
            "sellerAddress": req.get("seller_address", ""),
            "sellerPhone": req.get("seller_phone", ""),
            "sellerBankName": req.get("seller_bank_name", ""),
            "sellerBankNumber": req.get("seller_bank_account", ""),
            # 开票人
            "drawer": req.get("drawer", ""),
            "payee": req.get("payee", ""),
            "checker": req.get("reviewer", ""),
            # 购方信息
            "buyerName": req.get("buyer_name", ""),
            "buyerTaxNo": req.get("buyer_tax_no", ""),
            "buyerAddress": req.get("buyer_address", ""),
            "buyerTelephone": req.get("buyer_phone", ""),
            "buyerBankName": req.get("buyer_bank_name", ""),
            "buyerBankNumber": req.get("buyer_bank_account", ""),
            # 发票信息
            "invoiceType": invoice_type,
            "invoiceTypeCode": invoice_type_code,
            "invoiceSpecialMark": "00",  # 普通发票
            "priceTaxMark": "0" if not req.get("is_tax_inclusive", True) else "1",
            "invoiceListMark": "0",  # 非清单
            # 交付
            "pushEmail": req.get("push_email", ""),
            "pushPhone": req.get("push_phone", ""),
            # 备注
            "remarks": req.get("remark", ""),
            # 明细
            "invoiceDetailList": detail_list,
            # 扩展
            "ext": {},
        }

        # 红票相关字段
        if invoice_type == "2":
            data["redInvoiceLabel"] = req.get("red_reason", "2")  # 默认开票有误
            data["originalInvoiceCode"] = req.get("original_invoice_code", "")
            data["originalInvoiceNo"] = req.get("original_invoice_no", "")
            data["originalDigitInvoiceNo"] = req.get("original_digit_invoice_no", "")

        # 过滤空值（百望云不希望空字符串）
        return {k: v for k, v in data.items() if v != ""}

    # ------------------------------------------------------------------ #
    # 查询开票结果
    # ------------------------------------------------------------------ #

    async def query_result(self, channel_business_no: str) -> QueryResult:
        """查询开票结果。

        通过申请流水号（serialNo）查询发票状态。
        """
        data = {
            "taxNo": self.config.tax_no,
            "serialNoList": [channel_business_no],
        }
        try:
            result = await self._request(METHOD_QUERY, data)
            response = result.get("response", {})
            invoices = response.get("list", response.get("invoiceList", []))

            if not invoices:
                return QueryResult(
                    found=False,
                    status="processing",
                    raw_response=result,
                )

            inv = invoices[0] if isinstance(invoices, list) else invoices
            # 发票状态: 0-正常, 1-红冲, 2-作废, 3-开具中, 4-失败
            fpzt = str(inv.get("invoiceStatus", inv.get("fpzt", "")))
            status_map = {
                "0": "success",
                "1": "red_flushed",
                "2": "voided",
                "3": "processing",
                "4": "failed",
            }
            status = status_map.get(fpzt, "unknown")

            return QueryResult(
                found=True,
                status=status,
                invoice_number=inv.get("invoiceNo", inv.get("fphm", "")),
                invoice_code=inv.get("invoiceCode", inv.get("fpdm", "")),
                invoice_date=inv.get("invoiceDate", inv.get("kprq", "")),
                file_url=inv.get("pdfUrl", inv.get("fileUrl", "")),
                file_key=inv.get("invoiceNo", ""),
                raw_response=result,
            )
        except Exception as e:
            return QueryResult(
                found=False,
                status="unknown",
                raw_response={"error": str(e)},
            )

    # ------------------------------------------------------------------ #
    # 失败重推
    # ------------------------------------------------------------------ #

    async def retry_invoice(self, serial_no: str) -> IssueResult:
        """开票失败后重新推送。

        Args:
            serial_no: 原开票申请流水号
        """
        data = {
            "taxNo": self.config.tax_no,
            "serialNo": serial_no,
        }
        try:
            result = await self._request(METHOD_RETRY, data)
            response = result.get("response", {})
            return IssueResult(
                success=True,
                channel_business_no=response.get("serialNo", serial_no),
                raw_response=result,
            )
        except httpx.TimeoutException:
            return IssueResult(success=False, is_unknown=True, error_message="重推请求超时")
        except Exception as e:
            return IssueResult(success=False, error_message=str(e))

    # ------------------------------------------------------------------ #
    # 发票交付
    # ------------------------------------------------------------------ #

    async def push_invoice(
        self,
        tax_no: str,
        invoice_code: str = "",
        invoice_no: str = "",
        email: str = "",
        phone: str = "",
    ) -> dict:
        """发票再次交付（邮件/短信）。

        Args:
            tax_no: 销方税号
            invoice_code: 发票代码
            invoice_no: 发票号码
            email: 交付邮箱
            phone: 交付手机
        """
        data = {
            "taxNo": tax_no,
            "invoiceCode": invoice_code,
            "invoiceNo": invoice_no,
            "pushEmail": email,
            "pushPhone": phone,
        }
        data = {k: v for k, v in data.items() if v}
        result = await self._request(METHOD_PUSH, data)
        return result.get("response", {})

    # ------------------------------------------------------------------ #
    # 版式文件下载
    # ------------------------------------------------------------------ #

    async def download_file(self, file_key: str) -> bytes:
        """下载数电发票版式文件（PDF/OFD）。

        通过查询接口获取 PDF 下载 URL，然后下载文件内容。
        """
        query_result = await self.query_result(file_key)
        if query_result.file_url:
            resp = await self._client.get(query_result.file_url)
            resp.raise_for_status()
            return resp.content
        raise Exception("百望云版式文件下载失败：未找到文件URL")

    # ------------------------------------------------------------------ #
    # 快捷冲红
    # ------------------------------------------------------------------ #

    async def fast_red_invoice(
        self,
        order_no: str,
        red_reason: str = "2",
        nsrsbh: str = "",
    ) -> IssueResult:
        """快捷冲红（无需红字确认单，直接红冲）。

        Args:
            order_no: 原蓝票开票单号
            red_reason: 冲红原因 1-销货退回 2-开票有误 3-服务中止 4-销售折让
            nsrsbh: 销方税号
        """
        data = {
            "taxNo": nsrsbh or self.config.tax_no,
            "orderNo": order_no,
            "redInvoiceLabel": red_reason,
        }
        try:
            result = await self._request(METHOD_FAST_RED, data)
            response = result.get("response", {})
            return IssueResult(
                success=True,
                channel_business_no=response.get("serialNo", ""),
                raw_response=result,
            )
        except httpx.TimeoutException:
            return IssueResult(success=False, is_unknown=True, error_message="冲红请求超时")
        except Exception as e:
            return IssueResult(success=False, error_message=str(e))

    # ------------------------------------------------------------------ #
    # 红字确认单
    # ------------------------------------------------------------------ #

    async def query_red_confirm(
        self,
        nsrsbh: str = "",
        page_num: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页查询红字确认单。"""
        data = {
            "taxNo": nsrsbh or self.config.tax_no,
            "operatorType": "1",  # 查询
            "pageNum": str(page_num),
            "pageSize": str(page_size),
        }
        result = await self._request(METHOD_RED_QUERY, data)
        return result.get("response", {})

    async def operate_red_confirm(
        self,
        confirm_no: str,
        operate_type: str = "1",
        nsrsbh: str = "",
    ) -> dict:
        """操作红字确认单（确认/撤销）。

        Args:
            confirm_no: 确认单编号
            operate_type: 1-确认, 2-撤销
        """
        data = {
            "taxNo": nsrsbh or self.config.tax_no,
            "operatorType": operate_type,
            "confirmNo": confirm_no,
        }
        result = await self._request(METHOD_RED_OPERATE, data)
        return result.get("response", {})

    # ------------------------------------------------------------------ #
    # 红冲完整流程（申请确认单 → 开具红票）
    # ------------------------------------------------------------------ #

    async def apply_red_letter(
        self, original_invoice_no: str, reason: str, nsrsbh: str = ""
    ) -> dict:
        """红字确认单申请（快捷冲红的替代方案）。

        使用快捷冲红方式，返回冲红结果。
        """
        result = await self.fast_red_invoice(
            order_no=original_invoice_no,
            red_reason=reason,
            nsrsbh=nsrsbh,
        )
        return {
            "success": result.success,
            "serial_no": result.channel_business_no,
            "error": result.error_message,
        }

    async def issue_red_invoice(self, red_letter_no: str, nsrsbh: str = "") -> IssueResult:
        """开具红字发票（基于红字确认单）。

        快捷冲红已直接完成红冲，此方法保留兼容。
        """
        return IssueResult(
            success=False,
            error_message="请使用 fast_red_invoice 快捷冲红",
        )

    # ------------------------------------------------------------------ #
    # 健康检查
    # ------------------------------------------------------------------ #

    async def check_health(self) -> bool:
        """检查通道健康状态（尝试获取 token）。"""
        try:
            await self._get_access_token()
            return True
        except Exception as e:
            logger.error("百望云健康检查失败: %s", e)
            return False

    # ------------------------------------------------------------------ #
    # 能力
    # ------------------------------------------------------------------ #

    def get_capabilities(self) -> ChannelCapability:
        return ChannelCapability(
            supports_electronic_special=True,
            supports_electronic_normal=True,
            supports_special=True,
            supports_normal=True,
            supports_red_invoice=True,
            supports_batch=True,
            supports_split=True,
            max_items_per_invoice=100,
            max_amount=99999999.99,
            requires_tax_no=True,
        )

    async def close(self):
        """关闭 HTTP 客户端。"""
        await self._client.aclose()
