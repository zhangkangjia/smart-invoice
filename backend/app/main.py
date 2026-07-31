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
    """健康检查端点。"""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
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
