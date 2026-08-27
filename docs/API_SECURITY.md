# Jafar API authentication

## Public endpoint

`GET /health` is intentionally unauthenticated so local and external liveness checks can reach the service.

## Protected endpoints

Application endpoints under `/v1/*` require the `X-Jafar-API-Key` header by default in every
environment.

```http
X-Jafar-API-Key: <secret>
```

The key is supplied through the `API_KEY` environment variable and must never be committed to Git.

### Failure modes

- Development + no key configured: `503` by default.
- Development + `ALLOW_UNAUTHENTICATED_DEVELOPMENT=true` + no key: requests are allowed only as an
  explicit local developer opt-in; never use this setting for Private Beta or a network listener.
- Non-development + no key configured: `503` because the service is misconfigured and fails closed.
- Configured key + missing/wrong header: `401`.
- Correct header: request proceeds to existing workflow and human-approval boundaries.

The comparison uses `hmac.compare_digest` to avoid a straightforward timing side channel.

## Apple client contract

`RemoteCommandClient` uses the same `X-Jafar-API-Key` header. The key must be supplied at runtime from secure configuration. Do not place it in Swift source, `Info.plist`, GitHub, or test fixtures.
