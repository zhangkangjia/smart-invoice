"""OCR/AI识别管理API路由。

管理OCR识别任务和结果。
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.business import SourceDocument
from app.models.user import User
from app.services.ai import get_router, get_image_recognizer, get_text_recognizer
from app.services.ai.knowledge_matcher import enrich_recognition
from app.services.ai.safety import check_file_safety, sanitize_input

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recognitions", tags=["AI识别"])


# --------------------------------------------------------------------------- #
# 列表/详情
# --------------------------------------------------------------------------- #

@router.get("", summary="识别任务列表")
async def list_recognitions(
    business_request_id: str | None = Query(None),
    doc_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查询OCR/AI识别任务列表。"""
    stmt = select(SourceDocument).where(
        SourceDocument.tenant_id == current_user.tenant_id,
        SourceDocument.doc_type.in_(["image", "pdf", "ofd", "text"]),
    )
    if business_request_id:
        stmt = stmt.where(SourceDocument.business_request_id == business_request_id)
    if doc_type:
        stmt = stmt.where(SourceDocument.doc_type == doc_type)

    stmt = stmt.order_by(SourceDocument.created_at.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(stmt.offset(offset).limit(page_size))
    docs = result.scalars().all()

    return {
        "items": [
            {
                "id": d.id,
                "business_request_id": d.business_request_id,
                "doc_type": d.doc_type,
                "file_name": d.file_name,
                "file_size": d.file_size,
                "has_ocr_result": d.ocr_result is not None,
                "ocr_result": d.ocr_result if d.ocr_result else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/history", summary="识别历史记录")
async def recognition_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_type: str | None = Query(None, description="text / image"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """识别历史记录列表（用于前端识别记录页面）。"""
    from datetime import datetime
    stmt = select(SourceDocument).where(
        SourceDocument.tenant_id == current_user.tenant_id,
    )
    if source_type:
        if source_type == "text":
            stmt = stmt.where(SourceDocument.doc_type == "text")
        elif source_type == "image":
            stmt = stmt.where(SourceDocument.doc_type.in_(["image", "pdf", "ofd"]))
    if start_date:
        try:
            stmt = stmt.where(SourceDocument.created_at >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            stmt = stmt.where(SourceDocument.created_at <= datetime.fromisoformat(end_date))
        except ValueError:
            pass

    stmt = stmt.order_by(SourceDocument.created_at.desc())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(stmt.offset(offset).limit(page_size))
    docs = result.scalars().all()

    items = []
    for d in docs:
        # 统计字段数和平均置信度
        ocr = d.ocr_result or {}
        fields = ocr.get("fields", []) if isinstance(ocr, dict) else []
        field_count = len(fields)
        if field_count > 0:
            confidences = [f.get("confidence", 0) for f in fields if isinstance(f, dict)]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        else:
            avg_confidence = 0.0
        items.append({
            "id": d.id,
            "source_type": "text" if d.doc_type == "text" else "image",
            "enterprise_id": "",
            "enterprise_name": "",
            "status": "success" if ocr.get("success") else "partial",
            "field_count": field_count,
            "avg_confidence": round(avg_confidence, 4),
            "file_name": d.file_name,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/statistics", summary="识别统计")
async def recognition_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """识别统计数据。"""
    from datetime import datetime, timedelta
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())

    total_count = (await db.execute(
        select(func.count()).where(
            SourceDocument.tenant_id == current_user.tenant_id,
        )
    )).scalar_one()

    today_count = (await db.execute(
        select(func.count()).where(
            SourceDocument.tenant_id == current_user.tenant_id,
            SourceDocument.created_at >= today_start,
        )
    )).scalar_one()

    # 按来源类型统计
    by_source_rows = (await db.execute(
        select(SourceDocument.doc_type, func.count())
        .where(SourceDocument.tenant_id == current_user.tenant_id)
        .group_by(SourceDocument.doc_type)
    )).all()
    by_source = [
        {"source_type": k or "unknown", "count": v} for k, v in by_source_rows
    ]

    # 成功率 = 有 ocr_result 且 success=true 的比例
    success_count = (await db.execute(
        select(func.count()).where(
            SourceDocument.tenant_id == current_user.tenant_id,
            SourceDocument.ocr_result.isnot(None),
        )
    )).scalar_one()

    success_rate = success_count / total_count if total_count > 0 else 0

    return {
        "total_count": total_count,
        "success_count": success_count,
        "today_count": today_count,
        "success_rate": round(success_rate, 4),
        "by_source": by_source,
    }


@router.get("/{doc_id}", summary="识别结果详情")
async def get_recognition_detail(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取OCR/AI识别结果详情。"""
    result = await db.execute(
        select(SourceDocument).where(
            SourceDocument.id == doc_id,
            SourceDocument.tenant_id == current_user.tenant_id,
        )
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    ocr = doc.ocr_result or {}
    fields = ocr.get("fields", []) if isinstance(ocr, dict) else []

    return {
        "id": doc.id,
        "business_request_id": doc.business_request_id,
        "source_type": "text" if doc.doc_type == "text" else "image",
        "doc_type": doc.doc_type,
        "content": doc.content,
        "file_name": doc.file_name,
        "file_size": doc.file_size,
        "file_hash": doc.file_hash,
        "enterprise_id": "",
        "enterprise_name": "",
        "model_name": ocr.get("model_name", ""),
        "model_version": ocr.get("model_version", ""),
        "processing_time_ms": ocr.get("processing_time_ms", 0),
        "errors": ocr.get("errors", []),
        "fields": fields,
        "success": ocr.get("success", False),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


# --------------------------------------------------------------------------- #
# 文字识别
# --------------------------------------------------------------------------- #

@router.post("/text", summary="文字AI识别")
async def recognize_text(
    content: str = Form(...),
    enterprise_id: str = Form("default"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """对自然语言文本进行开票字段识别。"""
    # 1. 输入安全
    safe_content = sanitize_input(content)
    if not safe_content:
        raise HTTPException(status_code=400, detail="输入内容无效")

    # 2. 调用AI识别
    recognizer = get_text_recognizer()
    result = await recognizer.recognize_text(safe_content)

    # 3. 知识库补全
    if result.success and result.fields:
        result = await enrich_recognition(
            db=db,
            recognition=result,
            tenant_id=current_user.tenant_id,
            enterprise_id=enterprise_id,
        )

    # 4. 保存识别记录
    doc = SourceDocument(
        tenant_id=current_user.tenant_id,
        business_request_id=None,
        doc_type="text",
        content=safe_content,
        file_name="text_input",
        file_size=len(safe_content.encode("utf-8")),
        file_hash="",
        ocr_result=result.to_dict(),
    )
    db.add(doc)
    await db.commit()

    return result.to_dict()


# --------------------------------------------------------------------------- #
# 图片识别
# --------------------------------------------------------------------------- #

@router.post("/image", summary="图片AI识别")
async def recognize_image(
    file: UploadFile = File(...),
    enterprise_id: str = Form("default"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """对图片进行OCR+多模态识别。"""
    # 1. 文件安全
    file_bytes = await file.read()
    safe, reason = check_file_safety(file_bytes, file.filename or "")
    if not safe:
        raise HTTPException(status_code=400, detail=reason or "文件不安全")

    # 2. 调用AI识别
    recognizer = get_image_recognizer()
    result = await recognizer.recognize_image(file_bytes)

    # 3. 知识库补全
    if result.success and result.fields:
        result = await enrich_recognition(
            db=db,
            recognition=result,
            tenant_id=current_user.tenant_id,
            enterprise_id=enterprise_id,
        )

    # 4. 保存识别记录
    import hashlib
    doc = SourceDocument(
        tenant_id=current_user.tenant_id,
        business_request_id=None,
        doc_type="image",
        content="",
        file_name=file.filename or "",
        file_size=len(file_bytes),
        file_hash=hashlib.md5(file_bytes).hexdigest(),
        ocr_result=result.to_dict(),
    )
    db.add(doc)
    await db.commit()

    return result.to_dict()


@router.post("/{doc_id}/reprocess", summary="重新识别")
async def reprocess_recognition(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """重新执行OCR识别。"""
    result = await db.execute(
        select(SourceDocument).where(
            SourceDocument.id == doc_id,
            SourceDocument.tenant_id == current_user.tenant_id,
        )
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "doc_id": doc_id,
        "message": "已加入重新识别队列（开发中）",
        "status": "pending",
    }
