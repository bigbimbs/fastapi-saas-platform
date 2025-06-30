from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextvars import ContextVar
from typing import Optional
from .config import settings

tenant_context: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)

engine = create_engine(
    settings.database_url,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
metadata = MetaData()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant_id() -> Optional[str]:
    return tenant_context.get()


def set_tenant_id(tenant_id: str):
    tenant_context.set(tenant_id)


def clear_tenant_id():
    tenant_context.set(None) 