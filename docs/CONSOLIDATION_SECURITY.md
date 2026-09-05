# CONSOLIDATION security baseline

This document records security invariants verified during the CONSOLIDATION phase.

## Supabase

- RLS is enabled on legal and operational tables exposed through `public`.
- Service/worker tables must not be reachable by `anon` or `authenticated` roles unless an explicit policy is documented.
- `SECURITY DEFINER` RPCs are privileged backend operations; their `EXECUTE` grants must be reviewed explicitly.
- Search paths of privileged database functions must be fixed rather than role-mutable.
- Legal audit records must remain append-only from application clients.
- Matter RAG retrieval is service-role only and checks both `matter_id` and owner identity.
- Google OAuth token RPCs are service-role only; token values are encrypted at rest.

## Application

- External/legal actions remain behind explicit approval gates.
- Telegram responses pass through the response safety gate before outbound delivery.
- Multimodel verification is fail-closed when independent verification is requested but unavailable.
- Runtime model fallback is observable in the routing metadata.
- Incoming documents and messages are treated as untrusted input.
- Confidential legal analysis routes to the local Ollama provider unless cloud fallback is explicitly enabled.
- Matter research rejects cross-Matter retrieval rows and rejects missing or hallucinated document/page/chunk citation tokens.
- OCR-only case facts are not authoritative until corroborated by a verified source; source conflicts remain visible with provenance.
- HTTP API authentication may be optional in local development, but `/v1/*` fails closed in `staging` and `production` when `JAFAR_API_BEARER_TOKEN` is absent.
- The Google OAuth callback is the only `/v1` authentication exemption and remains protected by the OAuth state validation flow.
- Configured Google OAuth in staging/production requires persistent encrypted Supabase token storage; it must not silently fall back to an in-memory token store.
- Google OAuth and Workspace token lookup in staging/production use a server-bound subject; API callers cannot select another token-store subject.
- Internal document Edge workers accept only a dedicated `JAFAR_WORKER_SECRET` of at least 32 characters. The same value must be provisioned as the Supabase Vault secret `jafar_worker_secret`; publishable/anon and service-role API keys are not worker credentials.
- OpenAI-backed document workers, legal research, memory embeddings and direct analysis remain disabled until deployment explicitly sets `CONFIDENTIAL_CLOUD_FALLBACK=true`. Enabling it is an operational consent decision, not a default.

## Deployment constraint

The current one-time Google OAuth state store is process-local. Until a shared atomic OAuth state store is implemented, the supported OAuth deployment topology is a single application instance. Do not horizontally scale the OAuth broker behind a load balancer and assume replay protection is shared across instances.

## Release review rule

A release candidate must demonstrate Python CI, iOS/macOS build, Ollama regression, Matter RAG E2E, provenance acceptance, and production-auth tests on the consolidation lineage before PR #56 is considered for merge to `main`.

## Policy design rule

Do not add broad RLS policies merely to silence the Supabase linter. Policies must be derived from the eventual authenticated-user/tenant ownership model. Until that model is finalized, backend service-role access remains the intended path for these internal tables.
