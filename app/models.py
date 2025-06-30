from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from .database import Base


class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    plan = Column(String(50), nullable=False, default="basic")
    employee_count = Column(Integer, default=0)
    sso_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    users = relationship("User", back_populates="tenant")
    audit_logs = relationship("AuditLog", back_populates="tenant")
    webhook_events = relationship("WebhookEvent", back_populates="tenant")
    integration_status = relationship("IntegrationStatus", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    
    id = Column(String(50), primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=True)
    roles = Column(JSON, default=list)
    sso_attributes = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    tenant = relationship("Tenant", back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    __table_args__ = (
        Index('idx_users_tenant_email', 'tenant_id', 'email'),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(50), nullable=False)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    tenant = relationship("Tenant", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index('idx_audit_tenant_timestamp', 'tenant_id', 'timestamp'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id = Column(String(50), primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    event_id = Column(String(50), nullable=False)
    source = Column(String(100), nullable=False)
    data = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=True)
    status = Column(String(50), default="pending")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    tenant = relationship("Tenant", back_populates="webhook_events")
    
    __table_args__ = (
        Index('idx_webhook_tenant_status', 'tenant_id', 'status'),
        Index('idx_webhook_source_type', 'source', 'event_type'),
        Index('idx_webhook_created', 'created_at'),
    )


class IntegrationStatus(Base):
    __tablename__ = "integration_status"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False)
    service_name = Column(String(100), nullable=False)
    status = Column(String(50), default="healthy")
    last_check = Column(DateTime(timezone=True), server_default=func.now())
    response_time_ms = Column(Integer, nullable=True)
    error_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    circuit_breaker_state = Column(String(50), default="closed")
    last_error = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)
    
    tenant = relationship("Tenant", back_populates="integration_status")
    
    __table_args__ = (
        Index('idx_integration_tenant_service', 'tenant_id', 'service_name'),
    )


class RateLimit(Base):
    __tablename__ = "rate_limits"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), nullable=False)
    endpoint = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_id = Column(String(50), nullable=True)
    request_count = Column(Integer, default=1)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    
    __table_args__ = (
        Index('idx_rate_limit_tenant_endpoint', 'tenant_id', 'endpoint', 'window_start'),
        Index('idx_rate_limit_ip', 'ip_address', 'endpoint', 'window_start'),
    ) 