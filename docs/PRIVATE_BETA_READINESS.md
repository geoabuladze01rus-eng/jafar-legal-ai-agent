# Private Beta release checklist

This checklist is the operational handoff for a controlled, single-tenant Private Beta.
It contains no credentials. Complete every required item before inviting a user.

## Required configuration

- [ ] `ENVIRONMENT=production`; set a useful `LOG_LEVEL`.
- [ ] Generate a random `API_KEY` of at least 24 characters; do not use placeholders.
- [ ] Set the server-only `LAWYER_APPROVER_ID` and verify it is not client-editable.
- [ ] Set `STORAGE_BACKEND=supabase`.
- [ ] Set `JAFAR_SUPABASE_URL`, `JAFAR_SUPABASE_SERVICE_ROLE_KEY`, and the controlled
      `JAFAR_SUPABASE_OWNER_USER_ID`; keep service-role material backend-only.
- [ ] Apply and verify all migrations in `supabase/migrations/` in order.
- [ ] Set `AI_QUEUE_BACKEND=supabase` and verify the worker can atomically claim jobs.
- [ ] Enable cost control and provide reviewed `AI_PRICING_JSON`, `AI_PRICING_VERSION`,
      and request/user/matter/global ceilings.
- [ ] Configure only approved provider keys, model names, endpoints, and
      `AI_TRUSTED_PROVIDER_HOSTS`; leave unapproved providers unset.
- [ ] Provision the private document bucket and agree `DOCUMENT_RETENTION_DAYS` plus a
      tested deletion/hold procedure.
- [ ] Configure the Apple `JAFAR_API_BASE_URL`/bundle settings. Never embed a Supabase
      service-role key or backend API key in the app; user API tokens remain Keychain-backed.

## Security and data controls

- [ ] Confirm the deployment is single-tenant per
      [the authentication boundary](MULTI_TENANT_AUTH_BOUNDARY.md).
- [ ] Confirm `/v1/*` rejects missing, malformed, and placeholder bearer credentials.
- [ ] Verify owner-scoped reads/writes and negative cross-owner tests for matters,
      approvals, jobs, reservations, cost, reconciliation, rate limits, and documents.
- [ ] Verify approval payload fingerprints, server-side approver identity, one-time claim,
      idempotent settlement, and uncertain external-side-effect reconciliation.
- [ ] Verify document upload limits, private storage, provenance, extraction-failure paths,
      and no automatic persistence of legal facts.
- [ ] Verify Apple local authentication and fail-closed behavior for backend failures;
      keep Telegram/external sends in dry-run until separately approved.
- [ ] Review Supabase RLS, grants, RPC search paths, immutable ledgers, and service-role
      execution after migrations are applied.

## Evidence to attach to the release record

- [ ] `pytest -q`, Ruff, `compileall`, Python gate, and Apple iOS/macOS gate are green.
- [ ] Dependency and secret scans are clean; no skipped/xfail release tests are unexplained.
- [ ] Record migration status, bucket/retention settings, provider pricing version,
      configured owner, approver, and rollback contact without recording secret values.
- [ ] Record the known CI `startup_failure` as infrastructure follow-up; it is separate
      from application readiness.
