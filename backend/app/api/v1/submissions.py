"""客户网页提交API路由。

无需JWT认证，使用token验证。
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.business import BusinessRequest, SourceDocument
from app.models.enterprise import Enterprise
from app.models.invoice import InvoiceRequest
from app.models.invoice_task import InvoiceResult, InvoiceTask
from app.models.misc import SubmissionLink

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/submissions", tags=["客户提交"])

# 内存中存储已验证的 session_token（生产环境应使用 Redis）
_session_tokens: dict[str, str] = {}


async def _get_valid_link(db: AsyncSession, token: str) -> SubmissionLink:
    """验证并获取有效的提交链接。"""
    result = await db.execute(
        select(SubmissionLink).where(SubmissionLink.token == token)
    )
    link = result.scalar_one_or_none()

    if link is None:
        raise HTTPException(status_code=404, detail="提交链接不存在")
    if not link.is_active:
        raise HTTPException(status_code=403, detail="提交链接已停用")
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="提交链接已过期")
    if link.used_count >= link.max_uses:
        raise HTTPException(status_code=403, detail="提交链接已达最大使用次数")

    return link


@router.get("/{token}/info", summary="获取提交链接信息")
async def get_submission_info(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """客户获取提交链接关联的企业信息。"""
    link = await _get_valid_link(db, token)

    result = await db.execute(
        select(Enterprise).where(Enterprise.id == link.enterprise_id)
    )
    enterprise = result.scalar_one_or_none()
    if enterprise is None:
        raise HTTPException(status_code=404, detail="关联企业不存在")

    name = enterprise.name
    masked_name = name[:2] + "*" * (len(name) - 2) if len(name) > 2 else name

    return {
        "enterprise_name": masked_name,
        "requires_password": link.password_hash is not None,
        "is_active": link.is_active,
        "link_type": link.link_type,
        "used_count": link.used_count,
        "max_uses": link.max_uses,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }


@router.post("/{token}/auth", summary="验证提交密码")
async def auth_submission(
    token: str,
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """验证客户提交密码。"""
    link = await _get_valid_link(db, token)

    if link.password_hash is None:
        raise HTTPException(status_code=400, detail="此链接不需要密码")

    from app.core.security import verify_password

    if not verify_password(password, link.password_hash):
        raise HTTPException(status_code=401, detail="密码错误")

    session_token = secrets.token_urlsafe(32)
    _session_tokens[session_token] = token

    return {
        "session_token": session_token,
        "expires_in": 3600,
    }


def _verify_session(token: str, session_token: str | None) -> bool:
    """验证 session_token 是否匹配。"""
    if not session_token:
        return False
    stored = _session_tokens.get(session_token)
    return stored == token


@router.post("/{token}/submit", summary="客户提交开票资料")
async def submit_via_link(
    token: str,
    content: str | None = Form(None),
    external_order_no: str | None = Form(None),
    customer_remark: str | None = Form(None),
    contact_name: str | None = Form(None),
    contact_phone: str | None = Form(None),
    contact_email: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
    db: AsyncSession = Depends(get_db),
):
    """客户通过专属链接提交开票资料。"""
    link = await _get_valid_link(db, token)

    # 密码验证
    if link.password_hash is not None:
        if not _verify_session(token, x_session_token):
            raise HTTPException(status_code=401, detail="请先验证密码")

    if not content and not files:
        raise HTTPException(status_code=400, detail="请提供开票内容或上传文件")

    request_id = uuid.uuid4().hex
    business_request = BusinessRequest(
        id=request_id,
        tenant_id=link.tenant_id,
        enterprise_id=link.enterprise_id,
        source_type="web_link",
        source_channel="submission_link",
        external_order_no=external_order_no,
        customer_remark=customer_remark,
        urgency="normal",
        current_stage="submitted",
        status="pending",
        created_by=None,
    )
    db.add(business_request)
    await db.flush()

    if content:
        text_doc = SourceDocument(
            id=uuid.uuid4().hex,
            tenant_id=link.tenant_id,
            business_request_id=request_id,
            doc_type="text",
            content=content,
        )
        db.add(text_doc)

    saved_files: list[dict] = []
    for upload_file in files:
        file_content = await upload_file.read()
        if not file_content:
            continue

        file_hash = hashlib.sha256(file_content).hexdigest()
        filename = upload_file.filename or "unknown"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ("jpg", "jpeg", "png", "gif", "bmp"):
            doc_type = "image"
        elif ext == "pdf":
            doc_type = "pdf"
        elif ext == "ofd":
            doc_type = "ofd"
        elif ext in ("xls", "xlsx"):
            doc_type = "excel"
        else:
            doc_type = "text"

        doc = SourceDocument(
            id=uuid.uuid4().hex,
            tenant_id=link.tenant_id,
            business_request_id=request_id,
            doc_type=doc_type,
            file_name=filename,
            file_size=len(file_content),
            file_hash=file_hash,
            file_key=f"submissions/{request_id}/{filename}",
        )
        db.add(doc)
        saved_files.append({"file_name": filename, "file_size": len(file_content), "doc_type": doc_type})

    link.used_count += 1
    await db.commit()

    return {
        "request_id": request_id,
        "request_no": request_id[:8].upper(),
        "status": "pending",
        "message": "提交成功，请等待处理",
        "files_saved": len(saved_files),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{token}/status", summary="查询提交状态")
async def get_submission_status(
    token: str,
    request_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """客户查询已提交申请的状态。"""
    link = await _get_valid_link(db, token)

    result = await db.execute(
        select(BusinessRequest).where(
            BusinessRequest.id == request_id,
            BusinessRequest.tenant_id == link.tenant_id,
            BusinessRequest.enterprise_id == link.enterprise_id,
        )
    )
    br = result.scalar_one_or_none()
    if br is None:
        raise HTTPException(status_code=404, detail="申请不存在")

    enterprise = (await db.execute(
        select(Enterprise).where(Enterprise.id == link.enterprise_id)
    )).scalar_one_or_none()

    # 通过 InvoiceRequest.business_request_id 关联，而不是直接查 InvoiceTask
    inv_req_result = await db.execute(
        select(InvoiceRequest).where(InvoiceRequest.business_request_id == request_id)
    )
    invoice_request = inv_req_result.scalar_one_or_none()

    timeline: list[dict] = []
    tasks_data: list[dict] = []

    if invoice_request:
        task_result = await db.execute(
            select(InvoiceTask).where(
                InvoiceTask.invoice_request_id == invoice_request.id
            ).order_by(InvoiceTask.created_at.desc())
        )
        tasks = task_result.scalars().all()

        for t in tasks:
            inv_result = (await db.execute(
                select(InvoiceResult).where(InvoiceResult.invoice_task_id == t.id)
            )).scalar_one_or_none()

            tasks_data.append({
                "task_id": t.id,
                "status": t.status,
                "invoice_number": inv_result.invoice_number if inv_result else None,
                "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "last_error": t.last_error,
            })

            if t.status == "success":
                timeline.append({"action": "开票成功", "time": t.completed_at.isoformat() if t.completed_at else None})
            elif t.status == "failed":
                timeline.append({"action": f"开票失败: {t.last_error}", "time": t.completed_at.isoformat() if t.completed_at else None})
            elif t.status in ("submitting", "queuing", "accepted"):
                timeline.append({"action": "正在开票", "time": t.submitted_at.isoformat() if t.submitted_at else None})

    timeline.insert(0, {"action": "提交成功", "time": br.created_at.isoformat() if br.created_at else None})

    return {
        "request_id": request_id,
        "request_no": request_id[:8].upper(),
        "status": br.status,
        "enterprise_name": enterprise.name if enterprise else None,
        "current_stage": br.current_stage,
        "tasks": tasks_data,
        "timeline": timeline,
        "created_at": br.created_at.isoformat() if br.created_at else None,
        "updated_at": br.updated_at.isoformat() if br.updated_at else None,
    }


@router.get("/{token}/result", summary="下载开票结果")
async def get_submission_result(
    token: str,
    request_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """客户下载开票结果文件。"""
    link = await _get_valid_link(db, token)

    result = await db.execute(
        select(BusinessRequest).where(
            BusinessRequest.id == request_id,
            BusinessRequest.tenant_id == link.tenant_id,
            BusinessRequest.enterprise_id == link.enterprise_id,
        )
    )
    br = result.scalar_one_or_none()
    if br is None:
        raise HTTPException(status_code=404, detail="申请不存在")

    # 通过 InvoiceRequest 关联查找
    inv_req_result = await db.execute(
        select(InvoiceRequest).where(InvoiceRequest.business_request_id == request_id)
    )
    invoice_request = inv_req_result.scalar_one_or_none()

    results: list[dict] = []
    if invoice_request:
        task_result = await db.execute(
            select(InvoiceTask).where(InvoiceTask.invoice_request_id == invoice_request.id)
        )
        tasks = task_result.scalars().all()
        for task in tasks:
            inv_result = (await db.execute(
                select(InvoiceResult).where(InvoiceResult.invoice_task_id == task.id)
            )).scalar_one_or_none()
            if inv_result:
                results.append({
                    "task_id": task.id,
                    "status": task.status,
                    "invoice_number": inv_result.invoice_number,
                    "invoice_code": inv_result.invoice_code,
                    "total_with_tax": str(inv_result.total_with_tax) if inv_result.total_with_tax else None,
                    "file_status": inv_result.file_status,
                    "download_available": inv_result.file_status == "available" and inv_result.file_key is not None,
                })

    return {"request_id": request_id, "results": results}


@router.get("/{token}/history", summary="历史提交记录")
async def get_submission_history(
    token: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """客户查看历史提交记录。"""
    link = await _get_valid_link(db, token)

    from sqlalchemy import func
    stmt = select(BusinessRequest).where(
        BusinessRequest.tenant_id == link.tenant_id,
        BusinessRequest.enterprise_id == link.enterprise_id,
        BusinessRequest.source_type == "web_link",
    ).order_by(BusinessRequest.created_at.desc())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(stmt.offset(offset).limit(page_size))
    items = result.scalars().all()

    return {
        "items": [
            {
                "request_id": r.id,
                "request_no": r.id[:8].upper(),
                "status": r.status,
                "external_order_no": r.external_order_no,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
