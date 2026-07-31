"""企业微信 & 微信服务号 API。

核心场景：
1. 企业微信自建应用：OAuth 免登录、JS-SDK 签名、工作台嵌入
2. 微信服务号：客户提交开票、模板消息通知
"""

import logging
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_active_user, require_roles
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.wechat_service import wecom_service, wechat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wechat", tags=["微信/企业微信集成"])


# ============================================================
# 企业微信免登录（核心）
# ============================================================

@router.get("/wecom/oauth-login", summary="企业微信OAuth免登录")
async def wecom_oauth_login(
    code: str = Query(..., description="企业微信OAuth code"),
    redirect: str = Query("/", description="登录后跳转路径"),
    db: AsyncSession = Depends(get_db),
):
    """企业微信自建应用免登录入口。

    流程：
    1. 用户在企业微信里点击自建应用
    2. 企业微信带 code 跳转到本接口
    3. 用 code 换取 userid
    4. 在系统用户表中查找匹配的用户（userid 或 mobile 关联）
    5. 颁发 JWT，重定向到前端
    """
    if not wecom_service.enabled:
        raise HTTPException(status_code=503, detail="企业微信未配置")

    # 1. code -> userid
    userid = await wecom_service.get_user_id_by_code(code)
    if not userid:
        raise HTTPException(status_code=400, detail="企业微信OAuth失败")

    # 2. 查系统用户（通过 wecom_userid 字段）
    result = await db.execute(
        select(User).where(User.wecom_userid == userid)
    )
    user = result.scalar_one_or_none()

    # 3. 兜底：没绑定时通过手机号匹配
    if user is None:
        detail = await wecom_service.get_user_detail(userid)
        mobile = detail.get("mobile", "")
        if mobile:
            result = await db.execute(
                select(User).where(User.phone == mobile)
            )
            user = result.scalar_one_or_none()
            if user:
                # 绑定关系
                user.wecom_userid = userid
                await db.commit()

    if user is None or user.status != "active":
        raise HTTPException(
            status_code=403,
            detail="该企业微信账号未绑定系统用户，请联系管理员",
        )

    # 4. 颁发 JWT
    from app.core.deps import _get_user_role_codes
    role_codes = await _get_user_role_codes(db, user.id)
    extra_claims = {
        "tenant_id": user.tenant_id,
        "username": user.username,
        "roles": role_codes,
    }
    access_token = create_access_token(subject=user.id, extra_claims=extra_claims)

    # 5. 返回前端跳转信息
    frontend_base = settings.FRONTEND_BASE_URL.rstrip("/")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "is_super_admin": user.is_super_admin,
            "tenant_id": user.tenant_id,
        },
        "redirect": f"{frontend_base}{redirect}",
    }


@router.get("/wecom/jsapi-config", summary="企业微信JS-SDK配置")
async def wecom_jsapi_config(
    url: str = Query(..., description="当前页面URL（用于签名）"),
):
    """生成企业微信JS-SDK配置（用于在企业微信内嵌H5调用wx.agentConfig等）。

    前端用法：
    ```js
    wx.config({...})
    wx.agentConfig({
        corpid, agentid, signature, ...
    })
    ```
    """
    if not wecom_service.enabled:
        raise HTTPException(status_code=503, detail="企业微信未配置")

    nonce_str = secrets.token_hex(8)
    timestamp = int(time.time())
    signature = await wecom_service.generate_jsapi_signature(url, nonce_str, timestamp)

    return {
        "corp_id": wecom_service.corp_id,
        "agent_id": wecom_service.agent_id,
        "nonce_str": nonce_str,
        "timestamp": timestamp,
        "signature": signature,
    }


@router.post("/wecom/bind-user", summary="绑定企业微信userid")
async def bind_wecom_user(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "agency_admin")),
):
    """管理员将系统用户与企业微信userid绑定。"""
    user_id = data.get("user_id")
    wecom_userid = data.get("wecom_userid")
    if not user_id or not wecom_userid:
        raise HTTPException(status_code=400, detail="参数缺失")

    from app.core.deps import get_tenant_id
    tid = get_tenant_id(current_user)
    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.wecom_userid = wecom_userid
    user.wecom_bound_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True}


# ============================================================
# 微信服务号（客户侧）
# ============================================================

@router.get("/callback", summary="微信服务器验证")
async def wechat_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """微信公众号服务器配置校验。"""
    if wechat_service.verify_signature(signature, timestamp, nonce):
        return int(echostr)
    raise HTTPException(status_code=403, detail="签名验证失败")


@router.post("/callback", summary="微信消息回调")
async def wechat_message(
    request: Request,
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """接收微信事件推送。"""
    if not wechat_service.verify_signature(signature, timestamp, nonce):
        raise HTTPException(status_code=403, detail="签名验证失败")
    body = await request.body()
    logger.info("收到微信消息: %s", body[:200])
    return "success"


@router.get("/oauth-url", summary="获取微信授权链接")
async def get_oauth_url(
    redirect_uri: str = Query(...),
    state: str = Query(""),
):
    if not wechat_service.enabled:
        raise HTTPException(status_code=503, detail="微信服务号未配置")
    return {"url": wechat_service.build_oauth_url(redirect_uri, scope="snsapi_userinfo", state=state)}


@router.get("/user-info", summary="微信授权获取用户信息")
async def get_wechat_user(code: str = Query(...)):
    if not wechat_service.enabled:
        raise HTTPException(status_code=503, detail="微信服务号未配置")
    user_info = await wechat_service.get_oauth_user_info(code)
    if not user_info:
        raise HTTPException(status_code=400, detail="获取微信用户信息失败")
    return {
        "openid": user_info.get("openid", ""),
        "nickname": user_info.get("nickname", ""),
        "headimgurl": user_info.get("headimgurl", ""),
    }


# ============================================================
# 通知推送（内部调用）
# ============================================================

@router.post("/notify-invoice", summary="开票结果通知")
async def notify_invoice_result(data: dict):
    """开票完成后推送到企业微信。"""
    if not wecom_service.enabled:
        return {"skipped": True, "reason": "企业微信未配置"}
    success = await wecom_service.notify_invoice_result(
        user_ids=data.get("user_ids", ""),
        enterprise_name=data.get("enterprise_name", ""),
        invoice_number=data.get("invoice_number", ""),
        amount=data.get("amount", ""),
        status=data.get("status", ""),
        error_msg=data.get("error_msg", ""),
    )
    return {"success": success}


# ============================================================
# 状态
# ============================================================

@router.get("/status", summary="集成状态")
async def status():
    return {
        "wechat_service_account": wechat_service.enabled,
        "wecom": wecom_service.enabled,
        "wecom_corp_id": wecom_service.corp_id if wecom_service.enabled else "",
        "wecom_agent_id": wecom_service.agent_id if wecom_service.enabled else "",
        "frontend_base_url": settings.FRONTEND_BASE_URL,
    }


@router.get("/wecom/test", summary="测试企业微信连通性")
async def test_wecom():
    """测试企业微信 access_token 是否能正常获取。

    返回:
    - ok=true: 配置正确，可正常使用
    - ok=false: 配置错误，详见 error
    """
    if not wecom_service.enabled:
        return {"ok": False, "error": "企业微信未配置 (WECOM_CORP_ID/WECOM_SECRET 为空)"}
    try:
        token = await wecom_service.get_access_token()
        return {
            "ok": True,
            "access_token_prefix": token[:20] + "...",
            "corp_id": wecom_service.corp_id,
            "agent_id": wecom_service.agent_id,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/wecom/department-users", summary="企业微信部门成员")
async def get_dept_users(department_id: int = 1):
    """获取企业微信部门成员，用于同步到系统用户。"""
    if not wecom_service.enabled:
        raise HTTPException(status_code=503, detail="企业微信未配置")
    users = await wecom_service.get_department_users(department_id)
    return {"users": users}
