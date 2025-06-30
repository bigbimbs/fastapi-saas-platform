import pytest
from fastapi.testclient import TestClient
from app.models import User, Tenant
from app.schemas import UserRole, PlanType


def test_create_tenant_success(client, admin_headers):
    """Test successful tenant creation"""
    tenant_data = {
        "name": "New Corp",
        "domain": "newcorp.com",
        "plan": "premium",
        "employee_count": 50
    }
    
    response = client.post(
        "/api/v1/tenants/",
        json=tenant_data,
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Corp"
    assert data["domain"] == "newcorp.com"
    assert data["plan"] == "premium"


def test_create_tenant_duplicate_domain(client, admin_headers, sample_tenant):
    """Test tenant creation with duplicate domain"""
    tenant_data = {
        "name": "Another Corp",
        "domain": sample_tenant.domain,  # Use existing domain
        "plan": "basic",
        "employee_count": 25
    }
    
    response = client.post(
        "/api/v1/tenants/",
        json=tenant_data,
        headers=admin_headers
    )
    
    assert response.status_code == 400
    assert "Domain already exists" in response.json()["detail"]


def test_list_tenants(client, admin_headers, sample_tenant):
    """Test listing tenants"""
    response = client.get("/api/v1/tenants/", headers=admin_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_tenant(client, admin_headers, sample_tenant):
    """Test getting specific tenant"""
    response = client.get(
        f"/api/v1/tenants/{sample_tenant.id}",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_tenant.id
    assert data["name"] == sample_tenant.name


def test_get_tenant_not_found(client, admin_headers):
    """Test getting non-existent tenant"""
    response = client.get(
        "/api/v1/tenants/non_existent_id",
        headers=admin_headers
    )
    
    assert response.status_code == 404


def test_update_tenant(client, admin_headers, sample_tenant):
    """Test updating tenant"""
    update_data = {
        "name": "Updated Corp",
        "employee_count": 150
    }
    
    response = client.put(
        f"/api/v1/tenants/{sample_tenant.id}",
        json=update_data,
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Corp"
    assert data["employee_count"] == 150


def test_delete_tenant(client, admin_headers, sample_tenant):
    """Test deleting tenant"""
    response = client.delete(
        f"/api/v1/tenants/{sample_tenant.id}",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Tenant deleted successfully"


def test_list_tenant_users(client, admin_headers, sample_tenant, sample_user):
    """Test listing users for a tenant"""
    response = client.get(
        f"/api/v1/tenants/{sample_tenant.id}/users",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_create_tenant_user(client, admin_headers, sample_tenant):
    """Test creating user for a tenant"""
    user_data = {
        "email": "newuser@testcorp.com",
        "first_name": "New",
        "last_name": "User",
        "department": "Sales",
        "roles": ["employee"]
    }
    
    response = client.post(
        f"/api/v1/tenants/{sample_tenant.id}/users",
        json=user_data,
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@testcorp.com"
    assert data["tenant_id"] == sample_tenant.id


def test_create_tenant_user_duplicate_email(client, admin_headers, sample_tenant, sample_user):
    """Test creating user with duplicate email"""
    user_data = {
        "email": sample_user.email,  # Use existing email
        "first_name": "Another",
        "last_name": "User",
        "department": "Marketing",
        "roles": ["employee"]
    }
    
    response = client.post(
        f"/api/v1/tenants/{sample_tenant.id}/users",
        json=user_data,
        headers=admin_headers
    )
    
    assert response.status_code == 400
    assert "Email already exists" in response.json()["detail"]


def test_get_tenant_user(client, admin_headers, sample_tenant, sample_user):
    """Test getting specific user for a tenant"""
    response = client.get(
        f"/api/v1/tenants/{sample_tenant.id}/users/{sample_user.id}",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_user.id
    assert data["email"] == sample_user.email


def test_update_tenant_user(client, admin_headers, sample_tenant, sample_user):
    """Test updating user for a tenant"""
    update_data = {
        "first_name": "Updated",
        "department": "Engineering"
    }
    
    response = client.put(
        f"/api/v1/tenants/{sample_tenant.id}/users/{sample_user.id}",
        json=update_data,
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Updated"
    assert data["department"] == "Engineering"


def test_delete_tenant_user(client, admin_headers, sample_tenant, sample_user):
    """Test deleting user for a tenant"""
    response = client.delete(
        f"/api/v1/tenants/{sample_tenant.id}/users/{sample_user.id}",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted successfully"


def test_get_tenant_audit_logs(client, admin_headers, sample_tenant):
    """Test getting audit logs for a tenant"""
    response = client.get(
        f"/api/v1/tenants/{sample_tenant.id}/audit-logs",
        headers=admin_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_unauthorized_access(client, sample_tenant):
    """Test unauthorized access to tenant endpoints"""
    # Test without authentication
    response = client.get(f"/api/v1/tenants/{sample_tenant.id}")
    assert response.status_code == 401
    
    # Test without proper headers
    response = client.get(
        f"/api/v1/tenants/{sample_tenant.id}",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code in [401, 403] 