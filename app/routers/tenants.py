from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db, get_tenant_id
from ..models import Tenant, User, AuditLog
from ..schemas import (
    TenantCreate, TenantUpdate, TenantResponse, UserCreate, UserUpdate, UserResponse,
    PaginatedResponse
)
from ..auth import get_current_user, require_admin, require_manager
from ..config import settings
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("/", response_model=TenantResponse)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Create a new tenant (admin only)"""
    existing_tenant = db.query(Tenant).filter(Tenant.domain == tenant_data.domain).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain already exists"
        )
    
    tenant = Tenant(
        id=f"tenant_{len(str(hash(tenant_data.domain)))}",
        name=tenant_data.name,
        domain=tenant_data.domain,
        plan=tenant_data.plan,
        employee_count=tenant_data.employee_count,
        sso_config=tenant_data.sso_config
    )
    
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    logger.info("Tenant created", tenant_id=tenant.id, created_by=current_user.id)
    
    return tenant


@router.get("/", response_model=List[TenantResponse])
async def list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """List all tenants (admin only)"""
    tenants = db.query(Tenant).offset(skip).limit(limit).all()
    return tenants


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Get tenant by ID (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return tenant


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    tenant_data: TenantUpdate,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Update tenant (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    update_data = tenant_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    db.commit()
    db.refresh(tenant)
    
    logger.info("Tenant updated", tenant_id=tenant.id, updated_by=current_user.id)
    
    return tenant


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Delete tenant (admin only)"""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    tenant.is_active = False
    db.commit()
    
    logger.info("Tenant deleted", tenant_id=tenant.id, deleted_by=current_user.id)
    
    return {"message": "Tenant deleted successfully"}


@router.get("/{tenant_id}/users", response_model=PaginatedResponse)
async def list_tenant_users(
    tenant_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_manager()),
    db: Session = Depends(get_db)
):
    """List users for a specific tenant (manager/admin only)"""
    if current_user.tenant_id != tenant_id and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    users_query = db.query(User).filter(User.tenant_id == tenant_id)
    total = users_query.count()
    users = users_query.offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        items=users,
        total=total,
        page=skip // limit + 1,
        size=limit,
        pages=(total + limit - 1) // limit
    )


@router.post("/{tenant_id}/users", response_model=UserResponse)
async def create_tenant_user(
    tenant_id: str,
    user_data: UserCreate,
    current_user: User = Depends(require_manager()),
    db: Session = Depends(get_db)
):
    """Create user for a specific tenant (manager/admin only)"""
    if current_user.tenant_id != tenant_id and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active == True).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    existing_user = db.query(User).filter(
        User.email == user_data.email,
        User.tenant_id == tenant_id
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists in this tenant"
        )
    
    user = User(
        id=f"user_{len(str(hash(user_data.email)))}",
        tenant_id=tenant_id,
        email=user_data.email,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        department=user_data.department,
        roles=user_data.roles,
        sso_attributes=user_data.sso_attributes
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info("User created", user_id=user.id, tenant_id=tenant_id, created_by=current_user.id)
    
    return user


@router.get("/{tenant_id}/users/{user_id}", response_model=UserResponse)
async def get_tenant_user(
    tenant_id: str,
    user_id: str,
    current_user: User = Depends(require_manager()),
    db: Session = Depends(get_db)
):
    """Get user for a specific tenant (manager/admin only)"""
    if current_user.tenant_id != tenant_id and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/{tenant_id}/users/{user_id}", response_model=UserResponse)
async def update_tenant_user(
    tenant_id: str,
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(require_manager()),
    db: Session = Depends(get_db)
):
    """Update user for a specific tenant (manager/admin only)"""
    if current_user.tenant_id != tenant_id and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    logger.info("User updated", user_id=user.id, tenant_id=tenant_id, updated_by=current_user.id)
    
    return user


@router.delete("/{tenant_id}/users/{user_id}")
async def delete_tenant_user(
    tenant_id: str,
    user_id: str,
    current_user: User = Depends(require_manager()),
    db: Session = Depends(get_db)
):
    """Delete user for a specific tenant (manager/admin only)"""    
    if current_user.tenant_id != tenant_id and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    db.commit()
    
    logger.info("User deleted", user_id=user.id, tenant_id=tenant_id, deleted_by=current_user.id)
    
    return {"message": "User deleted successfully"}


@router.get("/{tenant_id}/audit-logs")
async def get_tenant_audit_logs(
    tenant_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Get audit logs for a specific tenant (admin only)"""
    if current_user.tenant_id != tenant_id and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    audit_logs = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id
    ).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    return audit_logs 