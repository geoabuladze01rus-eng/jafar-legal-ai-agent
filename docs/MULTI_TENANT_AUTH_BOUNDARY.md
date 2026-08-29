# Multi-tenant authentication boundary before commercial rollout

## Current Private Beta posture

The production backend is **single-tenant by configuration**. Supabase repositories and
the AI queue/rate-limit/cost paths obtain `JAFAR_SUPABASE_OWNER_USER_ID` from server
configuration. Client request fields are not accepted as an authority for ownership.
This is appropriate only for a controlled Private Beta with one explicitly designated
owner and a restricted set of invited operators.

Do not describe this deployment as multi-tenant. A second customer must not be onboarded
by changing a request field or sharing the same owner configuration.

## Boundary before commercial rollout

Before commercial or multi-customer rollout, replace the global owner configuration with
authenticated tenant identity propagated from the server-validated session/JWT and enforce
that identity consistently in matters, approvals, AI jobs, reservations, cost ledger,
reconciliation, rate limits, and document state. Add tenant membership/role checks,
cross-tenant negative tests, migration/backfill rules, and an operational tenant-offboarding
plan. Review all service-role RPCs and storage policies as part of that change.

## Beta controls

- Keep one `JAFAR_SUPABASE_OWNER_USER_ID` per deployment.
- Keep `ENVIRONMENT=production`, a non-placeholder `API_KEY`, and a fixed
  `LAWYER_APPROVER_ID` in the secret store.
- Provision no second customer against the same production owner until the boundary work
  is complete and reviewed.
- Treat this document as a release gate for any commercial rollout.
