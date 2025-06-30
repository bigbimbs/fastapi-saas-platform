from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional
from ..database import get_db, get_tenant_id
from ..models import User, Tenant
from ..schemas import UserLogin, Token, SSOLoginRequest, UserResponse
from ..auth import (
    authenticate_user, create_access_token, get_current_user,
    verify_sso_token, map_sso_attributes, require_admin
)
from ..config import settings
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    user_credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        host = request.headers.get("host", "")
        domain = host.split(":")[0]
        tenant = db.query(Tenant).filter(
            Tenant.domain == domain,
            Tenant.is_active == True
        ).first()
        if tenant:
            tenant_id = tenant.id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant not found"
            )
    
    user = await authenticate_user(
        email=user_credentials.email,
        password=user_credentials.password,
        tenant_id=tenant_id,
        db=db
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "roles": user.roles
    }
    
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": user
    }


@router.post("/sso/login", response_model=Token)
async def sso_login(
    sso_request: SSOLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        host = request.headers.get("host", "")
        domain = host.split(":")[0]
        tenant = db.query(Tenant).filter(
            Tenant.domain == domain,
            Tenant.is_active == True
        ).first()
        if tenant:
            tenant_id = tenant.id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant not found"
            )
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.sso_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO not configured for this tenant"
        )
    
    sso_data = verify_sso_token(sso_request.code, sso_request.provider, tenant)
    if not sso_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid SSO token"
        )
    
    mapped_data = map_sso_attributes(sso_data, tenant)
    
    user = db.query(User).filter(
        User.email == mapped_data.get("email"),
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        user = User(
            id=f"user_{sso_data['sub']}",
            tenant_id=tenant_id,
            email=mapped_data.get("email"),
            first_name=mapped_data.get("first_name", "SSO"),
            last_name=mapped_data.get("last_name", "User"),
            department=mapped_data.get("department"),
            roles=mapped_data.get("roles", ["employee"]),
            sso_attributes=sso_data
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    token_data = {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "roles": user.roles
    }
    
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": user
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}


@router.get("/sso/providers")
async def get_sso_providers(
    request: Request,
    db: Session = Depends(get_db)
):
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        host = request.headers.get("host", "")
        domain = host.split(":")[0]
        tenant = db.query(Tenant).filter(
            Tenant.domain == domain,
            Tenant.is_active == True
        ).first()
        if tenant:
            tenant_id = tenant.id
        else:
            return {"providers": []}
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant or not tenant.sso_config:
        return {"providers": []}
    
    return {
        "providers": [
            {
                "name": tenant.sso_config.get("provider"),
                "domain": tenant.sso_config.get("domain"),
                "client_id": tenant.sso_config.get("client_id")
            }
        ]
    } 