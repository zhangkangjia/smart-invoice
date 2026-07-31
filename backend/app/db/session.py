"""数据库会话管理。"""

from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# --- 异步引擎 (FastAPI 运行时使用) ---
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- 同步引擎 (Alembic / 脚本使用) - 延迟初始化 ---
_sync_engine = None
SyncSessionLocal: Optional[sessionmaker] = None


def get_sync_engine():
    """延迟获取同步引擎，避免导入时连接数据库。"""
    global _sync_engine, SyncSessionLocal
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.DATABASE_SYNC_URL,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        SyncSessionLocal = sessionmaker(bind=_sync_engine, autocommit=False, autoflush=False)
    return _sync_engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取异步数据库会话。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
