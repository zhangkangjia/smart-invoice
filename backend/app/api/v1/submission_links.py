"""提交链接管理API路由（后台管理端）。"""

import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.security import hash_password
from app.db.session import get_db
from app.models.enterprise import Enterprise
from app.models.misc import SubmissionLink
from app.models.user import User
from app.schemas.batch import CreateLinkRequest, SubmissionLinkResponse
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/submission-links", tags=["提交链接管理"])


@router.get("", summary="链接列表")
async def list_links(
    enterprise_id: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查询提交链接列表。"""
    stmt = select(SubmissionLink).where(
        SubmissionLink.tenant_id == current_user.tenant_id
    )
    if enterprise_id:
        stmt = stmt.where(SubmissionLink.enterprise_id == enterprise_id)
    if is_active is not None:
        stmt = stmt.where(SubmissionLink.is_active == is_active)

    stmt = stmt.order_by(SubmissionLink.created_at.desc())

    # count
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(stmt.offset(offset).limit(page_size))
    links = result.scalars().all()

    return {
        "items": [
            {
                "id": l.id,
                "enterprise_id": l.enterprise_id,
                "token": l.token,
                "link_type": l.link_type,
                "max_uses": l.max_uses,
                "used_count": l.used_count,
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                "is_active": l.is_active,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in links
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建链接")
async def create_link(
    body: CreateLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建提交链接。

    生成唯一token，支持设置密码、有效期、最大使用次数。
    """
    # 验证企业存在
    ent_result = await db.execute(
        select(Enterprise).where(
            Enterprise.id == body.enterprise_id,
            Enterprise.tenant_id == current_user.tenant_id,
        )
    )
    if ent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="企业不存在")

    # 生成唯一token
    token = secrets.token_urlsafe(32)

    # 密码哈希
    password_hash = None
    if body.password:
        password_hash = hash_password(body.password)

    link = SubmissionLink(
        id=uuid.uuid4().hex,
        tenant_id=current_user.tenant_id,
        enterprise_id=body.enterprise_id,
        token=token,
        link_type=body.link_type,
        password_hash=password_hash,
        max_uses=body.max_uses,
        used_count=0,
        expires_at=body.expires_at,
        is_active=True,
    )
    db.add(link)
    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=str(current_user.id),
        action="create_submission_link",
        entity_type="submission_link",
        entity_id=link.id,
        after={"enterprise_id": body.enterprise_id, "link_type": body.link_type},
    )
    await db.commit()

    return {
        "id": link.id,
        "enterprise_id": link.enterprise_id,
        "token": link.token,
        "link_type": link.link_type,
        "max_uses": link.max_uses,
        "used_count": link.used_count,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "is_active": link.is_active,
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }


@router.delete("/{link_id}", summary="停用链接")
async def deactivate_link(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """停用提交链接。"""
    result = await db.execute(
        select(SubmissionLink).where(
            SubmissionLink.id == link_id,
            SubmissionLink.tenant_id == current_user.tenant_id,
        )
    )
    link = result.scalar_one_or_none()

    if link is None:
        raise HTTPException(status_code=404, detail="链接不存在")

    link.is_active = False
    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=str(current_user.id),
        action="deactivate_submission_link",
        entity_type="submission_link",
        entity_id=link.id,
        before={"is_active": True},
        after={"is_active": False},
    )
    await db.commit()

    return {"message": "链接已停用"}


@router.post("/{link_id}/regenerate", summary="重新生成token")
async def regenerate_token(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """重新生成提交链接的token。

    旧token立即失效。
    """
    result = await db.execute(
        select(SubmissionLink).where(
            SubmissionLink.id == link_id,
            SubmissionLink.tenant_id == current_user.tenant_id,
        )
    )
    link = result.scalar_one_or_none()

    if link is None:
        raise HTTPException(status_code=404, detail="链接不存在")

    old_token = link.token
    link.token = secrets.token_urlsafe(32)
    link.used_count = 0

    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=str(current_user.id),
        action="regenerate_submission_link_token",
        entity_type="submission_link",
        entity_id=link.id,
        before={"token": old_token[:8] + "..."},
        after={"token": link.token[:8] + "..."},
    )
    await db.commit()

    return {
        "id": link.id,
        "token": link.token,
        "message": "token已重新生成，旧token已失效",
    }
