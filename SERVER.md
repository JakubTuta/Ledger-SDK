# Ledger Server Information

## Server URLs

- **Production Server**: https://ledger-server.jtuta.cloud
- **Local Development**: http://localhost:8000

## Quick Start

### 1. Register an Account

```bash
curl -X POST https://ledger-server.jtuta.cloud/api/v1/accounts/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123",
    "name": "Your Name"
  }'
```

Response includes an `access_token` for immediate use.

### 2. Create a Project

```bash
curl -X POST https://ledger-server.jtuta.cloud/api/v1/projects \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My App",
    "slug": "my-app",
    "environment": "production"
  }'
```

### 3. Create an API Key

```bash
curl -X POST https://ledger-server.jtuta.cloud/api/v1/projects/{project_id}/api-keys \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key"
  }'
```

**Important**: Save the `full_key` immediately - it won't be shown again!

### 4. Use the SDK

```python
from ledger import LedgerClient

client = LedgerClient(
    api_key="ldg_proj_1_your_api_key",
    base_url="https://ledger-server.jtuta.cloud"
)

client.log_info("Application started", attributes={"version": "1.0.0"})
```

## API Endpoints

### Authentication
- `POST /api/v1/accounts/register` - Create account
- `POST /api/v1/accounts/login` - Login
- `POST /api/v1/accounts/logout` - Logout
- `GET /api/v1/accounts/me` - Get current account

### Projects
- `POST /api/v1/projects` - Create project
- `GET /api/v1/projects` - List projects
- `GET /api/v1/projects/{slug}` - Get project by slug

### API Keys
- `POST /api/v1/projects/{project_id}/api-keys` - Create API key
- `DELETE /api/v1/api-keys/{key_id}` - Revoke API key

### Log Ingestion
- `POST /api/v1/ingest/single` - Ingest single log
- `POST /api/v1/ingest/batch` - Ingest batch logs (up to 1,000)
- `GET /api/v1/queue/depth` - Get queue depth

## Rate Limits

- **Per-Minute**: 1,000 requests
- **Per-Hour**: 50,000 requests

Rate limits are enforced per API key.

## Resources

- **Server Repository**: https://github.com/JakubTuta/Ledger-APP
- **SDK Repository**: https://github.com/JakubTuta/Ledger-SDK
- **Frontend Repository**: https://github.com/JakubTuta/Ledger-WEB
- **PyPI Package**: https://pypi.org/project/ledger-sdk/
- **Production Server**: https://ledger-server.jtuta.cloud
- **Frontend Dashboard**: https://ledger.jtuta.cloud
