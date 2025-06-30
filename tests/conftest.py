import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.models import Tenant, User
from app.schemas import UserRole, PlanType
import os

# Use SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    
    with TestClient(app) as test_client:
        yield test_client
    
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_tenant(db_session):
    tenant = Tenant(
        id="tenant_001",
        name="Test Corp",
        domain="testcorp.com",
        plan=PlanType.ENTERPRISE,
        employee_count=100,
        is_active=True
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def sample_user(db_session, sample_tenant):
    user = User(
        id="user_001",
        tenant_id=sample_tenant.id,
        email="test@testcorp.com",
        first_name="Test",
        last_name="User",
        department="Engineering",
        roles=[UserRole.ADMIN],
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(client, sample_tenant, sample_user):
    return {
        "Authorization": f"Bearer demo_token_{sample_user.id}",
        "X-Tenant-ID": sample_tenant.id
    }


@pytest.fixture
def manager_headers(client, sample_tenant):
    return {
        "Authorization": "Bearer demo_token_manager",
        "X-Tenant-ID": sample_tenant.id
    } 