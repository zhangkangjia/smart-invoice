"""系统配置路由。

让管理员在页面上配置：
- 企业微信（CorpID/AgentID/Secret）
- 微信服务号（AppID/AppSecret/Token）
- 百望云通道（AppKey/AppSecret/AccountID）
- AI 识别（Mock开关/模型/Key）
- 通用设置（前端URL/时区）

配置项存到数据库，修改后立即生效（部分配置需重启服务）。
首次启动时从环境变量初始化默认值。
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system-config", tags=["系统配置"])


# --------------------------------------------------------------------------- #
# 模型
# --------------------------------------------------------------------------- #

class ConfigItem(BaseModel):
    """单个配置项。"""
    key: str
    value: str
    category: str  # wecom / wechat / baiwang / ai / general
    label: str
    description: str = ""
    is_secret: bool = False  # 敏感字段（显示为 ***）


class ConfigGroup(BaseModel):
    """配置分组。"""
    category: str
    title: str
    icon: str
    description: str
    items: list[ConfigItem]


# 配置项定义（key 与 settings 环境变量同名）
CONFIG_DEFINITIONS: list[ConfigGroup] = [
    ConfigGroup(
        category="wecom",
        title="企业微信",
        icon="ChatDotRound",
        description="将开票平台作为企业微信自建应用嵌入，代账人员免登录使用",
        items=[
            ConfigItem(key="WECOM_CORP_ID", value="", category="wecom",
                       label="企业ID (CorpID)",
                       description="企业微信管理后台 → 我的企业 → 企业信息 → 企业ID"),
            ConfigItem(key="WECOM_AGENT_ID", value="", category="wecom",
                       label="应用ID (AgentID)",
                       description="自建应用详情页 → AgentId"),
            ConfigItem(key="WECOM_SECRET", value="", category="wecom",
                       label="应用Secret",
                       description="自建应用详情页 → Secret",
                       is_secret=True),
        ],
    ),
    ConfigGroup(
        category="wechat",
        title="微信服务号",
        icon="Message",
        description="客户通过微信公众号提交开票申请，接收模板消息通知",
        items=[
            ConfigItem(key="WECHAT_APP_ID", value="", category="wechat",
                       label="AppID",
                       description="公众号后台 → 基本配置 → 开发者ID"),
            ConfigItem(key="WECHAT_APP_SECRET", value="", category="wechat",
                       label="AppSecret",
                       description="公众号后台 → 基本配置 → 开发者密码",
                       is_secret=True),
            ConfigItem(key="WECHAT_TOKEN", value="", category="wechat",
                       label="Token",
                       description="公众号后台 → 基本配置 → 服务器配置 → Token"),
            ConfigItem(key="WECHAT_AES_KEY", value="", category="wechat",
                       label="EncodingAESKey",
                       description="公众号后台 → 基本配置 → 服务器配置 → EncodingAESKey"),
        ],
    ),
    ConfigGroup(
        category="baiwang",
        title="百望云开票通道",
        icon="Connection",
        description="接入百望云数电发票真实开票通道，未配置则使用模拟开票",
        items=[
            ConfigItem(key="BAIWANG_APP_KEY", value="", category="baiwang",
                       label="AppKey",
                       description="百望云开放平台 → 应用管理 → AppKey"),
            ConfigItem(key="BAIWANG_APP_SECRET", value="", category="baiwang",
                       label="AppSecret",
                       description="百望云开放平台 → 应用管理 → AppSecret",
                       is_secret=True),
            ConfigItem(key="BAIWANG_ACCOUNT_ID", value="", category="baiwang",
                       label="账户ID (AccountID)",
                       description="百望云账户ID"),
            ConfigItem(key="BAIWANG_API_BASE_URL", value="https://open.baiwang.com",
                       category="baiwang", label="API Base URL",
                       description="默认 https://open.baiwang.com"),
        ],
    ),
    ConfigGroup(
        category="ai",
        title="AI 识别",
        icon="MagicStick",
        description="配置文字/图片识别的AI模型，未配置则使用 Mock 模式",
        items=[
            ConfigItem(key="AI_USE_MOCK", value="true", category="ai",
                       label="使用 Mock 模式",
                       description="true=不调用真实AI，false=调用真实AI"),
            ConfigItem(key="AI_TEXT_API_URL", value="", category="ai",
                       label="文字识别 API URL",
                       description="如 https://api.openai.com/v1/chat/completions"),
            ConfigItem(key="AI_TEXT_API_KEY", value="", category="ai",
                       label="文字识别 API Key",
                       is_secret=True),
            ConfigItem(key="AI_TEXT_MODEL", value="gpt-4o-mini", category="ai",
                       label="文字识别模型"),
            ConfigItem(key="AI_MULTIMODAL_API_URL", value="", category="ai",
                       label="多模态识别 API URL"),
            ConfigItem(key="AI_MULTIMODAL_API_KEY", value="", category="ai",
                       label="多模态识别 API Key",
                       is_secret=True),
            ConfigItem(key="AI_MULTIMODAL_MODEL", value="gpt-4o", category="ai",
                       label="多模态识别模型"),
        ],
    ),
    ConfigGroup(
        category="general",
        title="通用设置",
        icon="Setting",
        description="基础环境配置",
        items=[
            ConfigItem(key="FRONTEND_BASE_URL", value="http://localhost:3000",
                       category="general", label="前端访问地址",
                       description="用于生成回调链接和通知中的跳转URL"),
            ConfigItem(key="ENVIRONMENT", value="development", category="general",
                       label="运行环境",
                       description="development / production"),
            ConfigItem(key="SECRET_KEY", value="", category="general",
                       label="JWT 密钥",
                       description="生产环境务必改为随机长字符串",
                       is_secret=True),
        ],
    ),
]


# --------------------------------------------------------------------------- #
# 数据库模型
# --------------------------------------------------------------------------- #

class SystemConfig:
    """简化的配置存储（直接用 dict 表）。"""
    pass


# 使用现有的 settings 读取默认值
def _init_defaults() -> None:
    """从 settings 读取环境变量作为默认值。"""
    from app.core.config import settings
    for group in CONFIG_DEFINITIONS:
        for item in group.items:
            # 优先用预定义值，否则从 settings 读取
            if not item.value:
                attr_value = getattr(settings, item.key, "")
                if attr_value is not None:
                    item.value = str(attr_value)


_init_defaults()


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

@router.get("", summary="获取所有配置项")
async def get_all_config(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有系统配置（按分组返回）。

    敏感字段（is_secret=true）返回 *** 而非真实值。
    """
    # 从数据库读取覆盖值
    overrides = await _load_overrides(db)

    groups = []
    for group in CONFIG_DEFINITIONS:
        items = []
        for item in group.items:
            value = overrides.get(item.key, item.value)
            # 敏感字段不返回真实值
            if item.is_secret and value:
                display_value = "******"
                has_value = True
            else:
                display_value = value
                has_value = bool(value)
            items.append({
                "key": item.key,
                "label": item.label,
                "description": item.description,
                "value": display_value,
                "is_secret": item.is_secret,
                "has_value": has_value,
            })
        groups.append({
            "category": group.category,
            "title": group.title,
            "icon": group.icon,
            "description": group.description,
            "items": items,
        })
    return {"groups": groups}


@router.put("", summary="批量更新配置")
async def update_config(
    data: dict[str, str],
    current_user: User = Depends(require_roles("super_admin", "agency_admin")),
    db: AsyncSession = Depends(get_db),
):
    """批量更新配置项。

    传入: {"WECOM_CORP_ID": "xxx", "WECOM_SECRET": "yyy", ...}
    值为 "******" 的字段会被忽略（保留原值）。
    """
    from sqlalchemy import text
    updated = []
    for key, value in data.items():
        # 跳过掩码值（用户没改）
        if value == "******":
            continue
        # 查找 key 对应的定义
        item_def = None
        for group in CONFIG_DEFINITIONS:
            for item in group.items:
                if item.key == key:
                    item_def = item
                    break
        if not item_def:
            continue

        # 写入或更新数据库
        existing = await db.execute(
            text("SELECT key FROM system_config WHERE key = :key"),
            {"key": key},
        )
        if existing.first():
            await db.execute(
                text("UPDATE system_config SET value = :value, updated_at = NOW() WHERE key = :key"),
                {"key": key, "value": value},
            )
        else:
            await db.execute(
                text("""INSERT INTO system_config (key, value, category, updated_at)
                        VALUES (:key, :value, :category, NOW())"""),
                {"key": key, "value": value, "category": item_def.category},
            )
        updated.append(key)

    await log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="update_system_config",
        entity_type="system_config",
        entity_id="config",
        after={"updated_keys": updated},
    )
    await db.commit()

    return {
        "updated": len(updated),
        "keys": updated,
        "message": f"已更新 {len(updated)} 项配置。部分配置需重启服务后生效。",
    }


@router.post("/test/{category}", summary="测试配置连通性")
async def test_config(
    category: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """测试某个配置分组的连通性。

    - wecom: 获取企业微信 access_token
    - baiwang: 百望云鉴权
    - ai: 调用 Mock 识别
    """
    overrides = await _load_overrides(db)

    if category == "wecom":
        from app.services.wechat_service import WeComService
        svc = WeComService()
        svc.corp_id = overrides.get("WECOM_CORP_ID", "")
        svc.secret = overrides.get("WECOM_SECRET", "")
        svc.agent_id = overrides.get("WECOM_AGENT_ID", "")
        if not svc.enabled:
            return {"ok": False, "error": "企业微信未配置"}
        try:
            token = await svc.get_access_token()
            return {"ok": True, "message": "企业微信连接成功", "token_prefix": token[:20] + "..."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if category == "baiwang":
        from app.services.channels.baiwang_channel import BaiwangChannel, BaiwangConfig
        config = BaiwangConfig(
            app_key=overrides.get("BAIWANG_APP_KEY", ""),
            app_secret=overrides.get("BAIWANG_APP_SECRET", ""),
            account_id=overrides.get("BAIWANG_ACCOUNT_ID", ""),
            api_base_url=overrides.get("BAIWANG_API_BASE_URL", "https://open.baiwang.com"),
        )
        if not config.app_key:
            return {"ok": False, "error": "百望云未配置 AppKey"}
        channel = BaiwangChannel(config=config)
        try:
            token = await channel._get_access_token()
            return {"ok": True, "message": "百望云鉴权成功", "token_prefix": token[:20] + "..."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if category == "ai":
        from app.core.config import settings
        use_mock = overrides.get("AI_USE_MOCK", str(settings.AI_USE_MOCK)).lower() == "true"
        if use_mock:
            return {"ok": True, "message": "AI Mock 模式（不调用真实AI）"}
        api_url = overrides.get("AI_TEXT_API_URL", "")
        if not api_url:
            return {"ok": False, "error": "AI API URL 未配置"}
        return {"ok": True, "message": "AI 配置已保存（请实际上传图片测试识别效果）"}

    return {"ok": False, "error": f"不支持的测试类别: {category}"}


@router.post("/apply", summary="应用配置（重启服务）")
async def apply_config(
    current_user: User = Depends(require_roles("super_admin")),
):
    """提示用户需要重启服务让配置生效。

    本接口不实际重启（避免卡死），仅返回提示。
    """
    return {
        "need_restart": True,
        "message": "部分配置（如 SECRET_KEY、数据库连接）需要重启服务后生效。请执行: ./deploy.sh restart",
    }


# --------------------------------------------------------------------------- #
# 辅助函数
# --------------------------------------------------------------------------- #

async def _load_overrides(db: AsyncSession) -> dict[str, str]:
    """从数据库读取配置覆盖值。

    如果表不存在或为空，返回空 dict（使用环境变量默认值）。
    """
    from sqlalchemy import text
    overrides: dict[str, str] = {}
    try:
        result = await db.execute(text("SELECT key, value FROM system_config"))
        for row in result:
            overrides[row[0]] = row[1]
    except Exception as e:
        # 表不存在时静默忽略（init_db 会创建）
        logger.debug("读取 system_config 失败: %s", e)
    return overrides


async def _ensure_table(db: AsyncSession) -> None:
    """确保 system_config 表存在。"""
    from sqlalchemy import text
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS system_config (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT,
            category VARCHAR(50),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    await db.commit()
