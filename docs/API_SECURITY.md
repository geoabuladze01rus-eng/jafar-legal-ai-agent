# Jafar API authentication

## Public endpoint

`GET /health` is intentionally unauthenticated so uptime and liveness checks can reach the service.

## Protected endpoints

Application endpoints under `/v1/*` require the `X-Jafar-API-Key` header outside development.

```http
X-Jafar-API-Key: <secret>
```

The key is supplied through the `API_KEY` environment variable and must never be committed to Git.

### Failure modes

- Development + no key configured: local requests are allowed.
- Non-development + no key configured: `503` because the service is misconfigured.
- Configured key + missing/wrong header: `401`.
- Correct header: request proceeds to the existing workflow and approval boundaries.

The comparison uses constant-time `hmac.compare_digest` to avoid a straightforward timing side channel.
