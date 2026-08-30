# Staging deployment rehearsal

## Topology

```text
Apple app
    ↓ HTTPS
Staging backend/API (stateless Python 3.x)
    ↓ service-side access only
Staging Supabase project
    ↓ private bucket
Private document storage

Backend ── HTTPS ──> OpenAI / explicitly trusted AI providers
```

The Apple client is public-facing and stores only the backend URL plus a user-entered
Keychain token. Supabase service-role credentials, provider API keys, owner ID, approval
identity, pricing and budget controls live in the staging secret store. The staging
deployment is controlled single-tenant (`PRIVATE BETA = SINGLE TENANT`).

## Staging creation (owner action)

- [ ] Create a separate Supabase staging project; do not point rehearsal commands at production.
- [ ] Record the staging project URL and environment label in the deployment system.
- [ ] Provision a private `jafar-legal-documents` bucket with no anonymous listing/public URLs.
- [ ] Create one dedicated staging owner UUID and one server-side `LAWYER_APPROVER_ID`.
- [ ] Inject values from `.env.private-beta.example`; never commit populated files.
- [ ] Configure HTTPS reverse proxy/platform, health probes, secret injection and Python 3.11+.

## Migration rehearsal (staging only)

1. Take a staging snapshot/backup.
2. Apply the 27 timestamped migrations in `supabase/migrations/` in lexical order.
3. Verify tables, indexes, functions/RPC signatures and extension prerequisites.
4. Verify RLS on all critical tables and inspect `SECURITY DEFINER` functions for fixed
   `search_path` and restricted grants.
5. Verify service-role-only grants for queue, cost, reconciliation and worker RPCs.
6. Run the read-only verifier and synthetic smoke flow; retain evidence with no secrets.

The migration set contains intentional function replacement (`DROP FUNCTION IF EXISTS`) in
owner-scoping migrations. It has no destructive table drops, but must still be rehearsed
against a disposable staging project first.

## Verification commands

```bash
ENVIRONMENT=staging STAGING_VERIFY_LIVE=true \
  python -m scripts.verify_staging
pytest -m staging_smoke -q   # opt-in suite, when staging credentials are supplied
```

`python -m scripts.verify_staging` performs no mutations, provider calls, sends, deletions,
or RPC execution. Live mode uses only Supabase metadata GETs; RLS confirmation is an explicit
operator check from SQL metadata, not inferred from an application response. Without staging
credentials, the verifier is intentionally expected to fail configuration checks.

## Smoke flow (synthetic fixtures only)

- [ ] `GET /health` returns process liveness; `/ready` is not currently implemented, so use
      deployment-level config verification before advertising readiness.
- [ ] Authenticated `GET /v1/dashboard` succeeds for the staging owner only.
- [ ] Create/list/read a synthetic matter; attempt a client owner override and verify it is
      ignored/rejected.
- [ ] Upload a harmless synthetic PDF/text fixture; verify analysis stays read-only and
      returns `persisted=false` and `requires_approval_to_persist=true`.
- [ ] Create a mock/internal action and verify `PROPOSED → APPROVED`; do not invoke an
      external handler.
- [ ] Verify reservation, budget block and cost projection with provider calls mocked/faked.

## Apple/TestFlight staging

- [ ] Use the existing generated project from `apple/project.yml` with a staging base URL
      supplied by build configuration or `JAFAR_API_BASE_URL`; do not bake production URLs.
- [ ] Confirm display name `ЮСТИЦИЯ AI`, bundle `ru.jafar.legal-ai`, privacy strings,
      Release configuration, version/build number and app icon in the archive review.
- [ ] Do not place API keys, Supabase service-role material or provider secrets in xcconfig,
      Info.plist, the app bundle or source control.
- [ ] A static backend bearer token is acceptable only for this controlled single-user beta;
      it is a blocker for commercial multi-user release until tenant authentication exists.

## Platform-neutral deployment contract

Python 3.11+, HTTPS reverse proxy/platform, injected environment secrets, external persistent
Supabase database/storage, stateless API instances, explicit `uvicorn` start command, and
platform health probes. No cloud provider is selected by this rehearsal.
