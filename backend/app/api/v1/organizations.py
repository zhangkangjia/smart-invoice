"""组织架构路由。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.organization import Agency, Branch, Department, Team
from app.models.user import User
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/organizations", tags=["组织架构"])


class AgencyCreate(BaseModel):
    name: str
    code: str


class BranchCreate(BaseModel):
    agency_id: str
    name: str
    code: str


# --- 机构 --- #

@router.get("/agencies", summary="机构列表")
async def list_agencies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询机构列表。"""
    stmt = select(Agency).where(Agency.tenant_id == current_user.tenant_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(stmt.order_by(Agency.created_at.desc()).offset(offset).limit(page_size))
    agencies = result.scalars().all()
    return {
        "items": [
            {
                "id": a.id,
                "name": a.name,
                "code": a.code,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in agencies
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/agencies", status_code=201, summary="创建机构")
async def create_agency(
    body: AgencyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建机构。"""
    agency = Agency(
        id=uuid.uuid4().hex,
        tenant_id=current_user.tenant_id,
        name=body.name,
        code=body.code,
        status="active",
    )
    db.add(agency)
    await db.commit()
    await db.refresh(agency)
    return {"id": agency.id, "name": agency.name, "code": agency.code}


# --- 分公司 --- #

@router.get("/branches", summary="分公司列表")
async def list_branches(
    agency_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询分公司列表。"""
    stmt = select(Branch).where(Branch.tenant_id == current_user.tenant_id)
    if agency_id:
        stmt = stmt.where(Branch.agency_id == agency_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(stmt.order_by(Branch.created_at.desc()).offset(offset).limit(page_size))
    branches = result.scalars().all()
    return {
        "items": [
            {
                "id": b.id,
                "agency_id": b.agency_id,
                "name": b.name,
                "code": b.code,
                "status": b.status,
            }
            for b in branches
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/branches", status_code=201, summary="创建分公司")
async def create_branch(
    body: BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建分公司。"""
    branch = Branch(
        id=uuid.uuid4().hex,
        tenant_id=current_user.tenant_id,
        agency_id=body.agency_id,
        name=body.name,
        code=body.code,
        status="active",
    )
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return {"id": branch.id, "name": branch.name, "code": branch.code}


# --- 部门 --- #

@router.get("/departments", summary="部门列表")
async def list_departments(
    branch_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询部门列表。"""
    stmt = select(Department).where(Department.tenant_id == current_user.tenant_id)
    if branch_id:
        stmt = stmt.where(Department.branch_id == branch_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(stmt.order_by(Department.created_at.desc()).offset(offset).limit(page_size))
    departments = result.scalars().all()
    return {
        "items": [
            {
                "id": d.id,
                "branch_id": d.branch_id,
                "name": d.name,
                "code": d.code,
                "status": d.status,
            }
            for d in departments
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# --- 团队 --- #

@router.get("/teams", summary="团队列表")
async def list_teams(
    department_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """分页查询团队列表。"""
    stmt = select(Team).where(Team.tenant_id == current_user.tenant_id)
    if department_id:
        stmt = stmt.where(Team.department_id == department_id)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(stmt.order_by(Team.created_at.desc()).offset(offset).limit(page_size))
    teams = result.scalars().all()
    return {
        "items": [
            {
                "id": t.id,
                "department_id": t.department_id,
                "name": t.name,
                "code": t.code,
                "status": t.status,
            }
            for t in teams
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
