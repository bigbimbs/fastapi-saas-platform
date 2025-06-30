from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import time
import structlog
from .database import get_db, get_tenant_id, set_tenant_id
from .models import RateLimit, AuditLog, Tenant
from .config import settings

logger = structlog.get_logger()


class RateLimitMiddleware:
    def __init__(self, requests_per_minute: int = 100, burst_limit: int = 20):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
    
    async def __call__(self, request: Request, call_next):
        if request.url.path in ["/health", "/metrics"] or request.url.path.startswith("/webhooks"):
            return await call_next(request)
        
        tenant_id = self._get_tenant_id(request)
        if not tenant_id:
            return await call_next(request)
        
        if not self._check_rate_limit(request, tenant_id):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests",
                    "retry_after": 60
                }
            )
        
        return await call_next(request)
    
    def _get_tenant_id(self, request: Request) -> Optional[str]:
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return tenant_id
        
        host = request.headers.get("host", "")
        domain = host.split(":")[0]
        
        if domain.startswith("tenant-"):
            return domain.split("-")[1]
        
        return None
    
    def _check_rate_limit(self, request: Request, tenant_id: str) -> bool:
        try:
            db = next(get_db())
            
            now = datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + timedelta(minutes=1)
            
            rate_limit = db.query(RateLimit).filter(
                RateLimit.tenant_id == tenant_id,
                RateLimit.endpoint == request.url.path,
                RateLimit.window_start == window_start
            ).first()
            
            if rate_limit:
                if rate_limit.request_count >= self.requests_per_minute:
                    return False
                rate_limit.request_count += 1
            else:
                rate_limit = RateLimit(
                    tenant_id=tenant_id,
                    endpoint=request.url.path,
                    ip_address=request.client.host,
                    request_count=1,
                    window_start=window_start,
                    window_end=window_end
                )
                db.add(rate_limit)
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            return True


class AuditLogMiddleware:
    async def __call__(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            await self._log_audit_event(request, response, start_time)
        
        return response
    
    async def _log_audit_event(self, request: Request, response: Response, start_time: float):
        try:
            tenant_id = get_tenant_id()
            if not tenant_id:
                return
            
            action = self._get_action_type(request.method)
            resource_type = self._get_resource_type(request.url.path)
            resource_id = self._extract_resource_id(request.url.path)
            
            user_id = None
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                from .auth import verify_token
                token = auth_header.split(" ")[1]
                payload = verify_token(token)
                if payload:
                    user_id = payload.get("sub")
            
            db = next(get_db())
            audit_log = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                old_values=None,
                new_values=None
            )
            
            db.add(audit_log)
            db.commit()
            
        except Exception as e:
            logger.error("Audit logging failed", error=str(e))
    
    def _get_action_type(self, method: str) -> str:
        return {
            "POST": "CREATE",
            "PUT": "UPDATE",
            "PATCH": "UPDATE",
            "DELETE": "DELETE"
        }.get(method, "UNKNOWN")
    
    def _get_resource_type(self, path: str) -> str:
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[1].upper()
        return "UNKNOWN"
    
    def _extract_resource_id(self, path: str) -> str:
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            return parts[2]
        return "unknown"


class TenantContextMiddleware:
    async def __call__(self, request: Request, call_next):
        tenant_id = self._resolve_tenant(request)
        if tenant_id:
            set_tenant_id(tenant_id)
        
        response = await call_next(request)
        
        from .database import clear_tenant_id
        clear_tenant_id()
        
        return response
    
    def _resolve_tenant(self, request: Request) -> Optional[str]:
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return tenant_id
        
        host = request.headers.get("host", "")
        domain = host.split(":")[0]
        
        if domain.startswith("tenant-"):
            return domain.split("-")[1]
        
        return None


class ErrorHandlingMiddleware:
    async def __call__(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unhandled exception", error=str(e), path=request.url.path)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )


class SecurityHeadersMiddleware:
    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response 