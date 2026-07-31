"""应用入口。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    logger.info("应用启动中... (环境: %s)", settings.ENVIRONMENT)

    # 初始化通道注册表
    from app.services.channels.registry import ChannelRegistry

    ChannelRegistry.initialize_defaults()
    logger.info("通道注册表已初始化: %s", [c["provider_code"] for c in ChannelRegistry.list_channels()])

    yield
    logger.info("应用关闭中...")
    # 此处可添加清理逻辑
    from app.db.session import async_engine

    await async_engine.dispose()
    logger.info("数据库连接已关闭")


app = FastAPI(
    title="Smart Invoice API",
    description="智能开票平台后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router)


@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查端点（无需认证）。"""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
    }


@app.get("/health/full", tags=["健康检查"])
async def health_check_full():
    """完整健康检查（检查依赖服务，无需认证）。"""
    from datetime import datetime, timezone
    from sqlalchemy import text
    from app.db.session import async_engine

    checks = {}

    # 1. 数据库
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}

    # 2. Redis
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "error", "message": str(e)}

    # 3. 企业微信/微信配置状态
    from app.services.wechat_service import wecom_service, wechat_service
    checks["wecom"] = {
        "status": "ok" if wecom_service.enabled else "not_configured",
    }
    checks["wechat"] = {
        "status": "ok" if wechat_service.enabled else "not_configured",
    }

    # 4. 百望云
    baiwang_key = getattr(settings, "BAIWANG_APP_KEY", "")
    checks["baiwang"] = {
        "status": "ok" if baiwang_key else "mock_mode",
        "mode": "live" if baiwang_key else "mock",
    }

    # 5. AI
    use_mock = getattr(settings, "AI_USE_MOCK", True)
    checks["ai"] = {
        "status": "ok",
        "mode": "mock" if use_mock else "live",
    }

    all_ok = all(
        v["status"] in ("ok", "not_configured", "mock_mode", "mock", "live")
        for v in checks.values()
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@app.get("/", tags=["根路径"])
async def root():
    """根路径重定向信息。"""
    return {
        "name": "Smart Invoice API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
