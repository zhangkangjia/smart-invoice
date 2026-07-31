"""定时对账服务。

定期检查：
- 结果未知的任务
- 回调缺失的任务
- 金额不一致的任务
- 版式文件缺失的任务
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import ChannelSubmission
from app.models.invoice_task import (
    InvoiceResult,
    InvoiceTask,
    ReconciliationCase,
)
from app.services.channels.registry import ChannelRegistry

logger = logging.getLogger(__name__)


class ReconciliationService:
    """对账服务。

    定期检查：
    - 结果未知的任务
    - 回调缺失的任务
    - 金额不一致的任务
    - 版式文件缺失的任务
    """

    @staticmethod
    async def run_reconciliation(
        db: AsyncSession,
        tenant_id: str | None = None,
    ) -> dict:
        """执行一轮对账。

        Args:
            db: 数据库会话
            tenant_id: 租户ID（可选，不传则对全部租户执行）

        Returns:
            对账结果摘要
        """
        summary = {
            "unknown_tasks_checked": 0,
            "missing_callbacks_checked": 0,
            "amount_mismatch_checked": 0,
            "missing_files_checked": 0,
            "cases_created": 0,
            "cases_resolved": 0,
            "errors": [],
        }

        try:
            summary["unknown_tasks_checked"] = await ReconciliationService.check_unknown_tasks(
                db, max_age_hours=1, tenant_id=tenant_id
            )
        except Exception as exc:
            logger.error("检查未知任务失败: %s", str(exc))
            summary["errors"].append(f"unknown_tasks: {exc}")

        try:
            summary["missing_callbacks_checked"] = await ReconciliationService.check_missing_callbacks(
                db, tenant_id=tenant_id
            )
        except Exception as exc:
            logger.error("检查回调缺失失败: %s", str(exc))
            summary["errors"].append(f"missing_callbacks: {exc}")

        try:
            summary["amount_mismatch_checked"] = await ReconciliationService.check_amount_mismatch(
                db, tenant_id=tenant_id
            )
        except Exception as exc:
            logger.error("检查金额不一致失败: %s", str(exc))
            summary["errors"].append(f"amount_mismatch: {exc}")

        try:
            summary["missing_files_checked"] = await ReconciliationService.check_missing_files(
                db, tenant_id=tenant_id
            )
        except Exception as exc:
            logger.error("检查文件缺失失败: %s", str(exc))
            summary["errors"].append(f"missing_files: {exc}")

        await db.commit()
        logger.info("对账完成 summary=%s", summary)
        return summary

    @staticmethod
    async def check_unknown_tasks(
        db: AsyncSession,
        max_age_hours: int = 1,
        tenant_id: str | None = None,
    ) -> int:
        """检查结果未知任务。

        查找状态为 unknown 或 awaiting_reconciliation 的任务，
        超过指定时间后向通道查询实际结果。

        Args:
            db: 数据库会话
            max_age_hours: 最小年龄（小时），只检查超过此时间的任务
            tenant_id: 租户ID

        Returns:
            检查的任务数
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        stmt = select(InvoiceTask).where(
            InvoiceTask.status.in_(["unknown", "awaiting_reconciliation"]),
            InvoiceTask.updated_at < cutoff,
        )
        if tenant_id:
            stmt = stmt.where(InvoiceTask.tenant_id == tenant_id)

        result = await db.execute(stmt.limit(100))
        tasks = result.scalars().all()

        checked = 0
        for task in tasks:
            checked += 1
            try:
                await ReconciliationService._reconcile_single_task(db, task)
            except Exception as exc:
                logger.error("对账任务异常 task_id=%s err=%s", task.id, str(exc))
                # 创建对账工单
                await ReconciliationService._create_or_update_case(
                    db, task, "unknown_result", f"对账查询失败: {exc}"
                )

        return checked

    @staticmethod
    async def _reconcile_single_task(db: AsyncSession, task: InvoiceTask) -> None:
        """对单个任务进行对账查询。"""
        # 查找通道提交记录
        sub_result = await db.execute(
            select(ChannelSubmission).where(
                ChannelSubmission.invoice_task_id == task.id,
            ).order_by(ChannelSubmission.created_at.desc())
        )
        submission = sub_result.scalar_one_or_none()
        if submission is None or not submission.channel_business_no:
            await ReconciliationService._create_or_update_case(
                db, task, "unknown_result", "无通道业务编号，无法查询"
            )
            return

        # 获取通道实例并查询
        try:
            channel = ChannelRegistry.get_channel_for_enterprise(
                submission.provider_code,
            )
        except ValueError:
            # real 通道需要配置，这里用 mock 查询
            channel = ChannelRegistry.get("mock")

        if channel is None:
            await ReconciliationService._create_or_update_case(
                db, task, "unknown_result", f"通道 {submission.provider_code} 不可用"
            )
            return

        query_result = await channel.query_result(submission.channel_business_no)

        if query_result.status == "success":
            # 通道确认成功
            task.status = "success"
            task.completed_at = datetime.now(timezone.utc)
            submission.status = "success"
            submission.confirmed_at = datetime.now(timezone.utc)

            # 保存发票结果
            await ReconciliationService._save_result_from_query(db, task, query_result)

            # 关闭相关对账工单
            await ReconciliationService._close_cases(db, task.id)

        elif query_result.status == "failed":
            task.status = "failed"
            task.completed_at = datetime.now(timezone.utc)
            submission.status = "failed"
            submission.confirmed_at = datetime.now(timezone.utc)
            await ReconciliationService._close_cases(db, task.id)

        else:
            # 仍然未知，更新时间触发下次检查
            task.updated_at = datetime.now(timezone.utc)

    @staticmethod
    async def check_missing_callbacks(
        db: AsyncSession,
        tenant_id: str | None = None,
    ) -> int:
        """检查回调缺失的任务。

        查找已提交但超过一定时间未收到回调的任务。

        Args:
            db: 数据库会话
            tenant_id: 租户ID

        Returns:
            检查的任务数
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

        stmt = (
            select(InvoiceTask)
            .join(ChannelSubmission, ChannelSubmission.invoice_task_id == InvoiceTask.id)
            .where(
                InvoiceTask.status.in_(["submitting", "accepted", "confirming"]),
                ChannelSubmission.status.in_(["submitting", "accepted"]),
                ChannelSubmission.submitted_at < cutoff,
            )
        )
        if tenant_id:
            stmt = stmt.where(InvoiceTask.tenant_id == tenant_id)

        result = await db.execute(stmt.limit(100))
        tasks = result.scalars().all()

        count = 0
        for task in tasks:
            count += 1
            await ReconciliationService._create_or_update_case(
                db, task, "callback_missing", "已提交超过30分钟未收到回调"
            )

        return count

    @staticmethod
    async def check_amount_mismatch(
        db: AsyncSession,
        tenant_id: str | None = None,
    ) -> int:
        """检查金额不一致。

        对比 InvoiceResult 与 InvoiceRequest 的金额是否一致。

        Args:
            db: 数据库会话
            tenant_id: 租户ID

        Returns:
            检查的任务数
        """
        from app.models.invoice import InvoiceRequest

        stmt = (
            select(InvoiceResult, InvoiceRequest, InvoiceTask)
            .join(InvoiceTask, InvoiceTask.id == InvoiceResult.invoice_task_id)
            .join(InvoiceRequest, InvoiceRequest.id == InvoiceTask.invoice_request_id)
            .where(InvoiceResult.total_with_tax.isnot(None))
        )
        if tenant_id:
            stmt = stmt.where(InvoiceResult.tenant_id == tenant_id)

        result = await db.execute(stmt.limit(200))
        rows = result.all()

        count = 0
        for inv_result, inv_request, task in rows:
            if inv_request.total_with_tax is None:
                continue
            if inv_result.total_with_tax is None:
                continue

            diff = abs(Decimal(str(inv_result.total_with_tax)) - Decimal(str(inv_request.total_with_tax)))
            if diff > Decimal("0.01"):
                count += 1
                await ReconciliationService._create_or_update_case(
                    db,
                    task,
                    "amount_mismatch",
                    f"金额不一致: 请求={inv_request.total_with_tax}, 结果={inv_result.total_with_tax}, 差异={diff}",
                )

        return count

    @staticmethod
    async def check_missing_files(
        db: AsyncSession,
        tenant_id: str | None = None,
    ) -> int:
        """检查版式文件缺失。

        查找状态为 success 但 file_status 为 pending 或 missing 的发票结果。

        Args:
            db: 数据库会话
            tenant_id: 租户ID

        Returns:
            检查的任务数
        """
        stmt = (
            select(InvoiceResult, InvoiceTask)
            .join(InvoiceTask, InvoiceTask.id == InvoiceResult.invoice_task_id)
            .where(
                InvoiceTask.status == "success",
                InvoiceResult.file_status.in_(["pending", "missing"]),
            )
        )
        if tenant_id:
            stmt = stmt.where(InvoiceResult.tenant_id == tenant_id)

        result = await db.execute(stmt.limit(100))
        rows = result.all()

        count = 0
        for inv_result, task in rows:
            count += 1
            # 标记文件为 missing（如果长时间 pending）
            if inv_result.file_status == "pending":
                inv_result.file_status = "missing"
            await ReconciliationService._create_or_update_case(
                db, task, "file_missing", "版式文件缺失"
            )

        return count

    @staticmethod
    async def _create_or_update_case(
        db: AsyncSession,
        task: InvoiceTask,
        case_type: str,
        description: str,
    ) -> None:
        """创建或更新对账工单。"""
        # 查找是否已有同类型未关闭的工单
        result = await db.execute(
            select(ReconciliationCase).where(
                ReconciliationCase.invoice_task_id == task.id,
                ReconciliationCase.case_type == case_type,
                ReconciliationCase.status.in_(["open", "investigating"]),
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.description = description
            existing.detected_at = datetime.now(timezone.utc)
        else:
            case = ReconciliationCase(
                id=uuid.uuid4().hex,
                tenant_id=task.tenant_id,
                invoice_task_id=task.id,
                case_type=case_type,
                description=description,
                detected_at=datetime.now(timezone.utc),
                status="open",
            )
            db.add(case)

    @staticmethod
    async def _close_cases(db: AsyncSession, task_id: str) -> None:
        """关闭任务关联的未决对账工单。"""
        result = await db.execute(
            select(ReconciliationCase).where(
                ReconciliationCase.invoice_task_id == task_id,
                ReconciliationCase.status.in_(["open", "investigating"]),
            )
        )
        cases = result.scalars().all()
        for case in cases:
            case.status = "resolved"
            case.resolved_at = datetime.now(timezone.utc)
            case.resolution = "对账确认后自动关闭"

    @staticmethod
    async def _save_result_from_query(
        db: AsyncSession,
        task: InvoiceTask,
        query_result,
    ) -> None:
        """从查询结果保存 InvoiceResult。"""
        result = await db.execute(
            select(InvoiceResult).where(InvoiceResult.invoice_task_id == task.id)
        )
        inv_result = result.scalar_one_or_none()

        if inv_result is None:
            inv_result = InvoiceResult(
                id=uuid.uuid4().hex,
                tenant_id=task.tenant_id,
                invoice_task_id=task.id,
                invoice_number=query_result.invoice_number,
                invoice_code=query_result.invoice_code,
                invoice_date=query_result.invoice_date,
                file_status="available" if query_result.file_key else "pending",
                file_key=query_result.file_key,
                verified=False,
            )
            db.add(inv_result)
        else:
            if query_result.invoice_number:
                inv_result.invoice_number = query_result.invoice_number
            if query_result.invoice_code:
                inv_result.invoice_code = query_result.invoice_code
            if query_result.invoice_date:
                inv_result.invoice_date = query_result.invoice_date
            if query_result.file_key:
                inv_result.file_key = query_result.file_key
                inv_result.file_status = "available"
