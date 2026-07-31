"""创建超级管理员脚本。

用法::

    python -m app.scripts.create_admin --username admin --password mypass --email admin@example.com

或直接运行::

    python -m app.scripts.create_admin
"""

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.init_db import DEFAULT_ROLES, DEFAULT_TENANT_ID
from app.db.session import AsyncSessionLocal, async_engine
from app.db.base import Base
from app.models.tenant import Tenant
from app.models.user import Role, User, UserRole

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def create_admin(
    username: str,
    password: str,
    email: str | None = None,
    full_name: str = "超级管理员",
) -> None:
    """创建超级管理员账户。"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # 确保默认租户存在
        existing_tenant = await db.execute(
            select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID)
        )
        if existing_tenant.scalar_one_or_none() is None:
            db.add(Tenant(
                id=DEFAULT_TENANT_ID,
                name="默认租户",
                code="default",
                status="active",
            ))
            await db.flush()
            logger.info("默认租户已创建")

        # 确保角色存在
        for role_def in DEFAULT_ROLES:
            existing = await db.execute(
                select(Role).where(
                    Role.tenant_id == DEFAULT_TENANT_ID,
                    Role.code == role_def["code"],
                )
            )
            if existing.scalar_one_or_none() is None:
                db.add(Role(
                    tenant_id=DEFAULT_TENANT_ID,
                    name=role_def["name"],
                    code=role_def["code"],
                    description=role_def["description"],
                    permissions=role_def["permissions"],
                ))
        await db.flush()
        logger.info("角色已就绪")

        # 检查用户是否已存在
        existing_user = await db.execute(select(User).where(User.username == username))
        if existing_user.scalar_one_or_none() is not None:
            logger.warning("用户 '%s' 已存在，跳过创建", username)
            return

        # 创建用户
        import uuid as uuid_lib

        admin = User(
            id=uuid_lib.uuid4().hex,
            tenant_id=DEFAULT_TENANT_ID,
            username=username,
            email=email,
            phone=None,
            hashed_password=hash_password(password),
            full_name=full_name,
            status="active",
            is_super_admin=True,
        )
        db.add(admin)
        await db.flush()

        # 关联超级管理员角色
        role_result = await db.execute(
            select(Role).where(
                Role.tenant_id == DEFAULT_TENANT_ID,
                Role.code == "super_admin",
            )
        )
        role = role_result.scalar_one_or_none()
        if role:
            db.add(UserRole(user_id=admin.id, role_id=role.id))

        await db.commit()
        logger.info("超级管理员创建成功: %s", username)


def main():
    parser = argparse.ArgumentParser(description="创建超级管理员")
    parser.add_argument("--username", default=settings.DEFAULT_ADMIN_USERNAME, help="用户名")
    parser.add_argument("--password", default=settings.DEFAULT_ADMIN_PASSWORD, help="密码")
    parser.add_argument("--email", default=settings.DEFAULT_ADMIN_EMAIL, help="邮箱")
    parser.add_argument("--full-name", default="超级管理员", help="姓名")
    args = parser.parse_args()

    asyncio.run(create_admin(
        username=args.username,
        password=args.password,
        email=args.email,
        full_name=args.full_name,
    ))


if __name__ == "__main__":
    main()
