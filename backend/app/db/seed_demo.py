"""示例数据填充脚本。

启动时自动调用，添加几家企业便于快速测试开票。
不会覆盖已有数据，重复执行幂等。
"""

import asyncio
import logging

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.enterprise import Enterprise
from app.models.user import User

logger = logging.getLogger(__name__)

DEMO_ENTERPRISES = [
    {
        "name": "杭州两心同网络科技有限公司",
        "tax_no": "91330106MA28T1234X",
        "phone": "13800138000",
        "address": "浙江省杭州市西湖区文三路478号",
        "bank_name": "中国工商银行杭州西湖支行",
        "bank_account": "1202020809000123456",
    },
    {
        "name": "上海阿里巴巴网络技术有限公司",
        "tax_no": "9131011576425899XD",
        "phone": "13900139000",
        "address": "上海市浦东新区张江高科技园区",
        "bank_name": "中国建设银行上海浦东支行",
        "bank_account": "6217000010023456789",
    },
    {
        "name": "北京百度网讯科技有限公司",
        "tax_no": "91110000710930008F",
        "phone": "13700137000",
        "address": "北京市海淀区上地十街10号百度大厦",
        "bank_name": "招商银行北京海淀支行",
        "bank_account": "110908456710101",
    },
]


async def seed_demo_data() -> None:
    """添加示例企业（已存在则跳过）。"""
    async with AsyncSessionLocal() as db:
        # 找一个管理员用户用作企业的 owner
        result = await db.execute(
            select(User).where(User.is_super_admin == True).limit(1)  # noqa: E712
        )
        owner = result.scalar_one_or_none()
        if owner is None:
            logger.warning("未找到超级管理员，跳过示例企业填充")
            return

        for ent_data in DEMO_ENTERPRISES:
            existing = await db.execute(
                select(Enterprise).where(Enterprise.tax_no == ent_data["tax_no"])
            )
            if existing.scalar_one_or_none() is not None:
                continue

            enterprise = Enterprise(
                tenant_id=owner.tenant_id,
                status="active",
                **ent_data,
            )
            db.add(enterprise)
            logger.info("添加示例企业: %s", ent_data["name"])

        await db.commit()
        logger.info("示例数据填充完成")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_data())
