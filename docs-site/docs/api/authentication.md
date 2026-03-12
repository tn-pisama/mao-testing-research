# Authentication

PISAMA supports multiple authentication methods depending on your integration type.

## Authentication Methods

| Method | Usage | Best For |
|---|---|---|
| API Key + Token Exchange | SDK and CLI integrations | Programmatic access |
| Google OAuth | Dashboard users | Browser-based access |
| JWT Bearer | Programmatic access | API calls after token exchange |
| Webhook Signatures | Clerk, Stripe, n8n | Webhook verification |

## API Key Authentication

### Create a Tenant

Create a tenant to get an API key:

```bash
curl -X POST http://localhost:8000/api/v1/auth/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project"}'
```

Response:

```json
{
  "id": "tenant-uuid",
  "name": "my-project",
  "api_key": "mao_key_..."
}
```

### Exchange API Key for JWT

Use the API key to obtain a JWT bearer token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "mao_key_..."}'
```

Response:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### Use the JWT Token

Include the token in the `Authorization` header:

```bash
curl http://localhost:8000/api/v1/tenants/TENANT_ID/traces \
  -H "Authorization: Bearer eyJ..."
```

## API Key Management

### List API Keys

```bash
curl http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer $TOKEN"
```

### Create a New API Key

```bash
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer $TOKEN"
```

### Revoke an API Key

```bash
curl -X DELETE http://localhost:8000/api/v1/auth/api-keys/KEY_ID \
  -H "Authorization: Bearer $TOKEN"
```

## Direct API Key Header

For webhook endpoints and simple integrations, you can use the API key directly in the `X-MAO-API-Key` header:

```bash
curl -X POST http://localhost:8000/api/v1/n8n/webhook \
  -H "X-MAO-API-Key: mao_key_..." \
  -H "Content-Type: application/json" \
  -d '{"executionId": "123", ...}'
```

## Google OAuth (Dashboard)

The PISAMA dashboard uses Google OAuth via NextAuth for browser-based authentication. Users sign in with their Google account and are automatically associated with their organization's tenant.

### Configuration

Set these environment variables for OAuth:

**Backend:**

```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

**Frontend:**

```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
NEXTAUTH_SECRET=<openssl rand -base64 32>
NEXTAUTH_URL=https://your-app.com
```

## Webhook Signature Verification

Inbound webhooks from n8n, Stripe, and Clerk are verified using signature headers:

### n8n Webhooks

| Header | Purpose |
|---|---|
| `X-MAO-Signature` | HMAC-SHA256 signature of the payload |
| `X-MAO-Timestamp` | Unix timestamp (must be within 5 minutes) |
| `X-MAO-Nonce` | Unique nonce to prevent replay attacks |

### Stripe Webhooks

Verified using the `stripe-signature` header and `STRIPE_WEBHOOK_SECRET`.

### Clerk Webhooks

Verified via Svix signature.

## Current User

Get the current authenticated user's profile:

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

## Security Best Practices

1. **Rotate API keys periodically** -- Use the API key management endpoints to create new keys and revoke old ones
2. **Use HTTPS in production** -- Never send API keys or tokens over unencrypted connections
3. **Store secrets securely** -- Never commit API keys to version control
4. **Use short-lived JWTs** -- Exchange API keys for JWTs for each session rather than reusing tokens
5. **Validate webhook signatures** -- Always verify inbound webhook signatures to prevent spoofing
