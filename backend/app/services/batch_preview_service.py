"""批量操作影响预览服务。

在执行批量操作前，预览操作的影响范围和风险。
"""

import logging
import secrets
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import ChannelBinding
from app.models.enterprise import Enterprise
from app.models.invoice_task import (
    ExceptionCase,
    InvoiceResult,
    InvoiceTask,
    ReconciliationCase,
)
from app.models.product import ProductRule
from app.models.task import WorkItem

logger = logging.getLogger(__name__)


class BatchPreviewService:
    """批量操作影响预览。"""

    @staticmethod
    async def preview_batch_invoice(
        db: AsyncSession,
        tenant_id: str,
        task_ids: list[str],
    ) -> dict[str, Any]:
        """预览批量开票影响。

        分析指定任务列表中哪些可以执行开票、哪些不能及原因。

        Args:
            db: 数据库会话
            tenant_id: 租户ID
            task_ids: 任务ID列表

        Returns:
            预览结果 dict
        """
        if not task_ids:
            return BatchPreviewService._empty_result("invoice")

        result = await db.execute(
            select(InvoiceTask).where(
                InvoiceTask.tenant_id == tenant_id,
                InvoiceTask.id.in_(task_ids),
            )
        )
        tasks = result.scalars().all()

        executable: list[dict[str, Any]] = []
        non_executable: list[dict[str, Any]] = []
        high_risk: list[dict[str, Any]] = []
        unknown_result: list[dict[str, Any]] = []
        non_exec_reasons: dict[str, list[str]] = {}
        affected_enterprises: set[str] = set()

        executable_statuses = {"pending_submit", "validation_passed", "pending_validation"}

        for task in tasks:
            affected_enterprises.add(task.enterprise_id)
            detail: dict[str, Any] = {
                "task_id": task.id,
                "enterprise_id": task.enterprise_id,
                "status": task.status,
                "retry_count": task.retry_count,
            }

            if task.status in executable_statuses:
                executable.append(detail)
            elif task.status == "unknown":
                unknown_result.append(detail)
                non_executable.append(detail)
                BatchPreviewService._add_reason(non_exec_reasons, task.id, "结果未知，需先对账")
            elif task.status in ("submitting", "accepted", "confirming"):
                non_executable.append(detail)
                BatchPreviewService._add_reason(non_exec_reasons, task.id, "正在处理中")
            elif task.status == "success":
                non_executable.append(detail)
                BatchPreviewService._add_reason(non_exec_reasons, task.id, "已开票成功")
            elif task.status == "terminated":
                non_executable.append(detail)
                BatchPreviewService._add_reason(non_exec_reasons, task.id, "已终止")
            else:
                if task.retry_count >= task.max_retries:
                    high_risk.append(detail)
                    BatchPreviewService._add_reason(non_exec_reasons, task.id, "已达最大重试次数")
                else:
                    executable.append(detail)

        requires_approval = len(task_ids) > 50 or len(high_risk) > 0

        return {
            "operation_type": "invoice",
            "total_count": len(task_ids),
            "executable_count": len(executable),
            "non_executable_count": len(non_executable),
            "high_risk_count": len(high_risk),
            "unknown_result_count": len(unknown_result),
            "requires_approval": requires_approval,
            "affected_enterprises": list(affected_enterprises),
            "details": executable + non_executable,
            "non_executable_reasons": non_exec_reasons,
            "preview_token": BatchPreviewService._generate_preview_token(),
        }

    @staticmethod
    async def preview_batch_retry(
        db: AsyncSession,
        tenant_id: str,
        task_ids: list[str],
    ) -> dict[str, Any]:
        """预览批量重试影响。

        分析哪些任务可以重试、哪些已达最大重试次数。

        Args:
            db: 数据库会话
            tenant_id: 租户ID
            task_ids: 任务ID列表

        Returns:
            预览结果 dict
        """
        if not task_ids:
            return BatchPreviewService._empty_result("retry")

        result = await db.execute(
            select(InvoiceTask).where(
                InvoiceTask.tenant_id == tenant_id,
                InvoiceTask.id.in_(task_ids),
            )
        )
        tasks = result.scalars().all()

        executable: list[dict[str, Any]] = []
        non_executable: list[dict[str, Any]] = []
        high_risk: list[dict[str, Any]] = []
        non_exec_reasons: dict[str, list[str]] = {}
        affected_enterprises: set[str] = set()

        retryable_statuses = {"failed", "unknown"}

        for task in tasks:
            affected_enterprises.add(task.enterprise_id)
            detail: dict[str, Any] = {
                "task_id": task.id,
                "enterprise_id": task.enterprise_id,
                "status": task.status,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
            }

            if task.status not in retryable_statuses:
                non_executable.append(detail)
                BatchPreviewService._add_reason(non_exec_reasons, task.id, f"状态 '{task.status}' 不允许重试")
            elif task.retry_count >= task.max_retries:
                high_risk.append(detail)
                non_executable.append(detail)
                BatchPreviewService._add_reason(non_exec_reasons, task.id, "已达最大重试次数")
            else:
                executable.append(detail)

        return {
            "operation_type": "retry",
            "total_count": len(task_ids),
            "executable_count": len(executable),
            "non_executable_count": len(non_executable),
            "high_risk_count": len(high_risk),
            "unknown_result_count": sum(1 for t in tasks if t.status == "unknown"),
            "requires_approval": len(high_risk) > 0,
            "affected_enterprises": list(affected_enterprises),
            "details": executable + non_executable,
            "non_executable_reasons": non_exec_reasons,
            "preview_token": BatchPreviewService._generate_preview_token(),
        }

    @staticmethod
    async def preview_rule_change(
        db: AsyncSession,
        tenant_id: str,
        rule_id: str,
        new_values: dict[str, Any],
    ) -> dict[str, Any]:
        """预览规则修改影响范围。

        分析修改商品规则会影响哪些待处理任务。

        Args:
            db: 数据库会话
            tenant_id: 租户ID
            rule_id: 规则ID
            new_values: 新的规则值

        Returns:
            预览结果 dict
        """
        # 查找规则
        rule_result = await db.execute(
            select(ProductRule).where(
                ProductRule.tenant_id == tenant_id,
                ProductRule.id == rule_id,
            )
        )
        rule = rule_result.scalar_one_or_none()

        if rule is None:
            return {
                "operation_type": "rule_change",
                "total_count": 0,
                "executable_count": 0,
                "non_executable_count": 0,
                "high_risk_count": 0,
                "unknown_result_count": 0,
                "requires_approval": False,
                "affected_enterprises": [],
                "details": [],
                "non_executable_reasons": {"rule_id": ["规则不存在"]},
                "preview_token": None,
            }

        # 查找该企业下待处理任务
        task_result = await db.execute(
            select(InvoiceTask).where(
                InvoiceTask.tenant_id == tenant_id,
                InvoiceTask.enterprise_id == rule.enterprise_id,
                InvoiceTask.status.in_(["pending_validation", "validation_passed", "pending_submit"]),
            )
        )
        tasks = task_result.scalars().all()

        affected_enterprises = [rule.enterprise_id] if tasks else []
        details = [
            {
                "task_id": t.id,
                "enterprise_id": t.enterprise_id,
                "status": t.status,
            }
            for t in tasks
        ]

        # 判断是否高风险（修改税码或税率）
        high_risk = any(k in new_values for k in ("tax_code", "default_tax_rate"))

        return {
            "operation_type": "rule_change",
            "total_count": len(tasks),
            "executable_count": len(tasks),
            "non_executable_count": 0,
            "high_risk_count": len(tasks) if high_risk else 0,
            "unknown_result_count": 0,
            "requires_approval": high_risk and len(tasks) > 10,
            "affected_enterprises": affected_enterprises,
            "details": details,
            "non_executable_reasons": {},
            "rule_info": {
                "rule_id": rule.id,
                "original_name": rule.original_name,
                "standard_name": rule.standard_name,
                "current_tax_code": rule.tax_code,
                "current_tax_rate": str(rule.default_tax_rate) if rule.default_tax_rate else None,
            },
            "preview_token": BatchPreviewService._generate_preview_token(),
        }

    @staticmethod
    async def preview_enterprise_pause(
        db: AsyncSession,
        tenant_id: str,
        enterprise_id: str,
    ) -> dict[str, Any]:
        """预览暂停企业影响。

        检查执行中任务、结果未知任务、未关闭工作项等。

        Args:
            db: 数据库会话
            tenant_id: 租户ID
            enterprise_id: 企业ID

        Returns:
            预览结果 dict
        """
        # 查找执行中的任务
        active_result = await db.execute(
            select(InvoiceTask).where(
                InvoiceTask.tenant_id == tenant_id,
                InvoiceTask.enterprise_id == enterprise_id,
                InvoiceTask.status.in_([
                    "pending_submit", "queuing", "submitting",
                    "accepted", "confirming",
                ]),
            )
        )
        active_tasks = active_result.scalars().all()

        # 查找结果未知的任务
        unknown_result = await db.execute(
            select(InvoiceTask).where(
                InvoiceTask.tenant_id == tenant_id,
                InvoiceTask.enterprise_id == enterprise_id,
                InvoiceTask.status.in_(["unknown", "awaiting_reconciliation"]),
            )
        )
        unknown_tasks = unknown_result.scalars().all()

        # 查找未关闭工作项
        work_result = await db.execute(
            select(WorkItem).where(
                WorkItem.tenant_id == tenant_id,
                WorkItem.enterprise_id == enterprise_id,
                WorkItem.status.in_(["pending", "in_progress"]),
            )
        )
        open_work_items = work_result.scalars().all()

        # 查找未关闭异常工单
        exc_result = await db.execute(
            select(ExceptionCase).where(
                ExceptionCase.tenant_id == tenant_id,
                ExceptionCase.enterprise_id == enterprise_id,
                ExceptionCase.status.in_(["open", "processing"]),
            )
        )
        open_exceptions = exc_result.scalars().all()

        # 查找未关闭对账工单
        recon_result = await db.execute(
            select(ReconciliationCase).where(
                ReconciliationCase.tenant_id == tenant_id,
                ReconciliationCase.invoice_task_id.in_(
                    select(InvoiceTask.id).where(
                        InvoiceTask.tenant_id == tenant_id,
                        InvoiceTask.enterprise_id == enterprise_id,
                    )
                ),
                ReconciliationCase.status.in_(["open", "investigating"]),
            )
        )
        open_recons = recon_result.scalars().all()

        total_affected = len(active_tasks) + len(unknown_tasks)
        high_risk = len(active_tasks) > 0 or len(unknown_tasks) > 0

        details = [
            {
                "type": "active_task",
                "task_id": t.id,
                "status": t.status,
            }
            for t in active_tasks
        ] + [
            {
                "type": "unknown_task",
                "task_id": t.id,
                "status": t.status,
            }
            for t in unknown_tasks
        ]

        return {
            "operation_type": "enterprise_pause",
            "total_count": total_affected,
            "executable_count": 0,
            "non_executable_count": total_affected,
            "high_risk_count": total_affected,
            "unknown_result_count": len(unknown_tasks),
            "requires_approval": high_risk,
            "affected_enterprises": [enterprise_id],
            "details": details,
            "non_executable_reasons": {},
            "summary": {
                "active_tasks": len(active_tasks),
                "unknown_tasks": len(unknown_tasks),
                "open_work_items": len(open_work_items),
                "open_exceptions": len(open_exceptions),
                "open_reconciliations": len(open_recons),
            },
            "preview_token": BatchPreviewService._generate_preview_token(),
        }

    @staticmethod
    async def preview_channel_switch(
        db: AsyncSession,
        tenant_id: str,
        enterprise_id: str,
        new_provider: str,
    ) -> dict[str, Any]:
        """预览通道切换影响。

        分析切换通道会影响哪些进行中的任务。

        Args:
            db: 数据库会话
            tenant_id: 租户ID
            enterprise_id: 企业ID
            new_provider: 新通道提供商标识

        Returns:
            预览结果 dict
        """
        # 查找当前绑定
        binding_result = await db.execute(
            select(ChannelBinding).where(
                ChannelBinding.tenant_id == tenant_id,
                ChannelBinding.enterprise_id == enterprise_id,
                ChannelBinding.status == "authorized",
            )
        )
        current_binding = binding_result.scalar_one_or_none()

        current_provider = current_binding.provider_code if current_binding else None

        # 查找处理中的任务（这些会受影响）
        active_result = await db.execute(
            select(InvoiceTask).where(
                InvoiceTask.tenant_id == tenant_id,
                InvoiceTask.enterprise_id == enterprise_id,
                InvoiceTask.status.in_([
                    "queuing", "submitting", "accepted", "confirming", "unknown",
                ]),
            )
        )
        active_tasks = active_result.scalars().all()

        high_risk = len(active_tasks) > 0

        details = [
            {
                "task_id": t.id,
                "status": t.status,
                "affected": True,
            }
            for t in active_tasks
        ]

        return {
            "operation_type": "channel_switch",
            "total_count": len(active_tasks),
            "executable_count": 0,
            "non_executable_count": len(active_tasks),
            "high_risk_count": len(active_tasks),
            "unknown_result_count": sum(1 for t in active_tasks if t.status == "unknown"),
            "requires_approval": high_risk,
            "affected_enterprises": [enterprise_id],
            "details": details,
            "non_executable_reasons": {},
            "summary": {
                "current_provider": current_provider,
                "new_provider": new_provider,
                "active_tasks": len(active_tasks),
            },
            "preview_token": BatchPreviewService._generate_preview_token(),
        }

    @staticmethod
    def _empty_result(operation_type: str) -> dict[str, Any]:
        """返回空结果。"""
        return {
            "operation_type": operation_type,
            "total_count": 0,
            "executable_count": 0,
            "non_executable_count": 0,
            "high_risk_count": 0,
            "unknown_result_count": 0,
            "requires_approval": False,
            "affected_enterprises": [],
            "details": [],
            "non_executable_reasons": {},
            "preview_token": None,
        }

    @staticmethod
    def _add_reason(reasons: dict[str, list[str]], task_id: str, reason: str) -> None:
        """添加不可执行原因。"""
        if task_id not in reasons:
            reasons[task_id] = []
        reasons[task_id].append(reason)

    @staticmethod
    def _generate_preview_token() -> str:
        """生成预览确认令牌。"""
        return secrets.token_urlsafe(32)
