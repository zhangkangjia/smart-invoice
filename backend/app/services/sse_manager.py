"""Server-Sent Events 管理器。

管理客户端连接和事件推送，按租户分组，支持按企业过滤。
"""

import asyncio
import json
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SSEManager:
    """SSE 管理器。

    维护 tenant_id -> set[asyncio.Queue] 的连接映射，
    每个客户端连接对应一个 asyncio.Queue，用于接收推送的事件。
    """

    def __init__(self) -> None:
        # tenant_id -> set of asyncio.Queue
        self._connections: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)

    async def connect(self, tenant_id: str) -> asyncio.Queue[str]:
        """创建新连接，返回事件队列。

        Args:
            tenant_id: 租户ID

        Returns:
            用于接收事件的 asyncio.Queue
        """
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._connections[tenant_id].add(queue)
        logger.info("SSE 连接建立 tenant=%s, 当前连接数=%d", tenant_id, len(self._connections[tenant_id]))
        return queue

    def disconnect(self, tenant_id: str, queue: asyncio.Queue[str]) -> None:
        """断开连接。"""
        self._connections[tenant_id].discard(queue)
        logger.info("SSE 连接断开 tenant=%s, 剩余连接数=%d", tenant_id, len(self._connections.get(tenant_id, set())))

    async def broadcast(self, tenant_id: str, event_type: str, data: dict) -> None:
        """向租户内所有连接广播事件。

        Args:
            tenant_id: 租户ID
            event_type: 事件类型
            data: 事件数据
        """
        message = json.dumps({"event": event_type, "data": data}, ensure_ascii=False)
        queues = self._connections.get(tenant_id, set()).copy()
        for queue in queues:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("SSE 队列已满，丢弃消息 tenant=%s", tenant_id)

    async def send_progress(
        self,
        tenant_id: str,
        batch_id: str,
        progress: int,
        message: str = "",
    ) -> None:
        """发送批次进度更新。

        Args:
            tenant_id: 租户ID
            batch_id: 批次ID
            progress: 进度百分比 (0-100)
            message: 进度描述
        """
        await self.broadcast(
            tenant_id,
            "batch_progress",
            {
                "batch_id": batch_id,
                "progress": progress,
                "message": message,
            },
        )

    async def send_task_update(
        self,
        tenant_id: str,
        task_id: str,
        status: str,
        extra: dict | None = None,
    ) -> None:
        """发送任务状态更新。"""
        data: dict = {"task_id": task_id, "status": status}
        if extra:
            data.update(extra)
        await self.broadcast(tenant_id, "task_update", data)

    async def send_notification(
        self,
        tenant_id: str,
        title: str,
        content: str,
        level: str = "info",
    ) -> None:
        """发送通知事件。"""
        await self.broadcast(
            tenant_id,
            "notification",
            {"title": title, "content": content, "level": level},
        )

    def get_connection_count(self, tenant_id: str | None = None) -> int:
        """获取连接数。"""
        if tenant_id:
            return len(self._connections.get(tenant_id, set()))
        return sum(len(qs) for qs in self._connections.values())


# 全局单例
sse_manager = SSEManager()
