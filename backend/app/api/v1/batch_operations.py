"""批量操作API路由。"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.invoice_task import InvoiceTask
from app.models.user import User
from app.schemas.batch import (
    BatchExecuteRequest,
    BatchExecuteResponse,
    BatchPreviewRequest,
    BatchPreviewResponse,
)
from app.services.batch_preview_service import BatchPreviewService
from app.services.sse_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch-operations", tags=["批量操作"])


@router.post("/preview", summary="批量操作影响预览")
async def preview_batch_operation(
    body: BatchPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """预览批量操作的影响范围。

    支持的操作类型：
    - invoice: 批量开票
    - retry: 批量重试
    - rule_change: 规则修改
    - enterprise_pause: 暂停企业
    - channel_switch: 通道切换
    """
    op_type = body.operation_type
    tenant_id = current_user.tenant_id

    if op_type == "invoice":
        result = await BatchPreviewService.preview_batch_invoice(db, tenant_id, body.target_ids)
    elif op_type == "retry":
        result = await BatchPreviewService.preview_batch_retry(db, tenant_id, body.target_ids)
    elif op_type == "rule_change":
        rule_id = body.params.get("rule_id") or (body.target_ids[0] if body.target_ids else "")
        if not rule_id:
            raise HTTPException(status_code=400, detail="rule_change 操作需要提供 rule_id")
        result = await BatchPreviewService.preview_rule_change(
            db, tenant_id, rule_id, body.params.get("new_values", {})
        )
    elif op_type == "enterprise_pause":
        enterprise_id = body.params.get("enterprise_id") or (body.target_ids[0] if body.target_ids else "")
        if not enterprise_id:
            raise HTTPException(status_code=400, detail="enterprise_pause 操作需要提供 enterprise_id")
        result = await BatchPreviewService.preview_enterprise_pause(db, tenant_id, enterprise_id)
    elif op_type == "channel_switch":
        enterprise_id = body.params.get("enterprise_id") or (body.target_ids[0] if body.target_ids else "")
        new_provider = body.params.get("new_provider", "")
        if not enterprise_id or not new_provider:
            raise HTTPException(status_code=400, detail="channel_switch 操作需要提供 enterprise_id 和 new_provider")
        result = await BatchPreviewService.preview_channel_switch(
            db, tenant_id, enterprise_id, new_provider
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的操作类型: {op_type}",
        )

    return result


@router.post("/execute", summary="执行批量操作")
async def execute_batch_operation(
    body: BatchExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """执行批量操作（需先预览确认）。

    需要提供预览时返回的 preview_token。
    """
    if not body.preview_token:
        raise HTTPException(status_code=400, detail="缺少预览确认令牌 preview_token")

    tenant_id = current_user.tenant_id
    batch_no = f"BATCH-{uuid.uuid4().hex[:12]}"
    op_type = body.operation_type

    if op_type == "invoice":
        return await _execute_batch_invoice(db, tenant_id, body.target_ids, batch_no)
    elif op_type == "retry":
        return await _execute_batch_retry(db, tenant_id, body.target_ids, batch_no)
    else:
        # 其他操作类型目前仅返回确认信息
        return BatchExecuteResponse(
            operation_type=op_type,
            batch_no=batch_no,
            total_count=len(body.target_ids),
            success_count=0,
            failure_count=0,
            skipped_count=len(body.target_ids),
            details=[{"message": f"操作类型 {op_type} 需要手动确认执行"}],
        )


async def _execute_batch_invoice(
    db: AsyncSession,
    tenant_id: str,
    task_ids: list[str],
    batch_no: str,
) -> BatchExecuteResponse:
    """执行批量开票。"""
    result = await db.execute(
        select(InvoiceTask).where(
            InvoiceTask.tenant_id == tenant_id,
            InvoiceTask.id.in_(task_ids),
        )
    )
    tasks = result.scalars().all()

    success_count = 0
    failure_count = 0
    skipped_count = 0
    details: list[dict] = []

    executable_statuses = {"pending_submit", "validation_passed", "pending_validation"}

    for task in tasks:
        if task.status in executable_statuses:
            task.status = "queuing"
            success_count += 1
            details.append({"task_id": task.id, "action": "queued", "status": "queuing"})
        else:
            skipped_count += 1
            details.append({"task_id": task.id, "action": "skipped", "reason": f"状态 {task.status} 不可执行"})

    await db.commit()

    # 推送SSE通知
    await sse_manager.send_notification(
        tenant_id=tenant_id,
        title="批量开票已提交",
        content=f"批次 {batch_no}: 成功 {success_count}, 跳过 {skipped_count}",
    )

    return BatchExecuteResponse(
        operation_type="invoice",
        batch_no=batch_no,
        total_count=len(task_ids),
        success_count=success_count,
        failure_count=failure_count,
        skipped_count=skipped_count,
        details=details,
    )


async def _execute_batch_retry(
    db: AsyncSession,
    tenant_id: str,
    task_ids: list[str],
    batch_no: str,
) -> BatchExecuteResponse:
    """执行批量重试。"""
    result = await db.execute(
        select(InvoiceTask).where(
            InvoiceTask.tenant_id == tenant_id,
            InvoiceTask.id.in_(task_ids),
        )
    )
    tasks = result.scalars().all()

    success_count = 0
    failure_count = 0
    skipped_count = 0
    details: list[dict] = []

    retryable_statuses = {"failed", "unknown"}

    for task in tasks:
        if task.status not in retryable_statuses:
            skipped_count += 1
            details.append({"task_id": task.id, "action": "skipped", "reason": f"状态 {task.status} 不可重试"})
        elif task.retry_count >= task.max_retries:
            failure_count += 1
            details.append({"task_id": task.id, "action": "failed", "reason": "已达最大重试次数"})
        else:
            task.retry_count += 1
            task.status = "pending_submit"
            task.last_error = None
            success_count += 1
            details.append({"task_id": task.id, "action": "retried", "status": "pending_submit"})

    await db.commit()

    await sse_manager.send_notification(
        tenant_id=tenant_id,
        title="批量重试已提交",
        content=f"批次 {batch_no}: 成功 {success_count}, 失败 {failure_count}, 跳过 {skipped_count}",
    )

    return BatchExecuteResponse(
        operation_type="retry",
        batch_no=batch_no,
        total_count=len(task_ids),
        success_count=success_count,
        failure_count=failure_count,
        skipped_count=skipped_count,
        details=details,
    )
