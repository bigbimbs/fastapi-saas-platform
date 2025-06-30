import asyncio
import httpx
import structlog
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.orm import Session
from .database import get_db
from .models import WebhookEvent, IntegrationStatus
from .schemas import WebhookStatus, IntegrationStatusType, CircuitBreakerState
from .config import settings
import json
import hashlib

logger = structlog.get_logger()


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
    
    def call(self, func, *args, **kwargs):
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        if not self.last_failure_time:
            return True
        
        return datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)
    
    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class ExternalServiceClient:
    def __init__(self, service_name: str, base_url: str, auth_type: str = "api_key"):
        self.service_name = service_name
        self.base_url = base_url
        self.auth_type = auth_type
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout
        )
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                          headers: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        
        def _make_request():
            return asyncio.run(self._async_request(method, url, data, headers))
        
        return self.circuit_breaker.call(_make_request)
    
    async def _async_request(self, method: str, url: str, data: Optional[Dict] = None,
                           headers: Optional[Dict] = None) -> Dict[str, Any]:
        try:
            response = await self.client.request(
                method=method,
                url=url,
                json=data,
                headers=headers or {}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {self.service_name}", 
                        status_code=e.response.status_code, 
                        response_text=e.response.text)
            raise
        except Exception as e:
            logger.error(f"Request error for {self.service_name}", error=str(e))
            raise
    
    async def close(self):
        await self.client.aclose()


class UserServiceClient(ExternalServiceClient):
    def __init__(self):
        super().__init__(
            service_name="user_service",
            base_url=settings.user_service_url,
            auth_type="api_key"
        )
    
    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.make_request("POST", "/users", data=user_data)
    
    async def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.make_request("PUT", f"/users/{user_id}", data=user_data)
    
    async def delete_user(self, user_id: str) -> Dict[str, Any]:
        return await self.make_request("DELETE", f"/users/{user_id}")
    
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        return await self.make_request("GET", f"/users/{user_id}")


class PaymentServiceClient(ExternalServiceClient):
    def __init__(self):
        super().__init__(
            service_name="payment_service",
            base_url=settings.payment_service_url,
            auth_type="oauth2"
        )
    
    async def create_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.make_request("POST", "/subscriptions", data=subscription_data)
    
    async def update_subscription(self, subscription_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.make_request("PUT", f"/subscriptions/{subscription_id}", data=data)
    
    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return await self.make_request("DELETE", f"/subscriptions/{subscription_id}")
    
    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.make_request("POST", "/payments", data=payment_data)


class CommunicationServiceClient(ExternalServiceClient):
    def __init__(self):
        super().__init__(
            service_name="communication_service",
            base_url=settings.communication_service_url,
            auth_type="bearer_token"
        )
    
    async def send_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.make_request("POST", "/emails", data=email_data)
    
    async def send_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.make_request("POST", "/notifications", data=notification_data)
    
    async def get_delivery_status(self, message_id: str) -> Dict[str, Any]:
        return await self.make_request("GET", f"/messages/{message_id}/status")


class WebhookProcessor:
    def __init__(self):
        self.user_client = UserServiceClient()
        self.payment_client = PaymentServiceClient()
        self.communication_client = CommunicationServiceClient()
        self.clients = {
            "user_service": self.user_client,
            "payment_service": self.payment_client,
            "communication_service": self.communication_client
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError))
    )
    async def process_webhook_event(self, event: WebhookEvent, db: Session) -> bool:
        """Process a webhook event with retry logic"""
        try:
            logger.info(f"Processing webhook event", 
                       event_id=event.event_id, 
                       event_type=event.event_type, 
                       source=event.source)
            
            # Update event status to processing
            event.status = WebhookStatus.PROCESSING
            db.commit()
            
            # Process based on event type
            success = await self._process_event_by_type(event, db)
            
            if success:
                event.status = WebhookStatus.COMPLETED
                event.processed_at = datetime.utcnow()
            else:
                event.status = WebhookStatus.FAILED
                event.error_message = "Event processing failed"
            
            db.commit()
            return success
            
        except Exception as e:
            logger.error(f"Webhook processing failed", 
                        event_id=event.event_id, 
                        error=str(e))
            
            event.status = WebhookStatus.FAILED
            event.error_message = str(e)
            event.retry_count += 1
            db.commit()
            
            raise
    
    async def _process_event_by_type(self, event: WebhookEvent, db: Session) -> bool:
        """Process event based on its type"""
        if event.source == "user_service":
            return await self._process_user_event(event, db)
        elif event.source == "payment_service":
            return await self._process_payment_event(event, db)
        elif event.source == "communication_service":
            return await self._process_communication_event(event, db)
        else:
            logger.warning(f"Unknown webhook source", source=event.source)
            return False
    
    async def _process_user_event(self, event: WebhookEvent, db: Session) -> bool:
        """Process user service events"""
        try:
            if event.event_type == "user.created":
                # Sync user creation with internal system
                user_data = event.data
                # Here you would create/update user in your system
                logger.info(f"User created event processed", user_id=user_data.get("user_id"))
                return True
                
            elif event.event_type == "user.updated":
                # Sync user updates with internal system
                user_data = event.data
                logger.info(f"User updated event processed", user_id=user_data.get("user_id"))
                return True
                
            elif event.event_type == "user.deleted":
                # Handle user deletion
                user_data = event.data
                logger.info(f"User deleted event processed", user_id=user_data.get("user_id"))
                return True
                
        except Exception as e:
            logger.error(f"User event processing failed", error=str(e))
            return False
    
    async def _process_payment_event(self, event: WebhookEvent, db: Session) -> bool:
        """Process payment service events"""
        try:
            if event.event_type == "subscription.created":
                # Handle new subscription
                subscription_data = event.data
                logger.info(f"Subscription created event processed", 
                           subscription_id=subscription_data.get("subscription_id"))
                return True
                
            elif event.event_type == "payment.failed":
                # Handle payment failure
                payment_data = event.data
                logger.info(f"Payment failed event processed", 
                           payment_id=payment_data.get("payment_id"))
                return True
                
        except Exception as e:
            logger.error(f"Payment event processing failed", error=str(e))
            return False
    
    async def _process_communication_event(self, event: WebhookEvent, db: Session) -> bool:
        """Process communication service events"""
        try:
            if event.event_type == "message.delivered":
                # Update message delivery status
                message_data = event.data
                logger.info(f"Message delivered event processed", 
                           message_id=message_data.get("message_id"))
                return True
                
            elif event.event_type == "message.bounced":
                # Handle message bounce
                message_data = event.data
                logger.info(f"Message bounced event processed", 
                           message_id=message_data.get("message_id"))
                return True
                
        except Exception as e:
            logger.error(f"Communication event processing failed", error=str(e))
            return False
    
    async def close(self):
        """Close all clients"""
        await self.user_client.close()
        await self.payment_client.close()
        await self.communication_client.close()


class IntegrationHealthMonitor:
    """Monitor integration health and status"""
    
    def __init__(self):
        self.processor = WebhookProcessor()
    
    async def check_service_health(self, service_name: str, tenant_id: str, db: Session) -> Dict[str, Any]:
        """Check health of external service"""
        try:
            client = self.processor.clients.get(service_name)
            if not client:
                return {"status": "unknown", "error": "Service not found"}
            
            start_time = datetime.utcnow()
                    
            if service_name == "user_service":
                response = await client.make_request("GET", "/health")
            elif service_name == "payment_service":
                response = await client.make_request("GET", "/health")
            elif service_name == "communication_service":
                response = await client.make_request("GET", "/health")
            else:
                return {"status": "unknown", "error": "Service not supported"}
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update integration status
            status_record = db.query(IntegrationStatus).filter(
                IntegrationStatus.tenant_id == tenant_id,
                IntegrationStatus.service_name == service_name
            ).first()
            
            if not status_record:
                status_record = IntegrationStatus(
                    tenant_id=tenant_id,
                    service_name=service_name,
                    status=IntegrationStatusType.HEALTHY,
                    response_time_ms=int(response_time),
                    success_count=1,
                    error_count=0,
                    circuit_breaker_state=client.circuit_breaker.state
                )
                db.add(status_record)
            else:
                status_record.status = IntegrationStatusType.HEALTHY
                status_record.response_time_ms = int(response_time)
                status_record.success_count += 1
                status_record.last_check = datetime.utcnow()
                status_record.circuit_breaker_state = client.circuit_breaker.state
                status_record.last_error = None
            
            db.commit()
            
            return {
                "status": "healthy",
                "response_time_ms": int(response_time),
                "circuit_breaker_state": client.circuit_breaker.state.value
            }
            
        except Exception as e:
            logger.error(f"Health check failed for {service_name}", error=str(e))
            
            # Update status with error
            status_record = db.query(IntegrationStatus).filter(
                IntegrationStatus.tenant_id == tenant_id,
                IntegrationStatus.service_name == service_name
            ).first()
            
            if not status_record:
                status_record = IntegrationStatus(
                    tenant_id=tenant_id,
                    service_name=service_name,
                    status=IntegrationStatusType.DOWN,
                    error_count=1,
                    success_count=0,
                    circuit_breaker_state=CircuitBreakerState.OPEN,
                    last_error=str(e)
                )
                db.add(status_record)
            else:
                status_record.status = IntegrationStatusType.DOWN
                status_record.error_count += 1
                status_record.last_check = datetime.utcnow()
                status_record.circuit_breaker_state = CircuitBreakerState.OPEN
                status_record.last_error = str(e)
            
            db.commit()
            
            return {
                "status": "down",
                "error": str(e),
                "circuit_breaker_state": CircuitBreakerState.OPEN.value
            }
    
    async def close(self):
        """Close processor"""
        await self.processor.close() 