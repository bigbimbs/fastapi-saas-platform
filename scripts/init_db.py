#!/usr/bin/env python3
"""
Database initialization script with sample data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal
from app.models import Base, Tenant, User
from app.schemas import UserRole, PlanType
import json

def init_database():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        if db.query(Tenant).first():
            print("Database already contains data. Skipping initialization.")
            return
        
        tenants_data = [
            {
                "id": "tenant_001",
                "name": "TechCorp Inc",
                "domain": "techcorp.com",
                "plan": PlanType.ENTERPRISE,
                "employee_count": 1200,
                "sso_config": {
                    "provider": "azure_ad",
                    "tenant_id": "12345678-1234-1234-1234-123456789012",
                    "client_id": "87654321-4321-4321-4321-210987654321",
                    "domain": "techcorp.onmicrosoft.com",
                    "attribute_mappings": {
                        "email": "mail",
                        "first_name": "givenName",
                        "last_name": "surname",
                        "department": "department",
                        "manager": "manager"
                    },
                    "role_mappings": {
                        "IT Admin": ["it-admin"],
                        "Manager": ["manager", "team-lead"],
                        "Employee": ["employee"]
                    }
                }
            },
            {
                "id": "tenant_002",
                "name": "StartupXYZ",
                "domain": "startupxyz.com",
                "plan": PlanType.PREMIUM,
                "employee_count": 150,
                "sso_config": {
                    "provider": "okta",
                    "domain": "startupxyz.okta.com",
                    "client_id": "okta_client_123",
                    "attribute_mappings": {
                        "email": "email",
                        "first_name": "firstName",
                        "last_name": "lastName",
                        "department": "department"
                    },
                    "role_mappings": {
                        "Admin": ["admin"],
                        "User": ["user"]
                    }
                }
            }
        ]
        
        for tenant_data in tenants_data:
            tenant = Tenant(**tenant_data)
            db.add(tenant)
        
        db.commit()
        
        users_data = [
            {
                "id": "user_001",
                "tenant_id": "tenant_001",
                "email": "john.doe@techcorp.com",
                "first_name": "John",
                "last_name": "Doe",
                "department": "Engineering",
                "roles": [UserRole.EMPLOYEE],
                "sso_attributes": {
                    "azure_ad_object_id": "11111111-2222-3333-4444-555555555555",
                    "manager": "jane.smith@techcorp.com"
                }
            },
            {
                "id": "user_002",
                "tenant_id": "tenant_001",
                "email": "jane.smith@techcorp.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "department": "Engineering",
                "roles": [UserRole.MANAGER, UserRole.EMPLOYEE],
                "sso_attributes": {
                    "azure_ad_object_id": "22222222-3333-4444-5555-666666666666"
                }
            },
            {
                "id": "user_003",
                "tenant_id": "tenant_001",
                "email": "admin@techcorp.com",
                "first_name": "Admin",
                "last_name": "User",
                "department": "IT",
                "roles": [UserRole.ADMIN, UserRole.IT_ADMIN],
                "sso_attributes": {
                    "azure_ad_object_id": "33333333-4444-5555-6666-777777777777"
                }
            },
            {
                "id": "user_004",
                "tenant_id": "tenant_002",
                "email": "alice@startupxyz.com",
                "first_name": "Alice",
                "last_name": "Johnson",
                "department": "Product",
                "roles": [UserRole.ADMIN],
                "sso_attributes": {
                    "okta_user_id": "okta_user_123"
                }
            }
        ]
        
        for user_data in users_data:
            user = User(**user_data)
            db.add(user)
        
        db.commit()
        
        print("Database initialized successfully!")
        print(f"Created {len(tenants_data)} tenants and {len(users_data)} users")
        
        print("\nSample login credentials:")
        print("Tenant: tenant_001 (TechCorp Inc)")
        print("  - Email: john.doe@techcorp.com")
        print("  - Password: password123")
        print("  - Role: Employee")
        print()
        print("Tenant: tenant_001 (TechCorp Inc)")
        print("  - Email: admin@techcorp.com")
        print("  - Password: password123")
        print("  - Role: Admin")
        print()
        print("Tenant: tenant_002 (StartupXYZ)")
        print("  - Email: alice@startupxyz.com")
        print("  - Password: password123")
        print("  - Role: Admin")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_database() 