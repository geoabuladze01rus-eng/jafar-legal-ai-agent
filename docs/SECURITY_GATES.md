# Jafar security gates

This document defines review gates for security-sensitive database changes. Jafar processes
confidential legal-practice data, so database hardening remains fail-closed and staging-first.

## Current review finding

A prior read-only production audit found broad object privileges on multiple `public` tables for
`anon` and `authenticated`, including `TRUNCATE`. Row Level Security does not protect `TRUNCATE`,
so that privilege is inappropriate for client-facing roles.

## Candidate hardening

`20260825014000_revoke_public_truncate_from_client_roles.sql`:

1. revokes `TRUNCATE` on existing `public` tables from `anon` and `authenticated`;
2. revokes it from default table privileges for future tables created by the migration role.

It does not change ordinary CRUD grants or `service_role`. The migration is tracked for review but
must not be applied to production from this branch.

## Required validation before any production use

- [ ] Parse and apply in a disposable/local or isolated staging database.
- [ ] Verify `anon` and `authenticated` cannot `TRUNCATE` any `public` table.
- [ ] Verify intended authenticated CRUD workflows still pass through RLS policies.
- [ ] Verify document-worker tables remain usable by `service_role`.
- [ ] Review authenticated RPC ownership checks and fixed `search_path` settings.
- [ ] Confirm the diff contains no production identifiers, credentials, Vault values, or client data.

Production deployment requires a separate explicit owner decision after these checks pass.
