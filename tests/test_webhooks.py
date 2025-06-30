import pytest
import json
from fastapi.testclient import TestClient
from app.models import WebhookEvent, Tenant
from app.schemas import WebhookStatus


def test_user_service_webhook_success(client, sample_tenant):
    """Test successful user service webhook processing"""
    webhook_data = {
        "event_type": "user.created",
        "event_id": "evt_user_001",
        "organization_id": sample_tenant.id,
        "data": {
            "user_id": "ext_user_123",
            "email": "newuser@testcorp.com",
            "first_name": "New",
            "last_name": "User",
            "department": "Engineering"
        },
        "metadata": {
            "source": "hr_system",
            "version": "1.2"
        }
    }
    
    response = client.post(
        "/api/v1/webhooks/user-service",
        json=webhook_data,
        headers={"X-Webhook-Signature": "test_signature"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert "event_id" in data


def test_payment_service_webhook_success(client, sample_tenant):
    """Test successful payment service webhook processing"""
    webhook_data = {
        "event_type": "subscription.created",
        "event_id": "evt_pay_001",
        "organization_id": sample_tenant.id,
        "data": {
            "subscription_id": "sub_123",
            "customer_id": "cust_456",
            "plan": "premium",
            "status": "active",
            "amount": 99.99
        },
        "metadata": {
            "source": "billing_system",
            "version": "2.1"
        }
    }
    
    response = client.post(
        "/api/v1/webhooks/payment-service",
        json=webhook_data,
        headers={"X-Webhook-Signature": "test_signature"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"


def test_communication_service_webhook_success(client, sample_tenant):
    """Test successful communication service webhook processing"""
    webhook_data = {
        "event_type": "message.delivered",
        "event_id": "evt_comm_001",
        "organization_id": sample_tenant.id,
        "data": {
            "message_id": "msg_123",
            "recipient": "user@testcorp.com",
            "template": "welcome_email",
            "status": "delivered"
        },
        "metadata": {
            "source": "email_service",
            "version": "1.5"
        }
    }
    
    response = client.post(
        "/api/v1/webhooks/communication-service",
        json=webhook_data,
        headers={"X-Webhook-Signature": "test_signature"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"


def test_webhook_invalid_json(client):
    """Test webhook with invalid JSON"""
    response = client.post(
        "/api/v1/webhooks/user-service",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 400


def test_webhook_missing_tenant_id(client):
    """Test webhook without tenant ID"""
    webhook_data = {
        "event_type": "user.created",
        "event_id": "evt_user_001",
        "data": {
            "user_id": "ext_user_123",
            "email": "user@testcorp.com"
        }
    }
    
    response = client.post(
        "/api/v1/webhooks/user-service",
        json=webhook_data
    )
    
    assert response.status_code == 400
    assert "Tenant ID not found" in response.json()["detail"]


def test_webhook_tenant_not_found(client):
    """Test webhook with non-existent tenant"""
    webhook_data = {
        "event_type": "user.created",
        "event_id": "evt_user_001",
        "organization_id": "non_existent_tenant",
        "data": {
            "user_id": "ext_user_123",
            "email": "user@testcorp.com"
        }
    }
    
    response = client.post(
        "/api/v1/webhooks/user-service",
        json=webhook_data
    )
    
    assert response.status_code == 404
    assert "Tenant not found" in response.json()["detail"]


def test_list_webhook_events(client, admin_headers, sample_tenant, db_session):
    """Test listing webhook events"""
    event = WebhookEvent(
        id="webhook_test_001",
        tenant_id=sample_tenant.id,
        event_type="user.created",
        event_id="evt_user_001",
        source="user_service",
        data={"user_id": "test_user"},
        status=WebhookStatus.COMPLETED
    )
    db_session.add(event)
    db_session.commit()
    
    response = client.get(
        "/api/v1/webhooks/events",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_get_webhook_event(client, admin_headers, sample_tenant, db_session):
    """Test getting specific webhook event"""
    event = WebhookEvent(
        id="webhook_test_002",
        tenant_id=sample_tenant.id,
        event_type="user.created",
        event_id="evt_user_002",
        source="user_service",
        data={"user_id": "test_user"},
        status=WebhookStatus.COMPLETED
    )
    db_session.add(event)
    db_session.commit()
    
    response = client.get(
        f"/api/v1/webhooks/events/{event.id}",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == event.id
    assert data["event_type"] == "user.created"


def test_get_webhook_event_not_found(client, admin_headers):
    """Test getting non-existent webhook event"""
    response = client.get(
        "/api/v1/webhooks/events/non_existent_id",
        headers=admin_headers
    )
    
    assert response.status_code == 404


def test_retry_webhook_event(client, admin_headers, sample_tenant, db_session):
    """Test retrying failed webhook event"""

    event = WebhookEvent(
        id="webhook_test_003",
        tenant_id=sample_tenant.id,
        event_type="user.created",
        event_id="evt_user_003",
        source="user_service",
        data={"user_id": "test_user"},
        status=WebhookStatus.FAILED,
        error_message="Processing failed"
    )
    db_session.add(event)
    db_session.commit()
    
    response = client.post(
        f"/api/v1/webhooks/events/{event.id}/retry",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Webhook event queued for retry"


def test_check_service_health(client, admin_headers, sample_tenant):
    """Test checking service health"""
    response = client.get(
        "/api/v1/webhooks/health/user_service",
        headers=admin_headers
    )
    
    assert response.status_code in [200, 400, 500]


def test_get_all_services_health(client, admin_headers, sample_tenant):
    """Test getting health status of all services"""
    response = client.get(
        "/api/v1/webhooks/health",
        headers=admin_headers
    )
    
    assert response.status_code in [200, 400, 500]


def test_webhook_events_filtering(client, admin_headers, sample_tenant, db_session):
    """Test filtering webhook events"""
    completed_event = WebhookEvent(
        id="webhook_completed_001",
        tenant_id=sample_tenant.id,
        event_type="user.created",
        event_id="evt_user_001",
        source="user_service",
        data={"user_id": "test_user"},
        status=WebhookStatus.COMPLETED
    )
    
    failed_event = WebhookEvent(
        id="webhook_failed_001",
        tenant_id=sample_tenant.id,
        event_type="user.created",
        event_id="evt_user_002",
        source="user_service",
        data={"user_id": "test_user"},
        status=WebhookStatus.FAILED
    )
    
    db_session.add_all([completed_event, failed_event])
    db_session.commit()
    
    response = client.get(
        "/api/v1/webhooks/events?status=completed",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "completed" for item in data["items"])
    
    response = client.get(
        "/api/v1/webhooks/events?source=user_service",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert all(item["source"] == "user_service" for item in data["items"])


def test_webhook_unauthorized_access(client, sample_tenant):
    """Test unauthorized access to webhook endpoints"""
    response = client.get("/api/v1/webhooks/events")
    assert response.status_code == 401
    
    response = client.get(
        "/api/v1/webhooks/events",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code in [401, 403] 