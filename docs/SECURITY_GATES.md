# JAFAR Security Gates

This document defines review gates for security-sensitive database changes. It is intentionally conservative because JAFAR processes confidential legal-practice data.

## Current review finding

A read-only production audit found that multiple `public` tables grant broad object privileges to `anon` / `authenticated`, including `TRUNCATE`. Row Level Security does not protect `TRUNCATE`, so this privilege is inappropriate for client-facing roles in JAFAR.

## Candidate hardening

Migration candidate:

`20260825014000_revoke_public_truncate_from_client_roles.sql`

It does two things only:

1. Revokes `TRUNCATE` on all existing tables in `public` from `anon` and `authenticated`.
2. Revokes `TRUNCATE` from default table privileges in `public` for future tables created by the migration role.

It does **not** revoke ordinary `SELECT` / `INSERT` / `UPDATE` / `DELETE` permissions and does not alter `service_role`.

## Required checks before merge

- [ ] Parse migration successfully with PostgreSQL tooling.
- [ ] Apply on disposable/local or staging database only.
- [ ] Verify `anon` cannot `TRUNCATE` any `public` table.
- [ ] Verify `authenticated` cannot `TRUNCATE` any `public` table.
- [ ] Verify intended authenticated CRUD workflows still work through RLS policies.
- [ ] Verify document worker tables remain usable by `service_role`.
- [ ] Verify `record_document_event` and other authenticated RPCs still enforce ownership.
- [ ] Verify no production UUIDs, credentials, Vault values or client data are present in the diff.

## Production gate

Do not apply this migration directly to production from an untested branch. Production deployment requires a separate explicit decision after local/staging verification.
