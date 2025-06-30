from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    IT_ADMIN = "it-admin"


class PlanType(str, Enum):
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class WebhookStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IntegrationStatusType(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class TenantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=255)
    plan: PlanType = PlanType.BASIC
    employee_count: int = Field(0, ge=0)
    sso_config: Optional[Dict[str, Any]] = None


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, min_length=1, max_length=255)
    plan: Optional[PlanType] = None
    employee_count: Optional[int] = Field(None, ge=0)
    sso_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class TenantResponse(TenantBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    roles: List[UserRole] = [UserRole.EMPLOYEE]
    sso_attributes: Optional[Dict[str, Any]] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    roles: Optional[List[UserRole]] = None
    sso_attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: str
    tenant_id: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class AuditLogResponse(BaseModel):
    id: int
    tenant_id: str
    user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: str
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class WebhookEventBase(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    event_id: str = Field(..., min_length=1, max_length=50)
    source: str = Field(..., min_length=1, max_length=100)
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class WebhookEventCreate(WebhookEventBase):
    pass


class WebhookEventResponse(WebhookEventBase):
    id: str
    tenant_id: str
    status: WebhookStatus
    retry_count: int
    max_retries: int
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class IntegrationStatusResponse(BaseModel):
    id: int
    tenant_id: str
    service_name: str
    status: IntegrationStatusType
    last_check: datetime
    response_time_ms: Optional[int] = None
    error_count: int
    success_count: int
    circuit_breaker_state: CircuitBreakerState
    last_error: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    database: str
    redis: str
    integrations: Dict[str, str]


class RateLimitResponse(BaseModel):
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


class SSOConfig(BaseModel):
    provider: str
    tenant_id: Optional[str] = None
    client_id: str
    domain: str
    attribute_mappings: Dict[str, str]
    role_mappings: Dict[str, List[str]]


class SSOLoginRequest(BaseModel):
    provider: str
    code: str
    state: Optional[str] = None


class ExternalUserData(BaseModel):
    user_id: str
    email: EmailStr
    first_name: str
    last_name: str
    department: Optional[str] = None
    title: Optional[str] = None
    status: str = "active"
    hire_date: Optional[str] = None


class ExternalPaymentData(BaseModel):
    subscription_id: str
    customer_id: str
    plan: str
    status: str
    billing_cycle: str
    amount: float
    currency: str = "USD"
    trial_end: Optional[datetime] = None


class ExternalCommunicationData(BaseModel):
    message_id: str
    recipient: EmailStr
    template: str
    status: str
    delivery_time_ms: Optional[int] = None
    esp_message_id: Optional[str] = None 