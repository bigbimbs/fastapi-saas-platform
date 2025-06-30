# Multi-Tenant SaaS Platform with External Integrations

A comprehensive FastAPI-based multi-tenant SaaS platform that combines platform engineering with external API integration capabilities.

## Features

### Part A: Multi-Tenant Platform (60% of assessment)

- ✅ **Multi-tenant data isolation** using database-level security
- ✅ **JWT-based authentication** with role management
- ✅ **RESTful API endpoints** for user and organization operations
- ✅ **Audit logging** for all data modifications
- ✅ **API rate limiting** and input validation

### Part B: External Integration Engine (40% of assessment)

- ✅ **Webhook processing** from multiple external services
- ✅ **Async event handling** with retry logic and failure recovery
- ✅ **External API calls** with proper error handling
- ✅ **Data synchronization** between external services and internal data
- ✅ **Integration health monitoring** and status tracking

### Advanced Features (Bonus)

- ✅ **SSO Integration**: Basic SAML/OIDC authentication flow
- ✅ **Bulk Operations**: Handle batch webhook events efficiently
- ✅ **Idempotency**: Ensure duplicate webhook processing is handled gracefully
- ✅ **Circuit Breaker**: Implement circuit breaker pattern for external API calls

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   PostgreSQL    │    │     Redis       │
│                 │    │   (Multi-tenant │    │   (Rate Limiting│
│  - Auth         │◄──►│    Database)    │    │   & Caching)    │
│  - Tenants      │    │                 │    │                 │
│  - Webhooks     │    └─────────────────┘    └─────────────────┘
└─────────────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  User Service   │    │ Payment Service │    │Communication   │
│  (External)     │    │  (External)     │    │Service (External│
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL (or SQLite for development)
- Redis (optional, for production)

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd fastapi-saas-platform
```

2. **Create virtual environment**

```bash
python -m venv venv
source venv/bin/activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Set up environment variables**

```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize database**

```bash
# The app will create tables automatically on startup
# For production, use Alembic migrations
```

6. **Run the application**

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- **API Documentation**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Authentication

- `POST /api/v1/auth/login` - Login with email/password
- `POST /api/v1/auth/sso/login` - Login with SSO
- `GET /api/v1/auth/me` - Get current user info
- `POST /api/v1/auth/logout` - Logout

### Tenants

- `POST /api/v1/tenants/` - Create tenant (admin only)
- `GET /api/v1/tenants/` - List tenants (admin only)
- `GET /api/v1/tenants/{tenant_id}` - Get tenant (admin only)
- `PUT /api/v1/tenants/{tenant_id}` - Update tenant (admin only)
- `DELETE /api/v1/tenants/{tenant_id}` - Delete tenant (admin only)

### Users (Tenant-scoped)

- `GET /api/v1/tenants/{tenant_id}/users` - List users
- `POST /api/v1/tenants/{tenant_id}/users` - Create user
- `GET /api/v1/tenants/{tenant_id}/users/{user_id}` - Get user
- `PUT /api/v1/tenants/{tenant_id}/users/{user_id}` - Update user
- `DELETE /api/v1/tenants/{tenant_id}/users/{user_id}` - Delete user

### Webhooks

- `POST /api/v1/webhooks/user-service` - User service webhook
- `POST /api/v1/webhooks/payment-service` - Payment service webhook
- `POST /api/v1/webhooks/communication-service` - Communication service webhook
- `GET /api/v1/webhooks/events` - List webhook events
- `GET /api/v1/webhooks/health` - Check integration health

## Multi-Tenant Architecture

### Tenant Isolation

- **Database-level isolation**: Each query is filtered by tenant_id
- **Context-based routing**: Tenant context is set via headers or domain
- **Role-based access**: Users can only access their tenant's data

### Tenant Resolution

1. **Header-based**: `X-Tenant-ID: tenant_001`
2. **Domain-based**: `tenant-001.yourdomain.com`
3. **Subdomain-based**: `tenant001.app.com`

## External Integrations

### Supported Services

- **User Management Service**: User CRUD operations
- **Payment Service**: Subscription and billing events
- **Communication Service**: Email/notification delivery status

### Integration Features

- **Circuit Breaker**: Prevents cascade failures
- **Retry Logic**: Exponential backoff with jitter
- **Health Monitoring**: Real-time service status
- **Webhook Processing**: Async event handling
- **Idempotency**: Duplicate event handling

## Security Features

### Authentication & Authorization

- JWT-based authentication
- Role-based access control (RBAC)
- SSO integration (Azure AD, Okta)
- Token expiration and refresh

### Data Protection

- Input validation and sanitization
- SQL injection prevention
- XSS protection headers
- Rate limiting per tenant

### Audit Logging

- All data modifications logged
- User action tracking
- IP address and user agent logging
- Immutable audit trail

## Testing

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

### Test Structure

```
tests/
├── test_auth.py          # Authentication tests
├── test_tenants.py       # Tenant management tests
├── test_webhooks.py      # Webhook processing tests
├── test_integrations.py  # External service tests
└── conftest.py          # Test configuration
```

## Monitoring & Observability

### Health Checks

- `/health` - Application health
- `/metrics` - Prometheus metrics
- `/webhooks/health` - Integration health

### Logging

- Structured logging with JSON format
- Request/response logging
- Error tracking and alerting
- Performance metrics

### Metrics

- Request rate and latency
- Error rates and types
- Tenant usage statistics
- Integration health status

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:

- Create an issue in the repository
- Check the documentation at `/docs`
- Review the API specification at `/redoc`
