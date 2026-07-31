"""用户管理路由。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user, require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.user import Role, User, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.audit_service import log_action

router = APIRouter(prefix="/users", tags=["用户管理"])


async def _get_user_roles(db: AsyncSession, user_id: str) -> list[str]:
    result = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return [row[0] for row in result.all()]


@router.get("", response_model=PaginatedResponse[UserResponse], summary="用户列表")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询用户列表。"""
    stmt = select(User).where(User.tenant_id == current_user.tenant_id)
    if keyword:
        stmt = stmt.where(
            or_(
                User.username.ilike(f"%{keyword}%"),
                User.full_name.ilike(f"%{keyword}%"),
                User.email.ilike(f"%{keyword}%"),
            )
        )
    if status_filter:
        stmt = stmt.where(User.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        stmt.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    )
    users = result.scalars().all()

    items: list[UserResponse] = []
    for u in users:
        roles = await _get_user_roles(db, u.id)
        items.append(UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            username=u.username,
            email=u.email,
            phone=u.phone,
            full_name=u.full_name,
            status=u.status,
            is_super_admin=u.is_super_admin,
            created_at=u.created_at,
            updated_at=u.updated_at,
            roles=roles,
        ))
    return PaginatedResponse.create(items, total, page, page_size)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="创建用户")
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "agency_admin")),
):
    """创建新用户。"""
    # 检查用户名唯一
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    tenant_id = body.tenant_id or current_user.tenant_id
    user = User(
        id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        username=body.username,
        email=body.email,
        phone=body.phone,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        status="active",
        is_super_admin=False,
    )
    db.add(user)
    await db.flush()

    # 分配角色
    if body.role_codes:
        for code in body.role_codes:
            role_result = await db.execute(
                select(Role).where(Role.tenant_id == tenant_id, Role.code == code)
            )
            role = role_result.scalar_one_or_none()
            if role:
                db.add(UserRole(user_id=user.id, role_id=role.id))

    await log_action(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="create_user",
        entity_type="user",
        entity_id=user.id,
        after={"username": user.username, "email": user.email},
    )
    await db.commit()

    roles = await _get_user_roles(db, user.id)
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        status=user.status,
        is_super_admin=user.is_super_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=roles,
    )


# --------------------------------------------------------------------------- #
# 角色管理（必须在 /{user_id} 之前定义，否则 /roles/all 会被 /{user_id} 捕获）
# --------------------------------------------------------------------------- #

@router.get("/roles/all", summary="角色列表")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前租户的所有角色。"""
    from app.core.deps import get_tenant_id
    tid = get_tenant_id(current_user)
    result = await db.execute(
        select(Role).where(Role.tenant_id == tid).order_by(Role.name)
    )
    roles = result.scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "code": r.code,
                "description": r.description,
                "permissions": r.permissions or [],
            }
            for r in roles
        ]
    }


@router.post("/roles", summary="创建角色")
async def create_role(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "agency_admin")),
):
    """创建自定义角色。"""
    from app.core.deps import get_tenant_id
    tid = get_tenant_id(current_user)
    name = body.get("name", "").strip()
    code = body.get("code", "").strip()
    if not name or not code:
        raise HTTPException(status_code=400, detail="角色名称和编码不能为空")

    existing = await db.execute(
        select(Role).where(Role.tenant_id == tid, Role.code == code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"角色编码 {code} 已存在")

    role = Role(
        id=uuid.uuid4().hex,
        tenant_id=tid,
        name=name,
        code=code,
        description=body.get("description", ""),
        permissions=body.get("permissions", []),
    )
    db.add(role)
    await log_action(
        db=db, tenant_id=tid, user_id=current_user.id,
        action="create_role", entity_type="role", entity_id=role.id,
        after={"name": name, "code": code},
    )
    await db.commit()
    return {"id": role.id, "name": name, "code": code}


@router.put("/roles/{role_id}", summary="更新角色")
async def update_role(
    role_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "agency_admin")),
):
    """更新角色（名称/描述/权限）。"""
    from app.core.deps import get_tenant_id
    tid = get_tenant_id(current_user)
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.tenant_id != tid:
        raise HTTPException(status_code=403, detail="无权修改")

    if "name" in body:
        role.name = body["name"]
    if "description" in body:
        role.description = body["description"]
    if "permissions" in body:
        role.permissions = body["permissions"]

    await log_action(
        db=db, tenant_id=tid, user_id=current_user.id,
        action="update_role", entity_type="role", entity_id=role.id,
    )
    await db.commit()
    return {"id": role.id, "name": role.name, "code": role.code}


@router.delete("/roles/{role_id}", summary="删除角色")
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin")),
):
    """删除自定义角色（系统内置角色不可删除）。"""
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    builtin_codes = {"super_admin", "agency_admin", "branch_admin", "tax_supervisor",
                     "accountant", "invoice_clerk", "customer_service", "operator",
                     "auditor", "substitute"}
    if role.code in builtin_codes:
        raise HTTPException(status_code=400, detail=f"系统内置角色 {role.name} 不可删除")

    links = await db.execute(select(UserRole).where(UserRole.role_id == role_id))
    if links.scalars().all():
        raise HTTPException(status_code=400, detail="该角色仍有用户关联，请先解除关联")

    await log_action(
        db=db, tenant_id=current_user.tenant_id, user_id=current_user.id,
        action="delete_role", entity_type="role", entity_id=role.id,
        before={"name": role.name, "code": role.code},
    )
    await db.delete(role)
    await db.commit()
    return {"message": "角色已删除"}


@router.post("/{user_id}/roles", summary="分配角色给用户")
async def assign_roles(
    user_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "agency_admin")),
):
    """给用户分配角色（覆盖式）。"""
    from app.core.deps import get_tenant_id
    tid = get_tenant_id(current_user)
    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    role_ids = body.get("role_ids", [])
    if role_ids:
        valid_roles = await db.execute(
            select(Role.id).where(Role.id.in_(role_ids), Role.tenant_id == tid)
        )
        valid_ids = {r[0] for r in valid_roles.all()}
        role_ids = [rid for rid in role_ids if rid in valid_ids]

    old_links = await db.execute(select(UserRole).where(UserRole.user_id == user_id))
    for link in old_links.scalars().all():
        await db.delete(link)

    for rid in role_ids:
        db.add(UserRole(user_id=user_id, role_id=rid))

    await log_action(
        db=db, tenant_id=tid, user_id=current_user.id,
        action="assign_roles", entity_type="user", entity_id=user_id,
        after={"role_ids": role_ids},
    )
    await db.commit()
    return {"message": "角色已更新", "role_ids": role_ids}


@router.get("/{user_id}", response_model=UserResponse, summary="用户详情")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取用户详情。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.tenant_id != current_user.tenant_id and not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="无权访问")
    roles = await _get_user_roles(db, user.id)
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        status=user.status,
        is_super_admin=user.is_super_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=roles,
    )


@router.put("/{user_id}", response_model=UserResponse, summary="更新用户")
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "agency_admin")),
):
    """更新用户信息。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    before = {
        "email": user.email,
        "phone": user.phone,
        "full_name": user.full_name,
        "status": user.status,
    }

    if body.email is not None:
        user.email = body.email
    if body.phone is not None:
        user.phone = body.phone
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.status is not None:
        user.status = body.status

    # 更新角色
    if body.role_codes is not None:
        # 删除旧关联
        old_links = await db.execute(select(UserRole).where(UserRole.user_id == user.id))
        for link in old_links.scalars().all():
            await db.delete(link)
        # 添加新关联
        for code in body.role_codes:
            role_result = await db.execute(
                select(Role).where(Role.tenant_id == user.tenant_id, Role.code == code)
            )
            role = role_result.scalar_one_or_none()
            if role:
                db.add(UserRole(user_id=user.id, role_id=role.id))

    await log_action(
        db=db,
        tenant_id=user.tenant_id,
        user_id=current_user.id,
        action="update_user",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={
            "email": user.email,
            "phone": user.phone,
            "full_name": user.full_name,
            "status": user.status,
        },
    )
    await db.commit()

    roles = await _get_user_roles(db, user.id)
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        status=user.status,
        is_super_admin=user.is_super_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=roles,
    )


@router.delete("/{user_id}", summary="停用用户")
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "agency_admin")),
):
    """停用用户（软删除）。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.is_super_admin:
        raise HTTPException(status_code=400, detail="不能停用超级管理员")

    user.status = "inactive"
    await log_action(
        db=db,
        tenant_id=user.tenant_id,
        user_id=current_user.id,
        action="deactivate_user",
        entity_type="user",
        entity_id=user.id,
    )
    await db.commit()
    return {"message": "用户已停用"}
