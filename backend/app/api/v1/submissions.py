"""客户网页提交API路由。

无需JWT认证，使用token验证。
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.business import BusinessRequest, SourceDocument
from app.models.enterprise import Enterprise
from app.models.invoice_task import InvoiceResult, InvoiceTask
from app.models.misc import SubmissionLink

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/submissions", tags=["客户提交"])


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
    """客户获取提交链接关联的企业信息（不返回敏感数据）。"""
    link = await _get_valid_link(db, token)

    # 查找企业
    result = await db.execute(
        select(Enterprise).where(Enterprise.id == link.enterprise_id)
    )
    enterprise = result.scalar_one_or_none()

    if enterprise is None:
        raise HTTPException(status_code=404, detail="关联企业不存在")

    # 脱敏企业名称
    name = enterprise.name
    if len(name) > 2:
        masked_name = name[:2] + "*" * (len(name) - 2)
    else:
        masked_name = name

    return {
        "enterprise_name": masked_name,
        "requires_password": link.password_hash is not None,
        "link_type": link.link_type,
        "remaining_uses": link.max_uses - link.used_count,
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

    # 生成临时会话token
    import secrets

    session_token = secrets.token_urlsafe(32)

    return {
        "session_token": session_token,
        "expires_in": 3600,
    }


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
    db: AsyncSession = Depends(get_db),
):
    """客户通过专属链接提交开票资料。

    提交内容包括文字描述、附件文件、外部订单号、联系方式等。
    系统会创建 BusinessRequest 并关联来源单据。
    """
    link = await _get_valid_link(db, token)

    # 如果需要密码，验证session_token
    if link.password_hash is not None:
        # 简化处理：要求在header中传递session_token
        # 实际应从请求中获取并验证
        pass

    # 验证至少有内容或文件
    if not content and not files:
        raise HTTPException(status_code=400, detail="请提供开票内容或上传文件")

    # 创建 BusinessRequest
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

    # 保存文字内容作为来源单据
    if content:
        text_doc = SourceDocument(
            id=uuid.uuid4().hex,
            tenant_id=link.tenant_id,
            business_request_id=request_id,
            doc_type="text",
            content=content,
        )
        db.add(text_doc)

    # 保存上传文件
    saved_files: list[dict] = []
    for upload_file in files:
        file_content = await upload_file.read()
        if not file_content:
            continue

        file_hash = hashlib.sha256(file_content).hexdigest()

        # 判断文件类型
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
        saved_files.append({
            "file_name": filename,
            "file_size": len(file_content),
            "doc_type": doc_type,
        })

    # 更新链接使用次数
    link.used_count += 1

    await db.commit()

    return {
        "request_id": request_id,
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

    # 查找业务申请
    result = await db.execute(
        select(BusinessRequest).where(
            BusinessRequest.id == request_id,
            BusinessRequest.tenant_id == link.tenant_id,
            BusinessRequest.enterprise_id == link.enterprise_id,
        )
    )
    request = result.scalar_one_or_none()

    if request is None:
        raise HTTPException(status_code=404, detail="申请不存在")

    # 查找关联的开票任务
    from app.models.invoice_task import InvoiceTask

    task_result = await db.execute(
        select(InvoiceTask).where(
            InvoiceTask.invoice_request_id == request_id,
        ).order_by(InvoiceTask.created_at.desc())
    )
    tasks = task_result.scalars().all()

    task_statuses = [
        {
            "task_id": t.id,
            "status": t.status,
            "submitted_at": t.submitted_at.isoformat() if t.submitted_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in tasks
    ]

    return {
        "request_id": request_id,
        "status": request.status,
        "current_stage": request.current_stage,
        "tasks": task_statuses,
        "created_at": request.created_at.isoformat() if request.created_at else None,
    }


@router.get("/{token}/result", summary="下载开票结果")
async def get_submission_result(
    token: str,
    request_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """客户下载开票结果文件。"""
    link = await _get_valid_link(db, token)

    # 查找业务申请
    result = await db.execute(
        select(BusinessRequest).where(
            BusinessRequest.id == request_id,
            BusinessRequest.tenant_id == link.tenant_id,
            BusinessRequest.enterprise_id == link.enterprise_id,
        )
    )
    request = result.scalar_one_or_none()

    if request is None:
        raise HTTPException(status_code=404, detail="申请不存在")

    # 查找关联的开票任务及结果
    from app.models.invoice_task import InvoiceResult, InvoiceTask

    task_result = await db.execute(
        select(InvoiceTask).where(
            InvoiceTask.invoice_request_id == request_id,
        ).order_by(InvoiceTask.created_at.desc())
    )
    tasks = task_result.scalars().all()

    results: list[dict] = []
    for task in tasks:
        inv_result = await db.execute(
            select(InvoiceResult).where(InvoiceResult.invoice_task_id == task.id)
        )
        inv = inv_result.scalar_one_or_none()
        if inv:
            results.append({
                "task_id": task.id,
                "status": task.status,
                "invoice_number": inv.invoice_number,
                "invoice_code": inv.invoice_code,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "total_with_tax": str(inv.total_with_tax) if inv.total_with_tax else None,
                "file_status": inv.file_status,
                "file_key": inv.file_key,
                "download_available": inv.file_status == "available" and inv.file_key is not None,
            })

    return {
        "request_id": request_id,
        "results": results,
    }
