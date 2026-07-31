"""SSE 实时推送端点。

EventSource 浏览器 API 不支持自定义请求头，因此支持通过 query 参数传递 access_token。
生产环境建议使用 HttpOnly cookie 或短期 ticket 避免 token 暴露在 URL 中。
"""

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.sse_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["实时推送"])


async def _resolve_sse_user(
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """SSE专用鉴权：优先从 Authorization header，失败再从 query token 取。"""
    # 先尝试正常鉴权（可能从其他依赖中拿到）
    auth_header = request.headers.get("Authorization", "")
    actual_token = None
    if auth_header.lower().startswith("bearer "):
        actual_token = auth_header.split(" ", 1)[1]
    elif token:
        actual_token = token

    if not actual_token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Missing token")

    payload = decode_token(actual_token)
    user_id = payload.get("sub")
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.status != "active":
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


@router.get("/events", summary="SSE事件流")
async def sse_events(
    request: Request,
    token: Optional[str] = Query(None, description="访问令牌（EventSource无法携带Header时使用）"),
    db: AsyncSession = Depends(get_db),
):
    """SSE事件流。

    支持两种鉴权方式：
    1. Authorization: Bearer <token>（推荐）
    2. ?token=<access_token>（EventSource浏览器场景）
    """
    current_user = await _resolve_sse_user(request, token, db)
    tenant_id = current_user.tenant_id

    async def event_generator():
        queue = await sse_manager.connect(tenant_id)
        try:
            # 发送连接确认
            connected_msg = json.dumps(
                {"event": "connected", "data": {"user_id": str(current_user.id), "tenant_id": tenant_id}},
                ensure_ascii=False,
            )
            yield f"data: {connected_msg}\n\n"

            while True:
                # 检查客户端是否断开
                if await request.is_disconnected():
                    logger.info("SSE 客户端断开 user=%s", current_user.id)
                    break

                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳
                    heartbeat = json.dumps(
                        {"event": "heartbeat", "data": {"ts": int(time.time())}},
                        ensure_ascii=False,
                    )
                    yield f"data: {heartbeat}\n\n"
        except asyncio.CancelledError:
            logger.info("SSE 生成器被取消 user=%s", current_user.id)
        except Exception as exc:
            logger.error("SSE 生成器异常: %s", str(exc))
        finally:
            sse_manager.disconnect(tenant_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Tenant-Id": tenant_id,
        },
    )


@router.get("/status", summary="SSE连接状态")
async def sse_status(
    current_user: User = Depends(get_current_active_user),
):
    """查看当前SSE连接状态。"""
    return {
        "tenant_id": current_user.tenant_id,
        "active_connections": sse_manager.get_connection_count(current_user.tenant_id),
        "total_connections": sse_manager.get_connection_count(),
    }
