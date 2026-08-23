# CONSOLIDATION security baseline

This document records security invariants verified during the CONSOLIDATION phase.

## Supabase

- RLS is enabled on legal and operational tables exposed through `public`.
- Service/worker tables must not be reachable by `anon` or `authenticated` roles unless an explicit policy is documented.
- `SECURITY DEFINER` RPCs are privileged backend operations; their `EXECUTE` grants must be reviewed explicitly.
- Search paths of privileged database functions must be fixed rather than role-mutable.
- Legal audit records must remain append-only from application clients.

## Application

- External/legal actions remain behind explicit approval gates.
- Telegram responses pass through the response safety gate before outbound delivery.
- Multimodel verification is fail-closed when independent verification is requested but unavailable.
- Runtime model fallback is observable in the routing metadata.
- Incoming documents and messages are treated as untrusted input.

## Policy design rule

Do not add broad RLS policies merely to silence the Supabase linter. Policies must be derived from the eventual authenticated-user/tenant ownership model. Until that model is finalized, backend service-role access remains the intended path for these internal tables.
