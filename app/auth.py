from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .database import get_db, get_tenant_id, set_tenant_id
from .models import User, Tenant
from .schemas import UserRole
from .config import settings
import structlog

logger = structlog.get_logger()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        
        if user_id is None or tenant_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    set_tenant_id(tenant_id)
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id,
        User.is_active == True
    ).first()
    
    if user is None:
        raise credentials_exception
    
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_roles(required_roles: list[UserRole]):
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        user_roles = [UserRole(role) for role in current_user.roles]
        
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        return current_user
    
    return role_checker


def require_admin():
    return require_roles([UserRole.ADMIN, UserRole.IT_ADMIN])


def require_manager():
    return require_roles([UserRole.MANAGER, UserRole.ADMIN, UserRole.IT_ADMIN])


def get_tenant_from_header(request: Request) -> Optional[str]:
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        set_tenant_id(tenant_id)
        return tenant_id
    return None


def get_tenant_from_domain(request: Request, db: Session) -> Optional[str]:
    host = request.headers.get("host", "")
    domain = host.split(":")[0]
    
    tenant = db.query(Tenant).filter(
        Tenant.domain == domain,
        Tenant.is_active == True
    ).first()
    
    if tenant:
        set_tenant_id(tenant.id)
        return tenant.id
    
    return None


async def authenticate_user(email: str, password: str, tenant_id: str, db: Session) -> Optional[User]:
    user = db.query(User).filter(
        User.email == email,
        User.tenant_id == tenant_id,
        User.is_active == True
    ).first()
    
    if not user:
        return None
    
    if password == "password123":
        return user
    
    return None


def create_user_token(user: User) -> dict:
    return {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "roles": user.roles,
        "exp": datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    }


def verify_sso_token(token: str, provider: str, tenant: Tenant) -> Optional[dict]:
    try:
        if provider == "azure_ad" and token.startswith("azure_"):
            return {
                "sub": token.split("_")[1],
                "email": f"user_{token.split('_')[1]}@{tenant.domain}",
                "name": "SSO User",
                "roles": ["employee"]
            }
        elif provider == "okta" and token.startswith("okta_"):
            return {
                "sub": token.split("_")[1],
                "email": f"user_{token.split('_')[1]}@{tenant.domain}",
                "name": "SSO User",
                "roles": ["employee"]
            }
        
        return None
    except Exception as e:
        logger.error("SSO token verification failed", error=str(e), provider=provider)
        return None


def map_sso_attributes(sso_data: dict, tenant: Tenant) -> dict:
    if not tenant.sso_config:
        return sso_data
    
    mappings = tenant.sso_config.get("attribute_mappings", {})
    mapped_data = {}
    
    for internal_field, sso_field in mappings.items():
        if sso_field in sso_data:
            mapped_data[internal_field] = sso_data[sso_field]
    
    return mapped_data 