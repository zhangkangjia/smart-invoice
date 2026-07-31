"""开票任务路由。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.enterprise import Enterprise
from app.models.invoice import InvoiceRequest
from app.models.invoice_task import (
    DeliveryTask,
    ExceptionCase,
    InvoiceResult,
    InvoiceTask,
    ReconciliationCase,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/invoice-tasks", tags=["开票任务"])


@router.get("", summary="任务列表")
async def list_invoice_tasks(
    enterprise_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询开票任务列表。"""
    stmt = select(InvoiceTask).where(InvoiceTask.tenant_id == current_user.tenant_id)
    if enterprise_id:
        stmt = stmt.where(InvoiceTask.enterprise_id == enterprise_id)
    if status_filter:
        stmt = stmt.where(InvoiceTask.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.order_by(InvoiceTask.created_at.desc()).offset(offset).limit(page_size)
    )
    tasks = result.scalars().all()

    # 批量加载关联数据，避免列表页产生 N+1 查询。
    enterprise_ids = list({task.enterprise_id for task in tasks})
    request_ids = list({task.invoice_request_id for task in tasks})
    enterprises = {}
    requests = {}
    if enterprise_ids:
        enterprise_rows = await db.execute(
            select(Enterprise).where(Enterprise.id.in_(enterprise_ids))
        )
        enterprises = {enterprise.id: enterprise for enterprise in enterprise_rows.scalars().all()}
    if request_ids:
        request_rows = await db.execute(
            select(InvoiceRequest).where(InvoiceRequest.id.in_(request_ids))
        )
        requests = {invoice_request.id: invoice_request for invoice_request in request_rows.scalars().all()}

    return {
        "items": [
            {
                "id": task.id,
                "enterprise_id": task.enterprise_id,
                "enterprise_name": enterprises.get(task.enterprise_id).name if enterprises.get(task.enterprise_id) else None,
                "invoice_request_id": task.invoice_request_id,
                "buyer_name": requests.get(task.invoice_request_id).buyer_name if requests.get(task.invoice_request_id) else None,
                "total_amount": float(requests.get(task.invoice_request_id).total_amount or 0) if requests.get(task.invoice_request_id) else 0,
                "total_tax": float(requests.get(task.invoice_request_id).total_tax or 0) if requests.get(task.invoice_request_id) else 0,
                "total_with_tax": float(requests.get(task.invoice_request_id).total_with_tax or 0) if requests.get(task.invoice_request_id) else 0,
                "status": task.status,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "last_error": task.last_error,
                "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
            }
            for task in tasks
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{task_id}", summary="任务详情")
async def get_invoice_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取开票任务详情。"""
    result = await db.execute(
        select(InvoiceTask).where(
            InvoiceTask.id == task_id,
            InvoiceTask.tenant_id == current_user.tenant_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    enterprise = (await db.execute(
        select(Enterprise).where(
            Enterprise.id == task.enterprise_id,
            Enterprise.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    invoice_request = (await db.execute(
        select(InvoiceRequest)
        .options(selectinload(InvoiceRequest.items))
        .where(
            InvoiceRequest.id == task.invoice_request_id,
            InvoiceRequest.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    invoice_result = (await db.execute(
        select(InvoiceResult).where(
            InvoiceResult.invoice_task_id == task.id,
            InvoiceResult.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    audit_logs = (await db.execute(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.entity_id == task.id,
        )
        .order_by(AuditLog.created_at.asc())
    )).scalars().all()

    # 即使早期任务缺少审计日志，也由任务自身状态生成可读时间线。
    timeline = [
        {
            "action": "开票任务已创建",
            "status": "pending_validation",
            "operator_name": "系统",
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "remark": "系统已生成开票任务",
        },
    ]
    if task.submitted_at:
        timeline.append({
            "action": "已提交开票通道",
            "status": "submitting",
            "operator_name": "系统",
            "created_at": task.submitted_at.isoformat(),
            "remark": "已请求开票通道处理",
        })
    if task.completed_at:
        timeline.append({
            "action": "开票成功" if task.status == "success" else "任务处理完成",
            "status": task.status,
            "operator_name": "系统",
            "created_at": task.completed_at.isoformat(),
            "remark": invoice_result.invoice_number if invoice_result else task.last_error,
        })
    for log in audit_logs:
        timeline.append({
            "action": log.action,
            "status": (log.after_value or {}).get("status", task.status),
            "operator_name": log.user_id or "系统",
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "remark": (log.after_value or {}).get("reason") or "",
        })
    timeline.sort(key=lambda item: item.get("created_at") or "")

    return {
        "id": task.id,
        "enterprise_id": task.enterprise_id,
        "enterprise_name": enterprise.name if enterprise else None,
        "enterprise_tax_no": enterprise.tax_no if enterprise else None,
        "invoice_request_id": task.invoice_request_id,
        "import_batch_id": task.import_batch_id,
        "idempotency_key": task.idempotency_key,
        "status": task.status,
        "channel_submission_id": task.channel_submission_id,
        "worker_node": task.worker_node,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
        "last_error": task.last_error,
        "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "invoice_request": {
            "id": invoice_request.id,
            "invoice_type": invoice_request.invoice_type,
            "buyer_name": invoice_request.buyer_name,
            "buyer_tax_no": invoice_request.buyer_tax_no,
            "buyer_address": invoice_request.buyer_address,
            "buyer_phone": invoice_request.buyer_phone,
            "buyer_bank_name": invoice_request.buyer_bank_name,
            "buyer_bank_account": invoice_request.buyer_bank_account,
            "total_amount": float(invoice_request.total_amount or 0),
            "total_tax": float(invoice_request.total_tax or 0),
            "total_with_tax": float(invoice_request.total_with_tax or 0),
            "remark": invoice_request.remark,
            "receiver_email": invoice_request.receiver_email,
            "items": [
                {
                    "id": item.id,
                    "product_name": item.product_name,
                    "tax_code": item.tax_code,
                    "spec": item.spec,
                    "unit": item.unit,
                    "quantity": float(item.quantity or 0),
                    "unit_price": float(item.unit_price or 0),
                    "amount": float(item.amount or 0),
                    "tax_rate": float(item.tax_rate or 0),
                    "tax_amount": float(item.tax_amount or 0),
                    "total_with_tax": float(item.total_with_tax or 0),
                }
                for item in invoice_request.items
            ],
        } if invoice_request else None,
        "invoice_result": {
            "invoice_number": invoice_result.invoice_number,
            "invoice_code": invoice_result.invoice_code,
            "invoice_date": invoice_result.invoice_date.isoformat() if invoice_result.invoice_date else None,
            "file_status": invoice_result.file_status,
            "file_key": invoice_result.file_key,
            "verified": invoice_result.verified,
        } if invoice_result else None,
        "timeline": timeline,
        "audit_logs": [
            {
                "id": log.id,
                "action": log.action,
                "user_id": log.user_id,
                "before": log.before_value,
                "after": log.after_value,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in audit_logs
        ],
    }


@router.post("/{task_id}/retry", summary="重试任务")
async def retry_invoice_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """重试失败的开票任务。"""
    result = await db.execute(
        select(InvoiceTask).where(
            InvoiceTask.id == task_id,
            InvoiceTask.tenant_id == current_user.tenant_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status not in ("failed", "unknown"):
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 '{task.status}' 不允许重试，仅 failed/unknown 可重试",
        )

    if task.retry_count >= task.max_retries:
        raise HTTPException(
            status_code=400,
            detail=f"已达到最大重试次数 {task.max_retries}",
        )

    task.retry_count += 1
    task.status = "pending_submit"
    task.last_error = None
    await db.commit()
    return {"message": "任务已加入重试队列", "retry_count": task.retry_count}


@router.post("/{task_id}/cancel", summary="取消任务")
async def cancel_invoice_task(
    task_id: str,
    reason: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """取消开票任务。"""
    result = await db.execute(
        select(InvoiceTask).where(
            InvoiceTask.id == task_id,
            InvoiceTask.tenant_id == current_user.tenant_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status in ("success", "terminated"):
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 '{task.status}' 不允许取消",
        )

    old_status = task.status
    task.status = "terminated"
    task.last_error = f"手动取消: {reason or '无'}"

    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="cancel_invoice_task",
        entity_type="invoice_task",
        entity_id=task.id,
        before={"status": old_status},
        after={"status": "terminated", "reason": reason},
    ))
    await db.commit()
    return {"message": "任务已取消"}


@router.get("/{task_id}/result", summary="开票结果")
async def get_invoice_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取开票结果。"""
    result = await db.execute(
        select(InvoiceResult).where(
            InvoiceResult.tenant_id == current_user.tenant_id,
            InvoiceResult.invoice_task_id == task_id,
        )
    )
    inv_result = result.scalar_one_or_none()
    if inv_result is None:
        raise HTTPException(status_code=404, detail="开票结果不存在")

    # 查询交付任务
    delivery_result = await db.execute(
        select(DeliveryTask).where(
            DeliveryTask.invoice_result_id == inv_result.id,
        )
    )
    deliveries = delivery_result.scalars().all()

    return {
        "invoice_number": inv_result.invoice_number,
        "invoice_code": inv_result.invoice_code,
        "invoice_date": inv_result.invoice_date.isoformat() if inv_result.invoice_date else None,
        "total_amount": str(inv_result.total_amount) if inv_result.total_amount else None,
        "total_tax": str(inv_result.total_tax) if inv_result.total_tax else None,
        "total_with_tax": str(inv_result.total_with_tax) if inv_result.total_with_tax else None,
        "buyer_name": inv_result.buyer_name,
        "seller_name": inv_result.seller_name,
        "file_status": inv_result.file_status,
        "file_key": inv_result.file_key,
        "verified": inv_result.verified,
        "deliveries": [
            {
                "id": d.id,
                "channel": d.channel,
                "receiver": d.receiver,
                "status": d.status,
                "sent_at": d.sent_at.isoformat() if d.sent_at else None,
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            }
            for d in deliveries
        ],
    }


@router.get("/{task_id}/audit-trail", summary="审计轨迹")
async def get_task_audit_trail(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取开票任务的完整审计轨迹。"""
    # 审计日志
    logs_result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == current_user.tenant_id,
            AuditLog.entity_id == task_id,
        )
        .order_by(AuditLog.created_at.desc())
    )
    logs = logs_result.scalars().all()

    # 对账工单
    recon_result = await db.execute(
        select(ReconciliationCase)
        .where(
            ReconciliationCase.tenant_id == current_user.tenant_id,
            ReconciliationCase.invoice_task_id == task_id,
        )
        .order_by(ReconciliationCase.created_at.desc())
    )
    recons = recon_result.scalars().all()

    # 异常工单
    exc_result = await db.execute(
        select(ExceptionCase)
        .where(
            ExceptionCase.tenant_id == current_user.tenant_id,
            ExceptionCase.invoice_task_id == task_id,
        )
        .order_by(ExceptionCase.created_at.desc())
    )
    exceptions = exc_result.scalars().all()

    return {
        "audit_logs": [
            {
                "id": log.id,
                "action": log.action,
                "user_id": log.user_id,
                "before": log.before_value,
                "after": log.after_value,
                "ip_address": log.ip_address,
                "trace_id": log.trace_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "reconciliation_cases": [
            {
                "id": r.id,
                "case_type": r.case_type,
                "description": r.description,
                "status": r.status,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            }
            for r in recons
        ],
        "exception_cases": [
            {
                "id": e.id,
                "exception_type": e.exception_type,
                "description": e.description,
                "status": e.status,
                "auto_fixable": e.auto_fixable,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in exceptions
        ],
    }
