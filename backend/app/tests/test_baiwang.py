"""百望云沙箱环境测试脚本。

用法：
    docker exec -it si-backend python -m app.tests.test_baiwang

测试项：
1. 鉴权（密码登录获取 token）
2. 开票（蓝票开具）
3. 查询开票结果
4. 快捷冲红
5. 红字确认单查询
"""

import asyncio
import logging
import sys

from app.services.channels.baiwang_channel import BaiwangChannel, BaiwangConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# 沙箱环境配置（来自 沙箱环境(2).txt）
SANDBOX_CONFIG = BaiwangConfig(
    app_key="1002948",
    app_secret="223998c6-5b76-4724-b5c9-666ff4215b45",
    user_salt="521c0eea19f04367ad20a3be12c9b4bc",
    username="admin_3sylog6ryv8cs",
    password="Aa2345678@",
    tax_no="338888888888SMB",
    invoice_terminal_code="202312120001",
    api_base_url="https://sandbox-openapi.baiwang.com/router/rest",
)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
NC = "\033[0m"


def log_pass(msg: str):
    print(f"{GREEN}  [PASS]{NC} {msg}")


def log_fail(msg: str, error: str = ""):
    print(f"{RED}  [FAIL]{NC} {msg}")
    if error:
        print(f"         {error}")


def log_info(msg: str):
    print(f"{CYAN}  [INFO]{NC} {msg}")


def section(title: str):
    print(f"\n{CYAN}━━━ {title} ━━━{NC}")


async def test_auth(channel: BaiwangChannel) -> str:
    """测试1: 鉴权"""
    section("1. 鉴权（密码登录）")
    try:
        token = await channel._get_access_token()
        if token:
            log_pass(f"Token 获取成功: {token[:30]}...")
            return token
        else:
            log_fail("Token 为空")
            return ""
    except Exception as e:
        log_fail("鉴权失败", str(e))
        return ""


async def test_issue_invoice(channel: BaiwangChannel) -> str:
    """测试2: 开票（蓝票）"""
    section("2. 开票（数电普票蓝票）")

    invoice_request = {
        "seller_tax_no": SANDBOX_CONFIG.tax_no,
        "seller_name": "沙箱测试企业",
        "seller_address": "测试地址",
        "seller_phone": "13800138000",
        "seller_bank_name": "测试银行",
        "seller_bank_account": "1234567890",
        "buyer_name": "个人",
        "buyer_tax_no": "",
        "external_order_no": f"TEST{int(__import__('time').time()*1000)}",
        "invoice_type": "1",  # 蓝票
        "invoice_type_code": "02",  # 数电普票
        "is_tax_inclusive": False,
        "drawer": "测试开票员",
        "items": [
            {
                "product_name": "测试商品",
                "tax_code": "1010101010100000000",
                "quantity": "1",
                "unit_price": "100",
                "tax_rate": "0.03",
                "amount": "97.09",
                "tax_amount": "2.91",
                "total_with_tax": "100",
            }
        ],
        "remark": "沙箱测试开票",
    }

    try:
        result = await channel.issue_invoice(invoice_request)
        if result.success:
            log_pass(f"开票成功！流水号: {result.channel_business_no}")
            return result.channel_business_no or ""
        else:
            log_fail(f"开票失败: {result.error_message}")
            return ""
    except Exception as e:
        log_fail("开票异常", str(e))
        return ""


async def test_query(channel: BaiwangChannel, serial_no: str) -> None:
    """测试3: 查询开票结果"""
    section("3. 查询开票结果")
    if not serial_no:
        log_fail("跳过（无流水号）")
        return

    try:
        result = await channel.query_result(serial_no)
        if result.found:
            log_pass(
                f"查询成功！状态: {result.status}, "
                f"发票号: {result.invoice_number}"
            )
        else:
            log_info(f"未查到结果（可能还在处理中）: {result.status}")
    except Exception as e:
        log_fail("查询异常", str(e))


async def test_health(channel: BaiwangChannel) -> None:
    """测试4: 健康检查"""
    section("4. 通道健康检查")
    try:
        ok = await channel.check_health()
        if ok:
            log_pass("百望云通道健康")
        else:
            log_fail("百望云通道不健康")
    except Exception as e:
        log_fail("健康检查异常", str(e))


async def test_red_query(channel: BaiwangChannel) -> None:
    """测试5: 红字确认单查询"""
    section("5. 红字确认单查询")
    try:
        result = await channel.query_red_confirm(page_num=1, page_size=5)
        log_pass(f"查询成功，返回数据: {str(result)[:200]}")
    except Exception as e:
        log_fail("红字确认单查询异常", str(e))


async def main():
    print(f"\n{CYAN}╔══════════════════════════════════════════════════════╗")
    print(f"║   百望云沙箱环境测试                                 ║")
    print(f"║   沙箱地址: sandbox-openapi.baiwang.com              ║")
    print(f"║   AppKey: 1002948                                   ║")
    print(f"║   销方税号: 338888888888SMB                          ║")
    print(f"╚══════════════════════════════════════════════════════╝{NC}\n")

    channel = BaiwangChannel(SANDBOX_CONFIG)

    try:
        # 1. 鉴权
        token = await test_auth(channel)
        if not token:
            print(f"\n{RED}鉴权失败，后续测试跳过{NC}")
            await channel.close()
            sys.exit(1)

        # 2. 健康检查
        await test_health(channel)

        # 3. 开票
        serial_no = await test_issue_invoice(channel)

        # 4. 等待2秒后查询
        if serial_no:
            log_info("等待2秒后查询...")
            await asyncio.sleep(2)
            await test_query(channel, serial_no)

        # 5. 红字确认单查询
        await test_red_query(channel)

    finally:
        await channel.close()

    print(f"\n{CYAN}━━━ 测试完成 ━━━{NC}")


if __name__ == "__main__":
    asyncio.run(main())
