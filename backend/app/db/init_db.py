"""数据库初始化工具。"""

import asyncio
import logging

from sqlalchemy import select

from app.core.security import hash_password
from app.core.config import settings
from app.db.base import Base
from app.db.session import AsyncSessionLocal, async_engine
from app.models.user import Role, User, UserRole

logger = logging.getLogger(__name__)

# 默认角色定义
DEFAULT_ROLES = [
    {"name": "超级管理员", "code": "super_admin", "description": "平台最高权限", "permissions": ["*"]},
    {"name": "机构管理员", "code": "agency_admin", "description": "管理机构及下属组织", "permissions": ["org.*", "enterprise.*", "user.*"]},
    {"name": "分公司管理员", "code": "branch_admin", "description": "管理分公司", "permissions": ["branch.*", "enterprise.read", "task.*"]},
    {"name": "财税主管", "code": "tax_supervisor", "description": "分配任务、审批", "permissions": ["task.*", "enterprise.read", "invoice.*"]},
    {"name": "主办会计", "code": "accountant", "description": "企业资料确认", "permissions": ["enterprise.read", "business.*", "customer.*"]},
    {"name": "开票员", "code": "invoice_clerk", "description": "执行开票", "permissions": ["invoice.*", "task.read", "business.read"]},
    {"name": "客服人员", "code": "customer_service", "description": "客户沟通", "permissions": ["customer.*", "business.read", "delivery.*"]},
    {"name": "运营人员", "code": "operator", "description": "批量配置", "permissions": ["enterprise.*", "customer.*", "product.*"]},
    {"name": "审计人员", "code": "auditor", "description": "只读审计", "permissions": ["audit.*", "*.read"]},
    {"name": "临时替班", "code": "substitute", "description": "临时替班", "permissions": ["task.read", "invoice.read"]},
]

# 默认租户
DEFAULT_TENANT_ID = "default"
DEFAULT_TENANT_NAME = "默认租户"


async def init_database() -> None:
    """创建所有表并初始化默认角色和超级管理员。"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 兼容旧库：给 users 表补 wecom_userid 字段（create_all 不会改已有表）
        from sqlalchemy import text
        try:
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS wecom_userid VARCHAR(100)"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS wecom_bound_at TIMESTAMPTZ"
            ))
            # 建索引（如果不存在）
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_users_wecom_userid ON users (wecom_userid)"
            ))
        except Exception as e:
            logger.warning("补充 wecom_userid 字段失败（可忽略）: %s", e)
    logger.info("数据库表已创建")

    async with AsyncSessionLocal() as db:
        # 创建默认租户
        from app.models.tenant import Tenant

        existing_tenant = await db.execute(
            select(Tenant).where(Tenant.id == DEFAULT_TENANT_ID)
        )
        if existing_tenant.scalar_one_or_none() is None:
            tenant = Tenant(
                id=DEFAULT_TENANT_ID,
                name=DEFAULT_TENANT_NAME,
                code="default",
                status="active",
            )
            db.add(tenant)
            await db.flush()
            logger.info("默认租户已创建")

        # 创建默认角色
        for role_def in DEFAULT_ROLES:
            existing = await db.execute(
                select(Role).where(
                    Role.tenant_id == DEFAULT_TENANT_ID,
                    Role.code == role_def["code"],
                )
            )
            if existing.scalar_one_or_none() is None:
                role = Role(
                    tenant_id=DEFAULT_TENANT_ID,
                    name=role_def["name"],
                    code=role_def["code"],
                    description=role_def["description"],
                    permissions=role_def["permissions"],
                )
                db.add(role)
        await db.flush()
        logger.info("默认角色已创建")

        # 创建超级管理员
        existing_admin = await db.execute(
            select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
        )
        if existing_admin.scalar_one_or_none() is None:
            admin = User(
                tenant_id=DEFAULT_TENANT_ID,
                username=settings.DEFAULT_ADMIN_USERNAME,
                email=settings.DEFAULT_ADMIN_EMAIL,
                phone=None,
                hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                full_name="超级管理员",
                status="active",
                is_super_admin=True,
            )
            db.add(admin)
            await db.flush()

            # 关联超级管理员角色
            super_role = await db.execute(
                select(Role).where(
                    Role.tenant_id == DEFAULT_TENANT_ID,
                    Role.code == "super_admin",
                )
            )
            role = super_role.scalar_one_or_none()
            if role is not None:
                db.add(UserRole(user_id=admin.id, role_id=role.id))

            logger.info(
                "超级管理员已创建: %s / %s",
                settings.DEFAULT_ADMIN_USERNAME,
                settings.DEFAULT_ADMIN_PASSWORD,
            )

        await db.commit()
    logger.info("数据库初始化完成")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_database())
