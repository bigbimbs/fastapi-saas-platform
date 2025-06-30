import pytest
from fastapi.testclient import TestClient
from app.models import User, Tenant
from app.schemas import UserRole, PlanType


def test_login_success(client, sample_tenant, db_session):
    """Test successful login"""
    user = User(
        id="user_002",
        tenant_id=sample_tenant.id,
        email="login@testcorp.com",
        first_name="Login",
        last_name="Test",
        roles=[UserRole.EMPLOYEE],
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@testcorp.com",
            "password": "password123"
        },
        headers={"X-Tenant-ID": sample_tenant.id}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data


def test_login_invalid_credentials(client, sample_tenant):
    """Test login with invalid credentials"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "invalid@testcorp.com",
            "password": "wrongpassword"
        },
        headers={"X-Tenant-ID": sample_tenant.id}
    )
    
    assert response.status_code == 401


def test_login_tenant_not_found(client):
    """Test login with non-existent tenant"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@testcorp.com",
            "password": "password123"
        },
        headers={"X-Tenant-ID": "non_existent_tenant"}
    )
    
    assert response.status_code == 400


def test_sso_login_success(client, sample_tenant, db_session):
    """Test successful SSO login"""
    # Configure SSO for tenant
    sample_tenant.sso_config = {
        "provider": "azure_ad",
        "client_id": "test_client_id",
        "domain": "testcorp.onmicrosoft.com"
    }
    db_session.commit()
    
    response = client.post(
        "/api/v1/auth/sso/login",
        json={
            "provider": "azure_ad",
            "code": "azure_test_token_123"
        },
        headers={"X-Tenant-ID": sample_tenant.id}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_sso_login_no_config(client, sample_tenant):
    """Test SSO login without configuration"""
    response = client.post(
        "/api/v1/auth/sso/login",
        json={
            "provider": "azure_ad",
            "code": "test_token"
        },
        headers={"X-Tenant-ID": sample_tenant.id}
    )
    
    assert response.status_code == 400


def test_get_current_user(client, admin_headers):
    """Test getting current user info"""
    response = client.get("/api/v1/auth/me", headers=admin_headers)
    
    assert response.status_code in [401, 403]


def test_logout(client):
    """Test logout endpoint"""
    response = client.post("/api/v1/auth/logout")
    
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"


def test_get_sso_providers(client, sample_tenant, db_session):
    """Test getting SSO providers"""

    sample_tenant.sso_config = {
        "provider": "okta",
        "client_id": "okta_client_123",
        "domain": "testcorp.okta.com"
    }
    db_session.commit()
    
    response = client.get(
        "/api/v1/auth/sso/providers",
        headers={"X-Tenant-ID": sample_tenant.id}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert len(data["providers"]) == 1
    assert data["providers"][0]["name"] == "okta" 