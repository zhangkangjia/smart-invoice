"""微信服务号 & 企业微信集成服务。

支持能力：
1. 微信服务号：客户通过公众号提交开票请求、接收模板消息通知
2. 企业微信：作为自建应用嵌入工作台、OAuth免登录、消息通知
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
            logger.error("获取微信access_token失败: %s", data)
            raise RuntimeError(f"微信获取access_token失败: {data.get('errmsg')}")

        self._access_token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200)
        return self._access_token

    def verify_signature(self, signature: str, timestamp: str, nonce: str) -> bool:
        """验证微信服务器签名。"""
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
    ) -> bool:
        """发送服务号模板消息通知客户。"""
        if not self.enabled:
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

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url_api, json=payload)
            result = resp.json()

        if result.get("errcode") == 0:
            logger.info("微信模板消息发送成功 openid=%s", openid)
            return True
        logger.error("微信模板消息发送失败: %s", result)
        return False

    async def get_oauth_user_info(self, code: str) -> dict:
        """通过OAuth授权码获取用户信息。"""
        if not self.enabled:
            raise RuntimeError("微信服务号未配置")

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
            return {}

        url = f"{self.BASE_URL}/sns/userinfo"
        params = {
            "access_token": token_data["access_token"],
            "openid": token_data["openid"],
            "lang": "zh_CN",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            return resp.json()

    def build_oauth_url(self, redirect_uri: str, scope: str = "snsapi_base", state: str = "") -> str:
        """构造网页授权URL。"""
        from urllib.parse import quote

        if not self.enabled:
            return ""
        encoded_uri = quote(redirect_uri, safe="")
        return (
            f"https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={self.app_id}&redirect_uri={encoded_uri}&response_type=code"
            f"&scope={scope}&state={state}#wechat_redirect"
        )


class WeComService:
    """企业微信 API 封装。

    核心能力：
    1. 自建应用免登录（OAuth code 换取 userid）
    2. 应用消息推送（文本/Markdown）
    3. 通讯录同步（部门、成员）
    4. JS-SDK 签名（用于在企业微信内嵌H5）
    5. 工作台应用配置
    """

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
        """获取企业微信 access_token（带缓存）。"""
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

    # ===== OAuth 免登录 =====

    async def get_user_id_by_code(self, code: str) -> str:
        """通过OAuth code换取企业微信userid（免登录核心）。

        流程：
        1. 前端在企业微信中打开自建应用URL，自动带上 code 参数
        2. 后端用 code 调此接口换取 userid
        3. 根据 userid 查找本地账号，自动登录
        """
        if not self.enabled:
            raise RuntimeError("企业微信未配置")

        token = await self.get_access_token()
        url = f"{self.BASE_URL}/auth/getuserinfo"
        params = {"access_token": token, "code": code}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        if data.get("errcode") != 0:
            logger.error("企业微信OAuth失败: %s", data)
            raise RuntimeError(f"企业微信OAuth失败: {data.get('errmsg')}")

        return data.get("userid", "")

    async def get_user_detail(self, userid: str) -> dict:
        """读取成员详情。"""
        token = await self.get_access_token()
        url = f"{self.BASE_URL}/user/get"
        params = {"access_token": token, "userid": userid}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        if data.get("errcode") != 0:
            logger.error("企业微信获取用户详情失败: %s", data)
            return {}
        return data

    # ===== JS-SDK 签名（嵌入企业微信H5用）=====

    _jsapi_ticket: str = ""
    _jsapi_ticket_expires: float = 0

    async def get_jsapi_ticket(self) -> str:
        """获取JS-SDK票据（带缓存）。"""
        if self._jsapi_ticket and time.time() < self._jsapi_ticket_expires - 300:
            return self._jsapi_ticket

        token = await self.get_access_token()
        url = f"{self.BASE_URL}/get_jsapi_ticket?access_token={token}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            data = resp.json()

        if data.get("errcode") != 0:
            logger.error("企业微信获取jsapi_ticket失败: %s", data)
            return ""
        self._jsapi_ticket = data["ticket"]
        self._jsapi_ticket_expires = time.time() + data.get("expires_in", 7200)
        return self._jsapi_ticket

    async def generate_jsapi_signature(self, url: str, nonce_str: str, timestamp: int) -> str:
        """生成JS-SDK签名（用于在企业微信内嵌H5页面时调用wx.config）。"""
        import hashlib

        ticket = await self.get_jsapi_ticket()
        if not ticket:
            return ""
        raw = f"jsapi_ticket={ticket}&noncestr={nonce_str}&timestamp={timestamp}&url={url}"
        return hashlib.sha1(raw.encode()).hexdigest()

    # ===== 消息推送 =====

    async def send_text_message(self, user_ids: str, content: str) -> bool:
        """发送文本消息。"""
        return await self._send_app_message({
            "touser": user_ids,
            "msgtype": "text",
            "agentid": int(self.agent_id) if self.agent_id else 0,
            "text": {"content": content},
        })

    async def send_markdown_message(self, user_ids: str, content: str) -> bool:
        """发送Markdown消息（支持格式化）。"""
        return await self._send_app_message({
            "touser": user_ids,
            "msgtype": "markdown",
            "agentid": int(self.agent_id) if self.agent_id else 0,
            "markdown": {"content": content},
        })

    async def _send_app_message(self, payload: dict) -> bool:
        if not self.enabled:
            return False
        token = await self.get_access_token()
        url = f"{self.BASE_URL}/message/send?access_token={token}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            result = resp.json()
        if result.get("errcode") == 0:
            logger.info("企业微信消息发送成功 to=%s", payload.get("touser"))
            return True
        logger.error("企业微信消息发送失败: %s", result)
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

    # ===== 通讯录 =====

    async def get_department_users(self, department_id: int = 1, fetch_child: int = 1) -> list[dict]:
        """获取部门成员列表。"""
        if not self.enabled:
            return []
        token = await self.get_access_token()
        url = f"{self.BASE_URL}/user/simplelist"
        params = {
            "access_token": token,
            "department_id": department_id,
            "fetch_child": fetch_child,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
        if data.get("errcode") == 0:
            return data.get("userlist", [])
        return []


# 全局单例
wechat_service = WeChatService()
wecom_service = WeComService()
