"""百望云数电发票通道适配器。

基于百望云开放平台公开API文档实现：
- 鉴权：OAuth2.0 client_credentials 模式获取 access_token
- 签名：MD5(Content_MD5 + req_date + access_token + app_secret) -> Base64
- 开票：POST /baiwang/IssueInvoice
- 查询：POST /baiwang/QueryInvoice
- 红冲：POST /baiwang/RedLetterConfirm
- 版式下载：POST /baiwang/DownloadFile

接入前提：
1. 在百望云开放平台注册（https://open.baiwang.com/）
2. 获取 AppKey 和 AppSecret
3. 完成企业产品订购和授权
4. 企业需完成人脸识别认证

文档来源：https://gfyjak742r.apifox.cn/
"""

import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.channels.base import (
    ChannelCapability,
    InvoiceChannel,
    IssueResult,
    QueryResult,
)

logger = logging.getLogger(__name__)


@dataclass
class BaiwangConfig:
    """百望云通道配置。"""

    app_key: str
    app_secret: str
    api_base_url: str = "https://open.baiwang.com"
    account_id: str = ""  # 企业账号ID
    timeout_seconds: int = 30
    # token 缓存
    _access_token: str = ""
    _token_expires_at: float = 0.0

    @property
    def secret_md5(self) -> str:
        """appSecret 的 MD5（32位小写），用于获取 token。"""
        return hashlib.md5(self.app_secret.encode("utf-8")).hexdigest()


class BaiwangChannel(InvoiceChannel):
    """百望云数电发票通道适配器。

    支持能力：
    - 数电蓝票开具（增值税专用/普通发票）
    - 发票结果查询
    - 版式文件下载
    - 红字确认单申请与红冲
    - 企业信息查询
    - 开票统计查询
    - 人脸识别认证（企业授权前置）
    """

    provider_code = "baiwang"
    provider_name = "百望云数电发票"

    def __init__(self, config: BaiwangConfig | dict):
        if isinstance(config, dict):
            config = BaiwangConfig(**config)
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=self.config.api_base_url,
            timeout=self.config.timeout_seconds,
        )

    # ------------------------------------------------------------------ #
    # 鉴权
    # ------------------------------------------------------------------ #

    async def _get_access_token(self) -> str:
        """获取 access_token（带缓存，提前5分钟刷新）。"""
        if self.config._access_token and time.time() < self.config._token_expires_at - 300:
            return self.config._access_token

        url = "/v2/public/oauth2/login"
        body = {
            "grant_type": "client_credentials",
            "client_appkey": self.config.app_key,
            "client_secret": self.config.secret_md5,
        }
        try:
            resp = await self._client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "2000" or not data.get("success"):
                raise Exception(f"百望云鉴权失败: {data.get('message', 'unknown')}")

            token = data["data"]["access_token"]
            # JWT token，解析 exp（简单处理，默认2小时）
            try:
                payload_b64 = token.split(".")[1]
                # 补齐 padding
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload = json.loads(base64.b64decode(payload_b64))
                exp = payload.get("exp", time.time() + 7200)
                self.config._token_expires_at = float(exp)
            except Exception:
                self.config._token_expires_at = time.time() + 7200

            self.config._access_token = token
            logger.info("百望云 access_token 获取成功，有效期至 %s", time.ctime(self.config._token_expires_at))
            return token
        except httpx.HTTPError as e:
            logger.error("百望云鉴权网络错误: %s", e)
            raise

    def _calc_sign(self, method: str, body_str: str, req_date: str, access_token: str) -> str:
        """计算请求签名。

        签名规则：
        1. 待签名串 = HTTPMethod + "_" + Content_MD5 + "_" + req_date + "_" + access_token + "_" + AppSecret
        2. 签名值 = Base64(MD5(待签名串))
        """
        content_md5 = hashlib.md5(body_str.encode("utf-8")).hexdigest()
        sign_str = f"{method}_{content_md5}_{req_date}_{access_token}_{self.config.app_secret}"
        md5_val = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
        signature = base64.b64encode(md5_val.encode("utf-8")).decode("utf-8")
        return signature

    async def _request(self, path: str, body: dict, nsrsbh: str = "", action: str = "") -> dict:
        """发送百望云API请求。"""
        access_token = await self._get_access_token()
        req_date = str(int(time.time() * 1000))
        body_str = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        signature = self._calc_sign("POST", body_str, req_date, access_token)

        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "access_token": access_token,
            "req_date": req_date,
            "req_sign": f"API-SV1:{self.config.app_key}:{signature}",
        }

        try:
            resp = await self._client.post(path, content=body_str, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != "2000":
                raise Exception(f"百望云API错误: code={result.get('code')}, msg={result.get('message')}")
            return result
        except httpx.TimeoutException:
            logger.error("百望云API超时: %s", path)
            raise
        except httpx.HTTPError as e:
            logger.error("百望云API网络错误: %s %s", path, e)
            raise

    # ------------------------------------------------------------------ #
    # 开票
    # ------------------------------------------------------------------ #

    async def issue_invoice(
        self, invoice_request: dict, config: dict | None = None
    ) -> IssueResult:
        """提交数电发票开具。

        Args:
            invoice_request: 平台标准开票请求，需转换为百望云格式
            config: 额外配置（如 nsrsbh、accountId）

        Returns:
            IssueResult
        """
        nsrsbh = (config or {}).get("nsrsbh", invoice_request.get("seller_tax_no", ""))
        account_id = (config or {}).get("account_id", self.config.account_id)

        # 转换平台格式 -> 百望云格式
        baiwang_data = self._convert_to_baiwang_format(invoice_request)

        body = {
            "action": "fpkj_zzs",
            "nsrsbh": nsrsbh,
            "async": False,
            "accountId": account_id,
            "data": baiwang_data,
        }

        try:
            result = await self._request("/baiwang/IssueInvoice", body, nsrsbh=nsrsbh)
            data = result.get("data", {})

            return IssueResult(
                success=True,
                is_unknown=False,
                channel_business_no=data.get("kplsh", ""),
                invoice_number=data.get("fphm", ""),
                invoice_date=data.get("kprq", ""),
                total_amount=baiwang_data.get("hjje"),
                total_tax=baiwang_data.get("hjse"),
                total_with_tax=baiwang_data.get("jshj"),
                raw_response=result,
            )
        except httpx.TimeoutException:
            # 超时 = 结果未知
            return IssueResult(
                success=False,
                is_unknown=True,
                error_message="百望云开票请求超时，结果未知",
            )
        except Exception as e:
            error_msg = str(e)
            # 判断是否为已知错误
            return IssueResult(
                success=False,
                is_unknown=False,
                error_message=error_msg,
            )

    def _convert_to_baiwang_format(self, req: dict) -> dict:
        """将平台标准开票请求转换为百望云接口格式。"""
        items = req.get("items", [])
        xmmx = []
        for item in items:
            xmmx.append({
                "fphxz": "0",  # 正常行
                "spbm": item.get("tax_code", ""),
                "spmc": item.get("product_name", ""),
                "xmmc": item.get("product_name", ""),
                "ggxh": item.get("spec", ""),
                "dw": item.get("unit", ""),
                "spsl": str(item.get("quantity", "")),
                "dj": str(item.get("unit_price", "")),
                "sl": str(item.get("tax_rate", "")),
                "je": str(item.get("amount", "")),
                "se": str(item.get("tax_amount", "")),
                "slbs": "1" if item.get("tax_rate") else "0",
            })

        # 发票类型代码映射
        invoice_type_map = {
            "electronic_special": "032,全电专用发票",
            "electronic_normal": "030,全电普通发票",
            "special": "004,增值税专用发票",
            "normal": "007,增值税普通发票",
        }
        fplxdm = invoice_type_map.get(req.get("invoice_type", ""), "030,全电普通发票")

        # 购方类型
        gmf_lx = "2,企业" if req.get("buyer_tax_no") else "1,个人"

        return {
            "ly_ddbh": req.get("external_order_no", ""),
            "fplxdm": fplxdm,
            "xsf_nsrsbh": req.get("seller_tax_no", ""),
            "xsf_nsrmc": req.get("seller_name", ""),
            "xsf_dz": req.get("seller_address", ""),
            "xsf_dh": req.get("seller_phone", ""),
            "xsf_yhmc": req.get("seller_bank_name", ""),
            "xsf_yhzh": req.get("seller_bank_account", ""),
            "gmf_lx": gmf_lx,
            "gmf_nsrsbh": req.get("buyer_tax_no", ""),
            "gmf_nsrmc": req.get("buyer_name", ""),
            "gmf_dz": req.get("buyer_address", ""),
            "gmf_dh": req.get("buyer_phone", ""),
            "gmf_yhmc": req.get("buyer_bank_name", ""),
            "gmf_yhzh": req.get("buyer_bank_account", ""),
            "hjje": str(req.get("total_amount", "0")),
            "hjse": str(req.get("total_tax", "0")),
            "jshj": str(req.get("total_with_tax", "0")),
            "bz": req.get("remark", ""),
            "fhr": req.get("reviewer", ""),
            "skr": req.get("payee", ""),
            "hsslbs": "1" if req.get("is_tax_inclusive", True) else "0",
            "xmmx": xmmx,
        }

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #

    async def query_result(self, channel_business_no: str) -> QueryResult:
        """查询开票结果（异步场景或结果未知时使用）。"""
        body = {
            "nsrsbh": "",
            "async": False,
            "data": {
                "kplsh": channel_business_no,
            },
        }
        try:
            result = await self._request("/baiwang/QueryInvoice", body)
            data = result.get("data", {})
            return QueryResult(
                success=data.get("fpzt") in ("0", "1"),  # 0=正常，1=红冲
                is_unknown=False,
                invoice_number=data.get("fphm", ""),
                invoice_date=data.get("kprq", ""),
                total_amount=data.get("hjje"),
                total_tax=data.get("hjse"),
                total_with_tax=data.get("jshj"),
                raw_response=result,
            )
        except Exception as e:
            return QueryResult(
                success=False,
                is_unknown=True,
                error_message=str(e),
            )

    # ------------------------------------------------------------------ #
    # 版式文件下载
    # ------------------------------------------------------------------ #

    async def download_file(self, file_key: str) -> bytes:
        """下载数电发票版式文件（PDF/OFD）。"""
        body = {
            "nsrsbh": "",
            "async": False,
            "data": {
                "fphm": file_key,
                "wjgs": "pdf",  # pdf 或 ofd
            },
        }
        result = await self._request("/baiwang/DownloadFile", body)
        data = result.get("data", {})
        # 返回的是 base64 编码的文件内容或下载URL
        file_content = data.get("file_content", "")
        if file_content:
            return base64.b64decode(file_content)
        download_url = data.get("download_url", "")
        if download_url:
            resp = await self._client.get(download_url)
            return resp.content
        raise Exception("百望云版式文件下载失败：无文件内容")

    # ------------------------------------------------------------------ #
    # 红冲
    # ------------------------------------------------------------------ #

    async def apply_red_letter(
        self, original_invoice_no: str, reason: str, nsrsbh: str = ""
    ) -> dict:
        """红字确认单申请。"""
        body = {
            "action": "hzqrd_sq",
            "nsrsbh": nsrsbh,
            "async": False,
            "accountId": self.config.account_id,
            "data": {
                "yfphm": original_invoice_no,
                "sqyy": reason,
            },
        }
        return await self._request("/baiwang/RedLetterConfirm", body, nsrsbh=nsrsbh)

    async def issue_red_invoice(self, red_letter_no: str, nsrsbh: str = "") -> IssueResult:
        """开具红字发票。"""
        body = {
            "action": "fpkj_hz",
            "nsrsbh": nsrsbh,
            "async": False,
            "accountId": self.config.account_id,
            "data": {
                "hzqrdh": red_letter_no,
            },
        }
        try:
            result = await self._request("/baiwang/IssueInvoice", body, nsrsbh=nsrsbh)
            data = result.get("data", {})
            return IssueResult(
                success=True,
                is_unknown=False,
                channel_business_no=data.get("kplsh", ""),
                invoice_number=data.get("fphm", ""),
                raw_response=result,
            )
        except httpx.TimeoutException:
            return IssueResult(success=False, is_unknown=True, error_message="红冲请求超时")
        except Exception as e:
            return IssueResult(success=False, is_unknown=False, error_message=str(e))

    # ------------------------------------------------------------------ #
    # 企业信息
    # ------------------------------------------------------------------ #

    async def query_enterprise_info(self, nsrsbh: str) -> dict:
        """获取企业基本信息。"""
        body = {"nsrsbh": nsrsbh, "async": False, "data": {"nsrsbh": nsrsbh}}
        result = await self._request("/baiwang/QueryEnterpriseInfo", body, nsrsbh=nsrsbh)
        return result.get("data", {})

    async def query_quota(self, nsrsbh: str) -> dict:
        """查询企业开票额度。"""
        body = {"nsrsbh": nsrsbh, "async": False, "data": {"nsrsbh": nsrsbh}}
        result = await self._request("/baiwang/QueryInvoiceStat", body, nsrsbh=nsrsbh)
        return result.get("data", {})

    async def get_face_recognition_qrcode(self, nsrsbh: str, app_type: str = "tax") -> dict:
        """获取人脸识别认证二维码（企业授权前置步骤）。

        Args:
            nsrsbh: 纳税人识别号
            app_type: "tax"=税务APP, "personal_tax"=个税APP
        """
        action = "rlsb_tax" if app_type == "tax" else "rlsb_personal"
        body = {
            "nsrsbh": nsrsbh,
            "async": False,
            "data": {"nsrsbh": nsrsbh},
        }
        path = "/baiwang/GetFaceQRCode" if app_type == "tax" else "/baiwang/GetPersonalFaceQRCode"
        result = await self._request(path, body, nsrsbh=nsrsbh)
        return result.get("data", {})

    # ------------------------------------------------------------------ #
    # 健康检查
    # ------------------------------------------------------------------ #

    async def check_health(self) -> bool:
        """检查通道健康状态。"""
        try:
            await self._get_access_token()
            return True
        except Exception:
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
            max_items_per_invoice=200,
            max_amount=99999999.99,
            requires_tax_no=True,
        )

    async def close(self):
        """关闭HTTP客户端。"""
        await self._client.aclose()
