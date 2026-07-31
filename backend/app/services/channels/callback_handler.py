"""通道回调处理器。

处理开票通道的异步回调通知，包括签名验证、去重、状态更新等。
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import ChannelSubmission
from app.models.invoice_task import InvoiceResult, InvoiceTask, ReconciliationCase
from app.services.channels.registry import ChannelRegistry
from app.services.sse_manager import sse_manager

logger = logging.getLogger(__name__)


class ChannelCallbackHandler:
    """处理开票通道的异步回调。"""

    @staticmethod
    async def handle_callback(
        db: AsyncSession,
        provider_code: str,
        callback_data: dict[str, Any],
        signature: str | None = None,
        secret: str | None = None,
    ) -> dict[str, Any]:
        """处理通道回调。

        流程：
        1. 验证签名
        2. 去重检查（callback_id）
        3. 查找对应的 ChannelSubmission
        4. 根据回调内容更新任务状态
        5. 保存发票结果
        6. 触发交付流程
        7. 返回确认响应

        Args:
            db: 数据库会话
            provider_code: 通道提供商标识
            callback_data: 回调数据
            signature: 回调签名
            secret: 用于验证签名的密钥

        Returns:
            确认响应 dict
        """
        # 1. 验证签名
        if signature and secret:
            if not ChannelCallbackHandler._verify_signature(callback_data, signature, secret):
                logger.warning("回调签名验证失败 provider=%s", provider_code)
                return {"code": "SIGN_ERROR", "message": "签名验证失败"}

        # 2. 去重检查
        callback_id = callback_data.get("callback_id") or callback_data.get("msg_id")
        if callback_id:
            if await ChannelCallbackHandler._is_duplicate_callback(db, callback_id):
                logger.info("重复回调已忽略 callback_id=%s", callback_id)
                return {"code": "DUPLICATE", "message": "重复回调"}

        # 3. 查找 ChannelSubmission
        channel_business_no = (
            callback_data.get("channel_business_no")
            or callback_data.get("fpqqlsh")
            or callback_data.get("business_no")
        )
        if not channel_business_no:
            logger.warning("回调缺少 channel_business_no")
            return {"code": "MISSING_BUSINESS_NO", "message": "缺少业务编号"}

        result = await db.execute(
            select(ChannelSubmission).where(
                ChannelSubmission.channel_business_no == channel_business_no,
            )
        )
        submission = result.scalar_one_or_none()

        if submission is None:
            logger.warning("未找到对应的提交记录 no=%s", channel_business_no)
            return {"code": "NOT_FOUND", "message": "未找到对应的提交记录"}

        # 4. 更新任务状态
        await ChannelCallbackHandler._update_task_from_callback(
            db, submission, callback_data
        )

        await db.commit()

        # 5. 推送SSE通知
        task_result = await db.execute(
            select(InvoiceTask).where(InvoiceTask.id == submission.invoice_task_id)
        )
        task = task_result.scalar_one_or_none()
        if task:
            await sse_manager.send_task_update(
                tenant_id=task.tenant_id,
                task_id=task.id,
                status=task.status,
                extra={"channel_business_no": channel_business_no},
            )

        return {"code": "SUCCESS", "message": "处理成功"}

    @staticmethod
    def _verify_signature(data: dict[str, Any], signature: str, secret: str) -> bool:
        """验证回调签名。

        将回调数据按key排序拼接后做 HMAC-SHA256，与传入签名比对。

        Args:
            data: 回调数据
            signature: 待验证的签名
            secret: 密钥

        Returns:
            是否验证通过
        """
        try:
            sorted_items = sorted(data.items())
            sign_str = "&".join(f"{k}={v}" for k, v in sorted_items if k not in ("sign", "signature"))
            expected = hmac.new(
                secret.encode("utf-8"),
                sign_str.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as exc:
            logger.error("签名验证异常: %s", str(exc))
            return False

    @staticmethod
    async def _is_duplicate_callback(db: AsyncSession, callback_id: str) -> bool:
        """检查是否为重复回调。

        通过查找是否有 ChannelRequestLog 记录该 callback_id 来判断。
        简化实现：查询 response_summary 中包含该 callback_id 的日志。
        """
        result = await db.execute(
            select(ChannelSubmission).where(
                ChannelSubmission.response_summary["callback_id"].as_string() == callback_id
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def _update_task_from_callback(
        db: AsyncSession,
        submission: ChannelSubmission,
        callback_data: dict[str, Any],
    ) -> None:
        """根据回调数据更新任务状态。

        Args:
            db: 数据库会话
            submission: 通道提交记录
            callback_data: 回调数据
        """
        # 更新 submission 状态
        callback_status = str(callback_data.get("status", "")).lower()
        submission.response_summary = {
            **(submission.response_summary or {}),
            "callback": callback_data,
            "callback_received_at": datetime.now(timezone.utc).isoformat(),
        }

        # 查找关联的 InvoiceTask
        task_result = await db.execute(
            select(InvoiceTask).where(InvoiceTask.id == submission.invoice_task_id)
        )
        task = task_result.scalar_one_or_none()
        if task is None:
            logger.warning("提交记录关联的任务不存在 task_id=%s", submission.invoice_task_id)
            return

        if callback_status in ("success", "00", "0", "valid"):
            # 开票成功
            submission.status = "success"
            submission.confirmed_at = datetime.now(timezone.utc)
            task.status = "success"
            task.completed_at = datetime.now(timezone.utc)

            # 创建或更新 InvoiceResult
            await ChannelCallbackHandler._save_invoice_result(
                db, task, submission, callback_data
            )

        elif callback_status in ("failed", "02", "2", "invalid"):
            # 开票失败
            submission.status = "failed"
            submission.confirmed_at = datetime.now(timezone.utc)
            task.status = "failed"
            task.last_error = callback_data.get("error_message") or callback_data.get("reason") or "通道回调: 开票失败"
            task.completed_at = datetime.now(timezone.utc)

        else:
            # 处理中或其他状态
            submission.status = "confirming"
            task.status = "confirming"

    @staticmethod
    async def _save_invoice_result(
        db: AsyncSession,
        task: InvoiceTask,
        submission: ChannelSubmission,
        callback_data: dict[str, Any],
    ) -> None:
        """保存发票结果。

        Args:
            db: 数据库会话
            task: 开票任务
            submission: 通道提交记录
            callback_data: 回调数据
        """
        # 查找是否已有结果记录
        result = await db.execute(
            select(InvoiceResult).where(
                InvoiceResult.invoice_task_id == task.id,
            )
        )
        inv_result = result.scalar_one_or_none()

        invoice_number = callback_data.get("invoice_number") or callback_data.get("fphm")
        invoice_code = callback_data.get("invoice_code") or callback_data.get("fpdm")
        file_key = callback_data.get("file_key") or callback_data.get("pdf_url")

        if inv_result is None:
            inv_result = InvoiceResult(
                id=uuid.uuid4().hex,
                tenant_id=task.tenant_id,
                invoice_task_id=task.id,
                invoice_number=invoice_number,
                invoice_code=invoice_code,
                file_status="available" if file_key else "pending",
                file_key=file_key,
                verified=False,
            )
            db.add(inv_result)
        else:
            if invoice_number:
                inv_result.invoice_number = invoice_number
            if invoice_code:
                inv_result.invoice_code = invoice_code
            if file_key:
                inv_result.file_key = file_key
                inv_result.file_status = "available"

        await db.flush()
