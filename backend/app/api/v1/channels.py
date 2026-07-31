"""通道管理API路由。"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.channel import ChannelBinding
from app.models.enterprise import Enterprise
from app.models.user import User
from app.services.channels.callback_handler import ChannelCallbackHandler
from app.services.channels.reconciliation import ReconciliationService
from app.services.channels.registry import ChannelRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["通道管理"])


@router.get("", summary="通道列表")
async def list_channels(
    current_user: User = Depends(get_current_active_user),
):
    """列出所有注册的通道和能力。"""
    channels = ChannelRegistry.list_channels()
    return {"channels": channels}


@router.get("/{provider_code}/capabilities", summary="通道能力")
async def get_channel_capabilities(
    provider_code: str,
    current_user: User = Depends(get_current_active_user),
):
    """获取指定通道的能力矩阵。"""
    cap = ChannelRegistry.get_capabilities(provider_code)
    if cap is None:
        raise HTTPException(status_code=404, detail=f"通道 '{provider_code}' 不存在")
    return {
        "provider_code": provider_code,
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
    }


@router.get("/{provider_code}/health", summary="通道健康检查")
async def check_channel_health(
    provider_code: str,
    current_user: User = Depends(get_current_active_user),
):
    """检查通道健康状态。"""
    channel = ChannelRegistry.get(provider_code)
    if channel is None:
        raise HTTPException(status_code=404, detail=f"通道 '{provider_code}' 不存在")

    try:
        healthy = await channel.check_health()
    except Exception as exc:
        logger.error("通道健康检查异常: %s", str(exc))
        healthy = False

    return {
        "provider_code": provider_code,
        "healthy": healthy,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/callback/{provider_code}", summary="通道回调")
async def channel_callback(
    provider_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """接收通道异步回调（无需认证，通过签名验证）。"""
    # 获取请求体
    body = await request.body()
    try:
        callback_data = json.loads(body)
    except json.JSONDecodeError:
        try:
            callback_data = json.loads(body.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="无效的请求体")

    # 获取签名（从header或query）
    signature = request.headers.get("X-Signature") or request.query_params.get("sign")

    # 获取密钥（从绑定记录中获取，这里简化处理）
    # 实际应从 callback_data 中提取企业标识后查找对应密钥
    secret = request.headers.get("X-Callback-Secret")

    try:
        result = await ChannelCallbackHandler.handle_callback(
            db=db,
            provider_code=provider_code,
            callback_data=callback_data,
            signature=signature,
            secret=secret,
        )
    except Exception as exc:
        logger.error("回调处理异常: %s", str(exc))
        raise HTTPException(status_code=500, detail="回调处理失败")

    return result


@router.get("/enterprises/{enterprise_id}/binding", summary="企业通道绑定")
async def get_channel_binding(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取企业通道绑定信息。"""
    result = await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.tenant_id == current_user.tenant_id,
            ChannelBinding.enterprise_id == enterprise_id,
        ).order_by(ChannelBinding.created_at.desc())
    )
    bindings = result.scalars().all()

    return {
        "bindings": [
            {
                "id": b.id,
                "enterprise_id": b.enterprise_id,
                "provider_code": b.provider_code,
                "status": b.status,
                "authorized_at": b.authorized_at.isoformat() if b.authorized_at else None,
                "expires_at": b.expires_at.isoformat() if b.expires_at else None,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in bindings
        ]
    }


@router.post(
    "/enterprises/{enterprise_id}/binding",
    status_code=status.HTTP_201_CREATED,
    summary="绑定通道",
)
async def bind_channel(
    enterprise_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """绑定开票通道（加密存储凭据）。

    body:
        provider_code: 通道标识
        credentials: 凭据信息（api_base_url, app_key, app_secret 等）
    """
    provider_code = body.get("provider_code")
    if not provider_code:
        raise HTTPException(status_code=400, detail="缺少 provider_code")

    credentials = body.get("credentials", {})

    # 验证企业存在
    ent_result = await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id,
            Enterprise.tenant_id == current_user.tenant_id,
        )
    )
    if ent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="企业不存在")

    # 验证通道存在
    if ChannelRegistry.get(provider_code) is None:
        raise HTTPException(status_code=400, detail=f"通道 '{provider_code}' 不存在")

    # 加密凭据（简化实现：JSON序列化后用hash_password方式存储密钥部分）
    # 实际生产应使用 AES 等对称加密
    import uuid as uuid_mod

    credentials_json = json.dumps(credentials, ensure_ascii=False)
    # 对 app_secret 做哈希保护（不可逆，仅用于验证；实际凭据需要可逆加密）
    # 这里使用简单方式：整体JSON存储（生产环境需替换为加密存储）
    from app.core.config import settings

    encrypted = _simple_encrypt(credentials_json, settings.SECRET_KEY)

    binding = ChannelBinding(
        id=uuid_mod.uuid4().hex,
        tenant_id=current_user.tenant_id,
        enterprise_id=enterprise_id,
        provider_code=provider_code,
        credentials_encrypted=encrypted,
        status="authorized",
        authorized_at=datetime.now(timezone.utc),
    )
    db.add(binding)
    await db.commit()

    return {
        "id": binding.id,
        "enterprise_id": enterprise_id,
        "provider_code": provider_code,
        "status": binding.status,
        "authorized_at": binding.authorized_at.isoformat() if binding.authorized_at else None,
    }


@router.delete("/enterprises/{enterprise_id}/binding", summary="解绑通道")
async def unbind_channel(
    enterprise_id: str,
    binding_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """解绑通道。"""
    stmt = select(ChannelBinding).where(
        ChannelBinding.tenant_id == current_user.tenant_id,
        ChannelBinding.enterprise_id == enterprise_id,
        ChannelBinding.status == "authorized",
    )
    if binding_id:
        stmt = stmt.where(ChannelBinding.id == binding_id)

    result = await db.execute(stmt)
    bindings = result.scalars().all()

    if not bindings:
        raise HTTPException(status_code=404, detail="未找到有效的通道绑定")

    for b in bindings:
        b.status = "revoked"

    await db.commit()
    return {"message": "通道已解绑", "count": len(bindings)}


@router.get("/enterprises/{enterprise_id}/quota", summary="企业开票额度")
async def get_enterprise_quota(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查询企业开票额度。"""
    # 查找企业绑定的通道
    result = await db.execute(
        select(ChannelBinding).where(
            ChannelBinding.tenant_id == current_user.tenant_id,
            ChannelBinding.enterprise_id == enterprise_id,
            ChannelBinding.status == "authorized",
        ).order_by(ChannelBinding.created_at.desc())
    )
    binding = result.scalar_one_or_none()

    if binding is None:
        raise HTTPException(status_code=404, detail="企业未绑定开票通道")

    # 查找企业税号
    ent_result = await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id,
            Enterprise.tenant_id == current_user.tenant_id,
        )
    )
    enterprise = ent_result.scalar_one_or_none()
    if enterprise is None:
        raise HTTPException(status_code=404, detail="企业不存在")

    if not enterprise.tax_no:
        raise HTTPException(status_code=400, detail="企业未设置税号")

    # 获取通道实例并查询额度
    try:
        # 对 mock 通道直接返回模拟数据
        if binding.provider_code == "mock":
            channel = ChannelRegistry.get_channel_for_enterprise(binding.provider_code)
            return {
                "enterprise_id": enterprise_id,
                "tax_no": enterprise.tax_no,
                "provider_code": binding.provider_code,
                "total_quota": 99999999.99,
                "used_quota": 0,
                "remaining_quota": 99999999.99,
                "note": "模拟通道额度",
            }

        # real 通道需要解密凭据
        from app.core.config import settings

        credentials_json = _simple_decrypt(binding.credentials_encrypted or "", settings.SECRET_KEY)
        credentials = json.loads(credentials_json) if credentials_json else {}

        channel = ChannelRegistry.get_channel_for_enterprise(
            binding.provider_code, config=credentials
        )

        if not hasattr(channel, "query_quota"):
            raise HTTPException(status_code=400, detail="该通道不支持额度查询")

        quota = await channel.query_quota(enterprise.tax_no)
        return {
            "enterprise_id": enterprise_id,
            "tax_no": enterprise.tax_no,
            "provider_code": binding.provider_code,
            **quota,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("查询额度异常: %s", str(exc))
        raise HTTPException(status_code=500, detail=f"查询额度失败: {exc}")


@router.post("/reconciliation/run", summary="手动触发对账")
async def run_reconciliation(
    tenant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """手动触发对账。"""
    target_tenant = tenant_id or current_user.tenant_id
    result = await ReconciliationService.run_reconciliation(db, tenant_id=target_tenant)
    return result


# --------------------------------------------------------------------------- #
# 简单加解密工具（生产环境应替换为 AES 对称加密）
# --------------------------------------------------------------------------- #

def _simple_encrypt(plaintext: str, key: str) -> str:
    """简单加密（XOR + Base64，仅用于开发环境）。

    生产环境必须替换为 AES-256-GCM 等标准加密算法。
    """
    import base64

    key_bytes = key.encode("utf-8")[:32]
    key_bytes = key_bytes.ljust(32, b"\0")
    data = plaintext.encode("utf-8")
    encrypted = bytes(d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data))
    return base64.b64encode(encrypted).decode("ascii")


def _simple_decrypt(ciphertext: str, key: str) -> str:
    """简单解密。"""
    import base64

    key_bytes = key.encode("utf-8")[:32]
    key_bytes = key_bytes.ljust(32, b"\0")
    encrypted = base64.b64decode(ciphertext)
    decrypted = bytes(d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(encrypted))
    return decrypted.decode("utf-8")
