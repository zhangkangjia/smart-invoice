"""微信服务号回调 & 开票入口 API。

提供：
1. 微信服务器签名验证（公众号后台配置）
2. 客户通过微信菜单进入开票H5页面
3. 微信OAuth授权回调
4. 开票结果模板消息推送（内部调用）
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services.wechat_service import wecom_service, wechat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wechat", tags=["微信集成"])


@router.get("/callback", summary="微信服务器验证")
async def wechat_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """微信公众号服务器配置校验（GET请求）。

    在公众号后台 → 开发 → 基本配置中填写回调URL时使用。
    """
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
    """接收微信事件推送（关注/菜单点击等）。

    客户点击公众号菜单"申请开票"时，返回H5链接。
    """
    if not wechat_service.verify_signature(signature, timestamp, nonce):
        raise HTTPException(status_code=403, detail="签名验证失败")

    body = await request.body()
    logger.info("收到微信消息回调: %s", body[:200])

    # TODO: 解析XML，根据MsgType和Event返回不同响应
    # 目前返回空响应
    return "success"


@router.get("/oauth-url", summary="获取微信授权链接")
async def get_oauth_url(
    redirect_uri: str = Query(..., description="授权后跳转的URL"),
    state: str = Query("", description="透传参数"),
):
    """获取微信网页授权URL（前端跳转用）。"""
    if not wechat_service.enabled:
        raise HTTPException(status_code=503, detail="微信服务号未配置")
    url = wechat_service.build_oauth_url(redirect_uri, scope="snsapi_userinfo", state=state)
    return {"url": url}


@router.get("/user-info", summary="微信授权获取用户信息")
async def get_wechat_user(code: str = Query(..., description="微信授权code")):
    """通过微信授权code获取用户信息（openid、昵称等）。

    前端流程：
    1. 调用 /wechat/oauth-url 获取授权链接
    2. 用户授权后微信回调带code
    3. 前端用code调用本接口换取用户信息
    """
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


@router.post("/notify-invoice", summary="开票结果通知（内部调用）")
async def notify_invoice_result(
    data: dict[str, Any],
):
    """开票完成后推送到企业微信通知代账人员。

    调用方传入:
    - user_ids: 企业微信用户ID（逗号分隔）
    - enterprise_name: 企业名称
    - invoice_number: 发票号
    - amount: 金额
    - status: 状态 success/failed
    - error_msg: 错误信息（可选）
    """
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


@router.get("/status", summary="微信集成状态")
async def wechat_status():
    """查看微信和企业微信配置状态。"""
    return {
        "wechat_enabled": wechat_service.enabled,
        "wecom_enabled": wecom_service.enabled,
        "frontend_base_url": settings.FRONTEND_BASE_URL,
    }
