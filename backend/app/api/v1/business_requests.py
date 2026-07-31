"""业务申请路由。

提交开票申请后自动走完：识别 → 创建开票请求 → 校验 → 创建开票任务 → 执行开票 → 回写结果。
"""

import hashlib
import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.business import BusinessRequest, SourceDocument
from app.models.enterprise import Enterprise, EnterpriseConfig
from app.models.invoice import InvoiceItem, InvoiceRequest
from app.models.invoice_task import InvoiceResult, InvoiceTask
from app.models.task import ImportBatch
from app.models.user import User
from app.schemas.business import BusinessRequestResponse, SourceDocumentResponse
from app.schemas.common import PaginatedResponse
from app.services.audit_service import log_action
from app.services.invoice_service import (
    calculate_invoice_amounts,
    create_invoice_request_from_business_request,
    create_invoice_task,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/business-requests", tags=["业务申请"])


# --------------------------------------------------------------------------- #
# 自动处理链路：申请 → 识别 → 校验 → 开票 → 结果
# --------------------------------------------------------------------------- #

async def _auto_process_request(
    db: AsyncSession,
    br: BusinessRequest,
    content: str | None = None,
    current_user: User | None = None,
):
    """自动处理业务申请：AI识别 → 创建开票请求 → 校验 → 创建任务 → 模拟开票。"""
    tenant_id = br.tenant_id
    enterprise_id = br.enterprise_id

    try:
        # 1. 获取企业信息
        ent_result = await db.execute(
            select(Enterprise).where(
                Enterprise.id == enterprise_id,
                Enterprise.tenant_id == tenant_id,
            )
        )
        enterprise = ent_result.scalar_one_or_none()
        if not enterprise:
            br.status = "failed"
            br.current_stage = "enterprise_not_found"
            await db.commit()
            return

        # 2. AI识别（如果提供了文字内容）
        invoice_data = None
        if content:
            try:
                from app.services.ai import get_text_recognizer
                from app.services.ai.knowledge_matcher import enrich_recognition

                recognizer = get_text_recognizer()
                recognition = await recognizer.recognize_text(content)

                if recognition.success and recognition.fields:
                    recognition = await enrich_recognition(
                        db=db,
                        recognition=recognition,
                        tenant_id=tenant_id,
                        enterprise_id=enterprise_id,
                    )

                # 从识别结果构建开票数据
                invoice_data = _build_invoice_data_from_recognition(recognition, enterprise)
                br.current_stage = "recognized"

                # 保存识别结果到 SourceDocument
                doc_result = await db.execute(
                    select(SourceDocument).where(SourceDocument.business_request_id == br.id)
                )
                doc = doc_result.scalar_one_or_none()
                if doc:
                    doc.ocr_result = recognition.to_dict()
            except Exception as e:
                logger.warning("AI识别失败，使用默认值: %s", e)
                br.current_stage = "recognition_failed"

        # 如果识别失败，使用默认值（允许手动补充）
        if not invoice_data:
            invoice_data = _build_default_invoice_data(enterprise, content or "")

        # 3. 创建开票请求
        invoice_request = await create_invoice_request_from_business_request(
            db=db,
            tenant_id=tenant_id,
            enterprise_id=enterprise_id,
            business_request=br,
            invoice_data=invoice_data,
            created_by=current_user.id if current_user else None,
        )
        br.current_stage = "invoice_request_created"

        # 4. 创建开票任务
        idempotency_key = hashlib.sha256(
            f"{tenant_id}:{enterprise_id}:{br.external_order_no or br.id}:{invoice_data.get('total_with_tax', '')}".encode()
        ).hexdigest()

        task = await create_invoice_task(
            db=db,
            tenant_id=tenant_id,
            enterprise_id=enterprise_id,
            invoice_request=invoice_request,
            idempotency_key=idempotency_key,
        )
        task.status = "pending_submit"
        br.current_stage = "task_created"
        await db.flush()

        # 5. 执行开票（调用模拟通道）
        await _execute_invoice(db, task, invoice_request, enterprise)
        br.status = "processed"
        await db.commit()

    except Exception as e:
        logger.error("自动处理业务申请失败: %s", e, exc_info=True)
        br.status = "failed"
        br.current_stage = f"error: {str(e)[:200]}"
        await db.commit()


def _build_invoice_data_from_recognition(recognition, enterprise: Enterprise) -> dict:
    """从AI识别结果构建开票数据。"""

    def get_val(name):
        f = recognition.get_field(name)
        return f.value if f else None

    buyer_name = get_val("buyer_name") or "客户"
    total_with_tax = get_val("total_with_tax") or get_val("total_amount") or Decimal("0")
    tax_rate = get_val("tax_rate")
    if tax_rate is not None:
        tax_rate = Decimal(str(tax_rate))
        # 如果税率 > 1，说明是百分数（如 6 表示 6%），转为小数
        if tax_rate > 1:
            tax_rate = tax_rate / 100
    else:
        tax_rate = Decimal("0.06")

    receiver_email = get_val("receiver_email") or ""
    product_name = get_val("product_name") or "服务费"

    # 含税金额
    total_with_tax = Decimal(str(total_with_tax))
    total_amount = (total_with_tax / (1 + tax_rate)).quantize(Decimal("0.01"))
    total_tax = (total_with_tax - total_amount).quantize(Decimal("0.01"))

    return {
        "invoice_type": "electronic_normal",
        "buyer_name": buyer_name,
        "buyer_tax_no": get_val("buyer_tax_no"),
        "buyer_address": None,
        "buyer_phone": None,
        "buyer_bank_name": None,
        "buyer_bank_account": None,
        "is_tax_inclusive": True,
        "remark": "",
        "receiver_email": receiver_email,
        "receiver_mobile": get_val("receiver_mobile"),
        "config_snapshot": {},
        "items": [
            {
                "product_name": product_name,
                "tax_code": None,
                "spec": None,
                "unit": "次",
                "quantity": 1,
                "unit_price": float(total_with_tax),
                "tax_rate": float(tax_rate),
                "discount_amount": 0,
            }
        ],
    }


def _build_default_invoice_data(enterprise: Enterprise, content: str) -> dict:
    """构建默认开票数据（识别失败时使用）。"""
    return {
        "invoice_type": "electronic_normal",
        "buyer_name": "客户",
        "buyer_tax_no": None,
        "buyer_address": None,
        "buyer_phone": None,
        "buyer_bank_name": None,
        "buyer_bank_account": None,
        "is_tax_inclusive": True,
        "remark": "",
        "receiver_email": "",
        "receiver_mobile": None,
        "config_snapshot": {},
        "items": [
            {
                "product_name": "服务费",
                "tax_code": None,
                "spec": None,
                "unit": "次",
                "quantity": 1,
                "unit_price": 0,
                "tax_rate": 0.06,
                "discount_amount": 0,
            }
        ],
    }


def _record_task_audit(
    db: AsyncSession,
    task: InvoiceTask,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """追加系统开票执行审计记录。"""
    db.add(AuditLog(
        tenant_id=task.tenant_id,
        user_id=None,
        action=action,
        entity_type="invoice_task",
        entity_id=task.id,
        before_value=before or {},
        after_value=after or {},
    ))


async def _execute_invoice(
    db: AsyncSession,
    task: InvoiceTask,
    invoice_request: InvoiceRequest,
    enterprise: Enterprise,
):
    """执行开票（调用模拟通道）。"""
    from app.services.channels.registry import ChannelRegistry

    # 获取通道（优先 mock，开发阶段使用模拟通道）
    channel = ChannelRegistry.get("mock")
    if not channel:
        logger.error("模拟通道不可用")
        task.status = "failed"
        task.last_error = "模拟通道不可用"
        return

    # 构建开票请求数据
    items_result = await db.execute(
        select(InvoiceItem).where(InvoiceItem.invoice_request_id == invoice_request.id)
    )
    items = items_result.scalars().all()

    channel_request = {
        "invoice_type": invoice_request.invoice_type,
        "seller_tax_no": enterprise.tax_no or "",
        "seller_name": enterprise.name,
        "seller_address": enterprise.address or "",
        "seller_phone": enterprise.phone or "",
        "seller_bank_name": enterprise.bank_name or "",
        "seller_bank_account": enterprise.bank_account or "",
        "buyer_name": invoice_request.buyer_name,
        "buyer_tax_no": invoice_request.buyer_tax_no or "",
        "buyer_address": invoice_request.buyer_address or "",
        "buyer_phone": invoice_request.buyer_phone or "",
        "buyer_bank_name": invoice_request.buyer_bank_name or "",
        "buyer_bank_account": invoice_request.buyer_bank_account or "",
        "is_tax_inclusive": invoice_request.is_tax_inclusive,
        "total_amount": float(invoice_request.total_amount),
        "total_tax": float(invoice_request.total_tax),
        "total_with_tax": float(invoice_request.total_with_tax),
        "remark": invoice_request.remark or "",
        "external_order_no": "",
        "items": [
            {
                "product_name": item.product_name,
                "tax_code": item.tax_code or "",
                "spec": item.spec or "",
                "unit": item.unit or "",
                "quantity": float(item.quantity),
                "unit_price": float(item.unit_price),
                "tax_rate": float(item.tax_rate),
                "amount": float(item.amount),
                "tax_amount": float(item.tax_amount),
            }
            for item in items
        ],
    }

    # 提交开票
    previous_status = task.status
    task.status = "submitting"
    task.submitted_at = func.now()
    _record_task_audit(
        db, task, "提交开票通道",
        before={"status": previous_status},
        after={"status": "submitting", "enterprise_id": enterprise.id},
    )
    await db.flush()

    try:
        result = await channel.issue_invoice(channel_request)

        if result.is_unknown:
            task.status = "unknown"
            task.last_error = result.error_message or "开票结果未知"
            _record_task_audit(
                db, task, "开票结果未知",
                before={"status": "submitting"},
                after={"status": "unknown", "error": task.last_error},
            )
        elif result.success:
            task.status = "success"
            task.completed_at = func.now()
            _record_task_audit(
                db, task, "开票成功",
                before={"status": "submitting"},
                after={"status": "success", "channel_business_no": result.channel_business_no},
            )

            # 保存开票结果
            invoice_result = InvoiceResult(
                tenant_id=task.tenant_id,
                invoice_task_id=task.id,
                invoice_number=result.channel_business_no or f"MOCK-{task.id[:8].upper()}",
                invoice_code="",
                invoice_date=None,
                total_amount=invoice_request.total_amount,
                total_tax=invoice_request.total_tax,
                total_with_tax=invoice_request.total_with_tax,
                buyer_name=invoice_request.buyer_name,
                seller_name=enterprise.name,
                file_status="available",
                file_key=f"mock/{task.id}.pdf",
                file_hash="",
                verified=True,
            )
            db.add(invoice_result)
        else:
            task.status = "failed"
            task.last_error = result.error_message or "开票失败"
            task.retry_count = (task.retry_count or 0) + 1
            _record_task_audit(
                db, task, "开票失败",
                before={"status": "submitting"},
                after={"status": "failed", "error": task.last_error},
            )

    except Exception as e:
        logger.error("开票执行异常: %s", e)
        task.status = "failed"
        task.last_error = str(e)[:500]
        _record_task_audit(
            db, task, "开票执行异常",
            before={"status": "submitting"},
            after={"status": "failed", "error": task.last_error},
        )

    # 推送企业微信通知（异步，不阻塞主流程）
    try:
        from app.services.wechat_service import wecom_service
        if wecom_service.enabled:
            amount_str = str(invoice_request.total_with_tax) if invoice_request.total_with_tax else "—"
            await wecom_service.notify_invoice_result(
                user_ids="@all",
                enterprise_name=enterprise.name,
                invoice_number=result.channel_business_no if 'result' in dir() else "",
                amount=amount_str,
                status=task.status,
                error_msg=task.last_error or "",
            )
    except Exception as notify_err:
        logger.warning("企业微信通知发送失败: %s", notify_err)


# --------------------------------------------------------------------------- #
# API 路由
# --------------------------------------------------------------------------- #

async def _build_detail_response(db: AsyncSession, br: BusinessRequest, tenant_id: str) -> dict:
    """构建业务申请详情响应（含来源单据和开票任务）。"""
    docs_result = await db.execute(
        select(SourceDocument).where(SourceDocument.business_request_id == br.id)
    )
    docs = [SourceDocumentResponse.model_validate(d) for d in docs_result.scalars().all()]

    from app.models.invoice import InvoiceRequest
    from app.models.invoice_task import InvoiceTask, InvoiceResult
    from app.models.enterprise import Enterprise

    # 查询关联企业
    ent_result = await db.execute(
        select(Enterprise).where(Enterprise.id == br.enterprise_id)
    )
    enterprise = ent_result.scalar_one_or_none()

    inv_result = await db.execute(
        select(InvoiceRequest).where(InvoiceRequest.business_request_id == br.id)
    )
    invoice_requests = inv_result.scalars().all()

    tasks_data = []
    for inv_req in invoice_requests:
        task_result = await db.execute(
            select(InvoiceTask).where(InvoiceTask.invoice_request_id == inv_req.id)
        )
        tasks = task_result.scalars().all()
        for task in tasks:
            result_result = await db.execute(
                select(InvoiceResult).where(InvoiceResult.invoice_task_id == task.id)
            )
            inv_result_obj = result_result.scalar_one_or_none()
            tasks_data.append({
                "task_id": task.id,
                "task_status": task.status,
                "invoice_request_id": inv_req.id,
                "buyer_name": inv_req.buyer_name,
                "total_with_tax": float(inv_req.total_with_tax),
                "invoice_number": inv_result_obj.invoice_number if inv_result_obj else None,
                "file_status": inv_result_obj.file_status if inv_result_obj else None,
                "last_error": task.last_error,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            })

    return {
        **BusinessRequestResponse.model_validate(br).model_dump(),
        "enterprise_id": br.enterprise_id,
        "enterprise_name": enterprise.name if enterprise else None,
        "source_documents": [d.model_dump() for d in docs],
        "invoice_tasks": tasks_data,
    }


async def _resolve_enterprise_id(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str | None = None,
    hint_text: str = "",
    seller_tax_no: str | None = None,
) -> str:
    """自动确定销方企业。

    优先级：显式企业ID → 销方税号 → 原始文本中的企业全称 → 仅有一家启用企业。
    多家企业且没有可靠依据时拒绝自动开票，防止错误销方开票。
    """
    base_stmt = select(Enterprise).where(
        Enterprise.tenant_id == tenant_id,
        Enterprise.status == "active",
    )

    if enterprise_id:
        result = await db.execute(base_stmt.where(Enterprise.id == enterprise_id))
        enterprise = result.scalar_one_or_none()
        if not enterprise:
            raise HTTPException(status_code=400, detail="指定销方企业不存在或未启用")
        return enterprise.id

    active_enterprises = (await db.execute(base_stmt.order_by(Enterprise.created_at.asc()))).scalars().all()
    if not active_enterprises:
        raise HTTPException(status_code=400, detail="没有启用的销方企业，请先完成企业接入")

    if seller_tax_no:
        normalized_tax_no = seller_tax_no.strip().upper()
        for enterprise in active_enterprises:
            if (enterprise.tax_no or "").upper() == normalized_tax_no:
                return enterprise.id

    # 以企业名称匹配，优先最长名称避免短名称误匹配
    normalized_hint = hint_text.replace(" ", "")
    matches = [
        enterprise for enterprise in active_enterprises
        if enterprise.name and enterprise.name.replace(" ", "") in normalized_hint
    ]
    if len(matches) == 1:
        return matches[0].id
    if len(matches) > 1:
        matches.sort(key=lambda enterprise: len(enterprise.name), reverse=True)
        return matches[0].id

    if len(active_enterprises) == 1:
        return active_enterprises[0].id

    # 不允许默认挑第一家企业：真实环境会造成错销方开票。
    raise HTTPException(
        status_code=409,
        detail={
            "message": "无法从资料中确认销方企业，请通过企业专属提交链接、Excel“企业名称”列或在文字中注明销方企业名称后重试",
            "candidates": [{"id": e.id, "name": e.name, "tax_no": e.tax_no} for e in active_enterprises[:20]],
        },
    )


async def _create_business_request(
    db: AsyncSession,
    tenant_id: str,
    enterprise_id: str,
    source_type: str,
    current_user: User,
    content: str | None = None,
    external_order_no: str | None = None,
    customer_remark: str | None = None,
    urgency: str = "normal",
    file: UploadFile | None = None,
) -> BusinessRequest:
    """创建业务申请并关联来源单据。"""
    br = BusinessRequest(
        id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        enterprise_id=enterprise_id,
        source_type=source_type,
        external_order_no=external_order_no,
        customer_remark=customer_remark,
        urgency=urgency,
        status="pending",
        created_by=current_user.id,
    )
    db.add(br)
    await db.flush()

    # 创建来源单据
    doc = SourceDocument(
        id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        business_request_id=br.id,
        doc_type="text" if source_type == "text" else ("image" if source_type == "image" else "excel"),
        content=content,
    )
    if file:
        file_bytes = await file.read()
        doc.file_name = file.filename
        doc.file_size = len(file_bytes)
        doc.file_hash = hashlib.sha256(file_bytes).hexdigest()

    db.add(doc)
    await log_action(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="create_business_request",
        entity_type="business_request",
        entity_id=br.id,
        after={"source_type": source_type, "enterprise_id": enterprise_id},
    )
    await db.commit()
    await db.refresh(br)
    return br


@router.post("/text", status_code=status.HTTP_201_CREATED, summary="文字提交开票")
async def submit_text(
    content: str = Form(...),
    enterprise_id: str | None = Form(None, description="销方企业ID（可选，自动匹配）"),
    external_order_no: str | None = Form(None),
    customer_remark: str | None = Form(None),
    urgency: str = Form("normal"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """文字方式提交开票申请。

    提交后自动执行：AI识别 → 自动匹配企业 → 创建开票请求 → 模拟开票 → 回写结果。
    如果不传 enterprise_id，系统自动匹配：
    1. 只有1家企业 → 自动使用
    2. 多家企业 → 从文字中识别企业名称匹配
    3. 匹配不到 → 使用第1家企业（用户可在结果中修改）
    """
    enterprise_id = await _resolve_enterprise_id(
        db=db,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        hint_text=content,
    )

    br = await _create_business_request(
        db,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        source_type="text",
        current_user=current_user,
        content=content,
        external_order_no=external_order_no,
        customer_remark=customer_remark,
        urgency=urgency,
    )
    # 自动处理
    await _auto_process_request(db, br, content=content, current_user=current_user)
    await db.refresh(br)

    # 返回完整详情（含开票任务结果）
    return await _build_detail_response(db, br, current_user.tenant_id)


@router.post("/image", status_code=status.HTTP_201_CREATED, summary="图片提交开票")
async def submit_image(
    file: UploadFile = File(...),
    enterprise_id: str | None = Form(None, description="销方企业ID（可选，自动匹配）"),
    external_order_no: str | None = Form(None),
    customer_remark: str | None = Form(None),
    urgency: str = Form("normal"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """图片上传方式智能开票。

    页面不要求预先选择客户抬头；OCR先识别资料，系统再用税号/名称匹配企业和客户。
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传图片为空")

    from app.services.ai import get_image_recognizer
    from app.services.ai.knowledge_matcher import enrich_recognition

    recognizer = get_image_recognizer()
    recognition = await recognizer.recognize_image(file_bytes)
    raw_text = "\n".join(
        str(field.raw_text or field.value or "") for field in recognition.fields
    )
    seller_tax_no = next(
        (str(field.value) for field in recognition.fields if field.field_name == "seller_tax_no"),
        None,
    )
    enterprise_id = await _resolve_enterprise_id(
        db=db,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        hint_text=raw_text,
        seller_tax_no=seller_tax_no,
    )

    # UploadFile 已读取，复位后保存原文件。
    await file.seek(0)
    br = await _create_business_request(
        db,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        source_type="image",
        current_user=current_user,
        external_order_no=external_order_no,
        customer_remark=customer_remark,
        urgency=urgency,
        file=file,
    )

    try:
        if recognition.success and recognition.fields:
            recognition = await enrich_recognition(
                db=db,
                recognition=recognition,
                tenant_id=current_user.tenant_id,
                enterprise_id=enterprise_id,
            )

        doc = (await db.execute(
            select(SourceDocument).where(SourceDocument.business_request_id == br.id)
        )).scalar_one_or_none()
        if doc:
            doc.ocr_result = recognition.to_dict()

        enterprise = (await db.execute(
            select(Enterprise).where(Enterprise.id == enterprise_id)
        )).scalar_one()
        invoice_data = (
            _build_invoice_data_from_recognition(recognition, enterprise)
            if recognition.success else _build_default_invoice_data(enterprise, "")
        )
        invoice_request = await create_invoice_request_from_business_request(
            db=db,
            tenant_id=current_user.tenant_id,
            enterprise_id=enterprise_id,
            business_request=br,
            invoice_data=invoice_data,
            created_by=current_user.id,
        )
        task = await create_invoice_task(
            db=db,
            tenant_id=current_user.tenant_id,
            enterprise_id=enterprise_id,
            invoice_request=invoice_request,
            idempotency_key=hashlib.sha256(
                f"{current_user.tenant_id}:{enterprise_id}:{br.id}".encode()
            ).hexdigest(),
        )
        task.status = "pending_submit"
        await _execute_invoice(db, task, invoice_request, enterprise)
        br.status = "processed"
        br.current_stage = "completed"
        await db.commit()
    except Exception as exc:
        logger.error("图片开票处理失败: %s", exc, exc_info=True)
        br.status = "failed"
        br.current_stage = f"error: {str(exc)[:200]}"
        await db.commit()

    await db.refresh(br)
    return await _build_detail_response(db, br, current_user.tenant_id)


@router.post("/excel", status_code=status.HTTP_201_CREATED, summary="Excel批量智能开票")
async def submit_excel(
    file: UploadFile = File(...),
    enterprise_id: str | None = Form(None, description="销方企业ID（可选，自动匹配）"),
    external_order_no: str | None = Form(None),
    customer_remark: str | None = Form(None),
    urgency: str = Form("normal"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Excel批量智能开票。

    标准模板含“企业名称”列时自动匹配销方；没有该列且仅有一家启用企业时自动使用。
    购方由每行的“购方名称/购方税号”自动创建开票数据，不要求预先维护抬头。
    """
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="当前仅支持 .xlsx 标准模板文件")

    from app.services.excel_service import parse_standard_excel, validate_excel_row

    file_bytes = await file.read()
    try:
        rows = parse_standard_excel(file_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Excel解析失败: {exc}")

    enterprise_hints = {
        str(row.get("enterprise_name", "")).strip()
        for row in rows if row.get("enterprise_name")
    }
    if len(enterprise_hints) > 1 and not enterprise_id:
        raise HTTPException(
            status_code=409,
            detail="同一Excel包含多个销方企业，请按企业拆分文件，或通过企业专属提交链接导入",
        )
    enterprise_id = await _resolve_enterprise_id(
        db=db,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        hint_text=next(iter(enterprise_hints), ""),
    )

    await file.seek(0)
    br = await _create_business_request(
        db,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        source_type="excel",
        current_user=current_user,
        external_order_no=external_order_no,
        customer_remark=customer_remark,
        urgency=urgency,
        file=file,
    )

    # 一个Excel文件对应一个可追踪导入批次；任务、异常和结果均可回到该批次。
    batch = ImportBatch(
        tenant_id=current_user.tenant_id,
        source_type="excel",
        created_by=current_user.id,
        enterprise_count=1,
        task_count=0,
        success_count=0,
        failure_count=0,
        exception_count=0,
        status="processing",
        file_name=file.filename,
    )
    db.add(batch)
    await db.flush()

    enterprise = (await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id)
    )).scalar_one()
    valid_count = 0
    success_count = 0
    failure_count = 0
    invalid_rows: list[dict] = []

    for row in rows:
        errors = validate_excel_row(row)
        if errors:
            invalid_rows.append({"row": row.get("_row_number"), "errors": errors})
            continue
        tax_rate = Decimal(str(row.get("tax_rate") or "0.06"))
        if tax_rate > 1:
            tax_rate = tax_rate / 100
        invoice_data = {
            "invoice_type": row.get("invoice_type") or "electronic_normal",
            "buyer_name": str(row["buyer_name"]),
            "buyer_tax_no": str(row.get("buyer_tax_no") or "") or None,
            "buyer_address": str(row.get("buyer_address") or "") or None,
            "buyer_phone": str(row.get("buyer_phone") or "") or None,
            "buyer_bank_name": str(row.get("buyer_bank_name") or "") or None,
            "buyer_bank_account": str(row.get("buyer_bank_account") or "") or None,
            "is_tax_inclusive": True,
            "remark": str(row.get("remark") or ""),
            "receiver_email": str(row.get("receiver_email") or "") or None,
            "receiver_mobile": str(row.get("receiver_mobile") or "") or None,
            "config_snapshot": {},
            "items": [{
                "product_name": str(row["product_name"]),
                "tax_code": None,
                "spec": str(row.get("spec") or "") or None,
                "unit": str(row.get("unit") or "") or None,
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
                "tax_rate": tax_rate,
                "discount_amount": 0,
            }],
        }
        invoice_request = await create_invoice_request_from_business_request(
            db=db,
            tenant_id=current_user.tenant_id,
            enterprise_id=enterprise_id,
            business_request=br,
            invoice_data=invoice_data,
            created_by=current_user.id,
        )
        task = await create_invoice_task(
            db=db,
            tenant_id=current_user.tenant_id,
            enterprise_id=enterprise_id,
            invoice_request=invoice_request,
            idempotency_key=hashlib.sha256(
                f"{current_user.tenant_id}:{enterprise_id}:{br.id}:{row.get('_row_number')}".encode()
            ).hexdigest(),
        )
        task.import_batch_id = batch.id
        task.status = "pending_submit"
        await _execute_invoice(db, task, invoice_request, enterprise)
        valid_count += 1
        if task.status == "success":
            success_count += 1
        else:
            failure_count += 1

    batch.task_count = valid_count
    batch.success_count = success_count
    batch.failure_count = failure_count
    batch.exception_count = len(invalid_rows) + failure_count
    batch.status = "completed" if batch.exception_count == 0 else ("partial" if success_count else "failed")

    doc = (await db.execute(
        select(SourceDocument).where(SourceDocument.business_request_id == br.id)
    )).scalar_one_or_none()
    if doc:
        doc.ocr_result = {
            "success": valid_count > 0,
            "source": "excel",
            "total_rows": len(rows),
            "success_count": valid_count,
            "invalid_rows": invalid_rows,
        }
    br.status = "processed" if valid_count else "failed"
    br.current_stage = f"completed:{valid_count}; invalid:{len(invalid_rows)}"
    await db.commit()
    await db.refresh(br)
    return await _build_detail_response(db, br, current_user.tenant_id)


@router.get("", response_model=PaginatedResponse[BusinessRequestResponse], summary="业务申请列表")
async def list_business_requests(
    enterprise_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询业务申请列表。"""
    stmt = select(BusinessRequest).where(BusinessRequest.tenant_id == current_user.tenant_id)
    if enterprise_id:
        stmt = stmt.where(BusinessRequest.enterprise_id == enterprise_id)
    if status_filter:
        stmt = stmt.where(BusinessRequest.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.order_by(BusinessRequest.created_at.desc()).offset(offset).limit(page_size)
    )
    items = [BusinessRequestResponse.model_validate(r) for r in result.scalars().all()]
    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/{request_id}", summary="业务申请详情")
async def get_business_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取业务申请详情（含来源单据和开票任务）。"""
    result = await db.execute(
        select(BusinessRequest).where(
            BusinessRequest.id == request_id,
            BusinessRequest.tenant_id == current_user.tenant_id,
        )
    )
    br = result.scalar_one_or_none()
    if br is None:
        raise HTTPException(status_code=404, detail="业务申请不存在")

    docs_result = await db.execute(
        select(SourceDocument).where(SourceDocument.business_request_id == br.id)
    )
    docs = [SourceDocumentResponse.model_validate(d) for d in docs_result.scalars().all()]

    # 查询关联的开票请求和任务
    from app.models.invoice import InvoiceRequest
    from app.models.invoice_task import InvoiceTask, InvoiceResult

    inv_result = await db.execute(
        select(InvoiceRequest).where(InvoiceRequest.business_request_id == br.id)
    )
    invoice_requests = inv_result.scalars().all()

    tasks_data = []
    for inv_req in invoice_requests:
        task_result = await db.execute(
            select(InvoiceTask).where(InvoiceTask.invoice_request_id == inv_req.id)
        )
        tasks = task_result.scalars().all()
        for task in tasks:
            result_result = await db.execute(
                select(InvoiceResult).where(InvoiceResult.invoice_task_id == task.id)
            )
            inv_result_obj = result_result.scalar_one_or_none()
            tasks_data.append({
                "task_id": task.id,
                "task_status": task.status,
                "invoice_request_id": inv_req.id,
                "buyer_name": inv_req.buyer_name,
                "total_with_tax": float(inv_req.total_with_tax),
                "invoice_number": inv_result_obj.invoice_number if inv_result_obj else None,
                "file_status": inv_result_obj.file_status if inv_result_obj else None,
                "last_error": task.last_error,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            })

    return {
        **BusinessRequestResponse.model_validate(br).model_dump(),
        "source_documents": docs,
        "invoice_tasks": tasks_data,
    }
