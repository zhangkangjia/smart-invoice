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
