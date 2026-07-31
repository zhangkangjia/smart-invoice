"""微信服务号 & 企业微信集成服务。

支持能力：
1. 客户通过微信服务号提交开票请求（H5页面）
2. 开票完成后推送模板消息通知客户
3. 企业微信应用消息通知代账人员
4. 微信回调签名验证
"""

import hashlib
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class WeChatService:
    """微信服务号 API 封装。"""

    BASE_URL = "https://api.weixin.qq.com"

    def __init__(self) -> None:
        self.app_id = settings.WECHAT_APP_ID
        self.app_secret = settings.WECHAT_APP_SECRET
        self._access_token: str = ""
        self._token_expires: float = 0

    @property
    def enabled(self) -> bool:
        return bool(self.app_id and self.app_secret)

    async def get_access_token(self) -> str:
        """获取微信 access_token（带缓存）。"""
        if self._access_token and time.time() < self._token_expires - 300:
            return self._access_token

        if not self.enabled:
            raise RuntimeError("微信服务号未配置")

        url = f"{self.BASE_URL}/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        if "access_token" not in data:
            errcode = data.get("errcode", -1)
            errmsg = data.get("errmsg", "unknown")
            logger.error("获取微信access_token失败: %s %s", errcode, errmsg)
            raise RuntimeError(f"微信获取access_token失败: {errmsg}")

        self._access_token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200)
        logger.info("微信access_token已刷新，有效期%ds", data.get("expires_in", 7200))
        return self._access_token

    def verify_signature(self, signature: str, timestamp: str, nonce: str, echostr: str = "") -> bool:
        """验证微信服务器签名（用于公众号服务器配置校验）。"""
        token = settings.WECHAT_TOKEN
        if not token:
            return False
        parts = sorted([token, timestamp, nonce])
        sha1 = hashlib.sha1("".join(parts).encode()).hexdigest()
        return sha1 == signature

    async def send_template_message(
        self,
        openid: str,
        template_id: str,
        data: dict[str, dict[str, str]],
        url: str = "",
        miniprogram: dict | None = None,
    ) -> bool:
        """发送模板消息通知客户。

        Args:
            openid: 接收者的微信openid
            template_id: 模板消息ID
            data: 模板数据，如 {"first": {"value": "您的发票已开具"}, ...}
            url: 点击跳转的URL
            miniprogram: 小程序跳转参数
        """
        if not self.enabled:
            logger.warning("微信未配置，跳过模板消息发送")
            return False

        token = await self.get_access_token()
        url_api = f"{self.BASE_URL}/cgi-bin/message/template/send?access_token={token}"

        payload: dict[str, Any] = {
            "touser": openid,
            "template_id": template_id,
            "data": data,
        }
        if url:
            payload["url"] = url
        if miniprogram:
            payload["miniprogram"] = miniprogram

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url_api, json=payload)
            result = resp.json()

        if result.get("errcode") == 0:
            logger.info("微信模板消息发送成功 openid=%s", openid)
            return True

        logger.error("微信模板消息发送失败: %s", result)
        return False

    async def send_invoice_notification(
        self,
        openid: str,
        enterprise_name: str,
        invoice_number: str,
        amount: str,
        status: str,
    ) -> bool:
        """发送开票完成通知（需在公众号后台配置模板）。"""
        template_id = ""  # 替换为实际模板ID
        data = {
            "first": {"value": f"您在{enterprise_name}的发票已处理完成"},
            "keyword1": {"value": invoice_number or "—"},
            "keyword2": {"value": amount},
            "keyword3": {"value": status},
            "remark": {"value": "点击查看发票详情"},
        }
        detail_url = f"{settings.FRONTEND_BASE_URL}/invoice/result?no={invoice_number}"
        return await self.send_template_message(openid, template_id, data, url=detail_url)

    async def get_oauth_user_info(self, code: str) -> dict:
        """通过OAuth授权码获取用户信息（网页授权）。"""
        if not self.enabled:
            raise RuntimeError("微信服务号未配置")

        # 第一步：用code换取access_token和openid
        url = f"{self.BASE_URL}/sns/oauth2/access_token"
        params = {
            "appid": self.app_id,
            "secret": self.app_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            token_data = resp.json()

        if "openid" not in token_data:
            logger.error("微信OAuth失败: %s", token_data)
            return {}

        openid = token_data["openid"]
        access_token = token_data["access_token"]

        # 第二步：拉取用户信息
        url = f"{self.BASE_URL}/sns/userinfo"
        params = {"access_token": access_token, "openid": openid, "lang": "zh_CN"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            user_info = resp.json()

        return user_info

    def build_oauth_url(self, redirect_uri: str, scope: str = "snsapi_base", state: str = "") -> str:
        """构造网页授权URL。"""
        from urllib.parse import quote

        if not self.enabled:
            return ""
        encoded_uri = quote(redirect_uri, safe="")
        url = (
            f"https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={self.app_id}&redirect_uri={encoded_uri}&response_type=code"
            f"&scope={scope}&state={state}#wechat_redirect"
        )
        return url


class WeComService:
    """企业微信 API 封装（内部通知代账人员）。"""

    BASE_URL = "https://qyapi.weixin.qq.com/cgi-bin"

    def __init__(self) -> None:
        self.corp_id = settings.WECOM_CORP_ID
        self.secret = settings.WECOM_SECRET
        self.agent_id = settings.WECOM_AGENT_ID
        self._access_token: str = ""
        self._token_expires: float = 0

    @property
    def enabled(self) -> bool:
        return bool(self.corp_id and self.secret)

    async def get_access_token(self) -> str:
        """获取企业微信 access_token。"""
        if self._access_token and time.time() < self._token_expires - 300:
            return self._access_token

        if not self.enabled:
            raise RuntimeError("企业微信未配置")

        url = f"{self.BASE_URL}/gettoken"
        params = {"corpid": self.corp_id, "corpsecret": self.secret}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        if data.get("errcode") != 0:
            logger.error("企业微信获取token失败: %s", data)
            raise RuntimeError(f"企业微信获取token失败: {data.get('errmsg')}")

        self._access_token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200)
        return self._access_token

    async def send_text_message(self, user_ids: str, content: str) -> bool:
        """发送文本消息给指定用户（@user_ids 逗号分隔）。"""
        if not self.enabled:
            logger.warning("企业微信未配置，跳过消息发送")
            return False

        token = await self.get_access_token()
        url = f"{self.BASE_URL}/message/send?access_token={token}"
        payload = {
            "touser": user_ids,
            "msgtype": "text",
            "agentid": int(self.agent_id) if self.agent_id else 0,
            "text": {"content": content},
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            result = resp.json()

        if result.get("errcode") == 0:
            logger.info("企业微信消息发送成功 to=%s", user_ids)
            return True
        logger.error("企业微信消息发送失败: %s", result)
        return False

    async def send_markdown_message(self, user_ids: str, content: str) -> bool:
        """发送Markdown消息（支持格式化）。"""
        if not self.enabled:
            return False

        token = await self.get_access_token()
        url = f"{self.BASE_URL}/message/send?access_token={token}"
        payload = {
            "touser": user_ids,
            "msgtype": "markdown",
            "agentid": int(self.agent_id) if self.agent_id else 0,
            "markdown": {"content": content},
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            result = resp.json()

        if result.get("errcode") == 0:
            logger.info("企业微信Markdown消息发送成功 to=%s", user_ids)
            return True
        logger.error("企业微信Markdown消息发送失败: %s", result)
        return False

    async def notify_invoice_result(
        self,
        user_ids: str,
        enterprise_name: str,
        invoice_number: str,
        amount: str,
        status: str,
        error_msg: str = "",
    ) -> bool:
        """通知代账人员开票结果。"""
        status_emoji = "✅" if status == "success" else "❌"
        content = (
            f"## {status_emoji} 开票结果通知\n"
            f"> **企业**: {enterprise_name}\n"
            f"> **发票号**: {invoice_number or '—'}\n"
            f"> **金额**: {amount}\n"
            f"> **状态**: {status}\n"
        )
        if error_msg:
            content += f"> **错误**: {error_msg}\n"
        content += f"\n> 详情: {settings.FRONTEND_BASE_URL}"
        return await self.send_markdown_message(user_ids, content)


# 全局单例
wechat_service = WeChatService()
wecom_service = WeComService()
