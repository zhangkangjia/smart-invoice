"""开票通道注册表和工厂。

管理所有可用的通道实例，按 provider_code 索引。
支持动态注册和获取通道。
"""

import logging
from typing import Any

from app.services.channels.base import ChannelCapability, InvoiceChannel
from app.services.channels.mock_channel import MockInvoiceChannel
from app.services.channels.real_channel import RealInvoiceChannel
from app.services.channels.baiwang_channel import BaiwangChannel, BaiwangConfig

logger = logging.getLogger(__name__)


class ChannelRegistry:
    """开票通道注册表。

    管理所有可用的通道实例，按provider_code索引。
    支持动态注册和获取通道。
    """

    _channels: dict[str, InvoiceChannel] = {}
    _mock_singleton: MockInvoiceChannel | None = None

    @classmethod
    def register(cls, channel: InvoiceChannel) -> None:
        """注册通道。

        Args:
            channel: 通道实例
        """
        cls._channels[channel.provider_code] = channel
        logger.info("通道已注册: %s (%s)", channel.provider_code, channel.provider_name)

    @classmethod
    def get(cls, provider_code: str) -> InvoiceChannel | None:
        """获取通道实例。

        Args:
            provider_code: 通道提供商标识

        Returns:
            通道实例，不存在返回 None
        """
        return cls._channels.get(provider_code)

    @classmethod
    def list_channels(cls) -> list[dict[str, Any]]:
        """列出所有已注册通道及其能力。

        Returns:
            通道信息列表
        """
        result: list[dict[str, Any]] = []
        for code, channel in cls._channels.items():
            cap = channel.get_capabilities()
            result.append({
                "provider_code": code,
                "provider_name": channel.provider_name,
                "capabilities": {
                    "supports_electronic_special": cap.supports_electronic_special,
                    "supports_electronic_normal": cap.supports_electronic_normal,
                    "supports_special": cap.supports_special,
                    "supports_normal": cap.supports_normal,
                    "supports_red_invoice": cap.supports_red_invoice,
                    "supports_batch": cap.supports_batch,
                    "supports_split": cap.supports_split,
                    "max_items_per_invoice": cap.max_items_per_invoice,
                    "max_amount": cap.max_amount,
                    "requires_tax_no": cap.requires_tax_no,
                },
            })
        return result

    @classmethod
    def get_capabilities(cls, provider_code: str) -> ChannelCapability | None:
        """获取指定通道的能力矩阵。

        Args:
            provider_code: 通道提供商标识

        Returns:
            ChannelCapability 或 None
        """
        channel = cls._channels.get(provider_code)
        if channel is None:
            return None
        return channel.get_capabilities()

    @classmethod
    def get_channel_for_enterprise(
        cls,
        provider_code: str,
        config: dict[str, Any] | None = None,
    ) -> InvoiceChannel:
        """获取企业绑定的通道实例。

        对于 real 通道，使用 config 初始化新实例；
        对于 mock 通道，返回单例。

        Args:
            provider_code: 通道提供商标识
            config: 通道配置（用于 real 通道）

        Returns:
            通道实例

        Raises:
            ValueError: 通道未注册
        """
        if provider_code == "mock":
            if cls._mock_singleton is None:
                cls._mock_singleton = MockInvoiceChannel()
            return cls._mock_singleton

        if provider_code == "real":
            if not config:
                raise ValueError("real 通道需要提供 config 配置")
            return RealInvoiceChannel(config=config)

        if provider_code == "baiwang":
            if not config:
                raise ValueError("百望云通道需要提供 config（含 app_key, app_secret）")
            return BaiwangChannel(config=BaiwangConfig(**config))

        channel = cls._channels.get(provider_code)
        if channel is None:
            raise ValueError(f"通道 '{provider_code}' 未注册")
        return channel

    @classmethod
    def initialize_defaults(cls) -> None:
        """初始化默认通道（mock + real框架）。"""
        # mock 通道注册单例
        if "mock" not in cls._channels:
            mock = MockInvoiceChannel()
            cls.register(mock)
            cls._mock_singleton = mock

        # real 通道注册一个无配置的占位实例（仅用于列表展示和能力查询）
        if "real" not in cls._channels:
            real_placeholder = RealInvoiceChannel(config={})
            cls.register(real_placeholder)

        # 百望云通道注册占位实例（真实调用需要企业级 config）
        if "baiwang" not in cls._channels:
            bw_placeholder = BaiwangChannel(config=BaiwangConfig(
                app_key="", app_secret="", api_base_url="https://open.baiwang.com"
            ))
            cls.register(bw_placeholder)

        logger.info("默认通道初始化完成: %s", list(cls._channels.keys()))

    @classmethod
    def clear(cls) -> None:
        """清空所有注册的通道（主要用于测试）。"""
        cls._channels.clear()
        cls._mock_singleton = None


# 模块加载时注册默认通道
ChannelRegistry.initialize_defaults()
