from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import json
import hashlib
import hmac
import structlog
from datetime import datetime
from ..database import get_db, get_tenant_id
from ..models import WebhookEvent, Tenant
from ..schemas import WebhookEventCreate, WebhookEventResponse, PaginatedResponse
from ..integrations import WebhookProcessor, IntegrationHealthMonitor
from ..auth import get_current_user, require_admin
from ..config import settings

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
    
webhook_processor = WebhookProcessor()
health_monitor = IntegrationHealthMonitor()


@router.post("/user-service")
async def user_service_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Webhook endpoint for User Management Service"""
    return await _process_webhook(request, background_tasks, db, "user_service")


@router.post("/payment-service")
async def payment_service_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Webhook endpoint for Payment Service"""
    return await _process_webhook(request, background_tasks, db, "payment_service")


@router.post("/communication-service")
async def communication_service_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Webhook endpoint for Communication Service"""
    return await _process_webhook(request, background_tasks, db, "communication_service")


async def _process_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session,
    source: str
):
    """Process webhook from external service"""
    try:
        body = await request.body()
        payload = json.loads(body)
        
        signature = request.headers.get("X-Webhook-Signature")
        if not _verify_webhook_signature(body, signature, source):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        tenant_id = _extract_tenant_id(payload, request.headers)
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant ID not found"
            )
        
        tenant = db.query(Tenant).filter(
            Tenant.id == tenant_id,
            Tenant.is_active == True
        ).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        event = WebhookEvent(
            id=f"webhook_{hashlib.md5(f'{source}_{payload.get('event_id', '')}'.encode()).hexdigest()}",
            tenant_id=tenant_id,
            event_type=payload.get("event_type"),
            event_id=payload.get("event_id"),
            source=source,
            data=payload.get("data", {}),
            metadata=payload.get("metadata", {})
        )
        
        db.add(event)
        db.commit()
        db.refresh(event)
        
        background_tasks.add_task(_process_webhook_background, event.id, db)
        
        logger.info("Webhook received", 
                   event_id=event.event_id, 
                   event_type=event.event_type, 
                   source=source,
                   tenant_id=tenant_id)
        
        return {"status": "accepted", "event_id": event.id}
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.error("Webhook processing error", error=str(e), source=source)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


async def _process_webhook_background(event_id: str, db: Session):
    """Process webhook event in background"""
    try:
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        if not event:
            logger.error("Webhook event not found", event_id=event_id)
            return
        
        await webhook_processor.process_webhook_event(event, db)
        
    except Exception as e:
        logger.error("Background webhook processing failed", 
                    event_id=event_id, 
                    error=str(e))


def _verify_webhook_signature(body: bytes, signature: str, source: str) -> bool:
    """Verify webhook signature"""
    return True


def _extract_tenant_id(payload: Dict[str, Any], headers: Dict[str, str]) -> str:
    """Extract tenant ID from payload or headers"""
    tenant_id = payload.get("organization_id") or payload.get("tenant_id")
    if tenant_id:
        return tenant_id
    
    tenant_id = headers.get("X-Tenant-ID")
    if tenant_id:
        return tenant_id

    return "tenant_001"


@router.get("/events", response_model=PaginatedResponse)
async def list_webhook_events(
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    source: str = None,
    current_user = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """List webhook events (admin only)"""
    query = db.query(WebhookEvent)
    
    tenant_id = get_tenant_id()
    if tenant_id:
        query = query.filter(WebhookEvent.tenant_id == tenant_id)
    
    if status:
        query = query.filter(WebhookEvent.status == status)
    if source:
        query = query.filter(WebhookEvent.source == source)
    
    total = query.count()
    
    events = query.order_by(WebhookEvent.created_at.desc()).offset(skip).limit(limit).all()
    
    return PaginatedResponse(
        items=events,
        total=total,
        page=skip // limit + 1,
        size=limit,
        pages=(total + limit - 1) // limit
    )


@router.get("/events/{event_id}", response_model=WebhookEventResponse)
async def get_webhook_event(
    event_id: str,
    current_user = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Get webhook event by ID (admin only)"""
    event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook event not found"
        )
    
    tenant_id = get_tenant_id()
    if tenant_id and event.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return event


@router.post("/events/{event_id}/retry")
async def retry_webhook_event(
    event_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Retry failed webhook event (admin only)"""
    event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook event not found"
        )
    
    tenant_id = get_tenant_id()
    if tenant_id and event.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    event.status = "pending"
    event.retry_count += 1
    event.error_message = None
    db.commit()
    
    background_tasks.add_task(_process_webhook_background, event.id, db)
    
    return {"message": "Webhook event queued for retry"}


@router.get("/health/{service_name}")
async def check_service_health(
    service_name: str,
    current_user = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Check health of external service (admin only)"""
    tenant_id = get_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required"
        )
    
    health_status = await health_monitor.check_service_health(service_name, tenant_id, db)
    return health_status


@router.get("/health")
async def get_all_services_health(
    current_user = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Get health status of all external services (admin only)"""
    tenant_id = get_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required"
        )
    
    services = ["user_service", "payment_service", "communication_service"]
    health_status = {}
    
    for service in services:
        try:
            status = await health_monitor.check_service_health(service, tenant_id, db)
            health_status[service] = status
        except Exception as e:
            health_status[service] = {"status": "error", "error": str(e)}
    
    return health_status 