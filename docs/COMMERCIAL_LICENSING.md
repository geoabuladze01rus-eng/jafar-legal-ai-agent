# Commercial licensing architecture (design only)

Licensing metadata must remain separate from Matters, documents, evidence, provenance, and legal analysis. No legal document or case fact is required to activate a license.

## Proposed boundary

- The app creates a device installation identifier in Keychain.
- A future licensing service exchanges that identifier plus an account/license token for a signed entitlement document.
- The entitlement contains product, plan, seat/device binding, issued/expiry timestamps, and a key identifier; it contains no legal content.
- The app verifies the entitlement signature locally and keeps a short offline grace period for already activated installations.
- Revocation is checked when connectivity is available, with explicit user-facing state for expired or revoked licenses.
- Subscription state is account/license metadata only and never joins the Matter or evidence data model.

## Privacy and failure behavior

Activation should require the minimum account and device metadata, disclose the retention policy, and support deletion. Offline use continues during the documented grace period; after expiry, read-only local diagnostics remain available while licensed actions are blocked. No confidential document is uploaded as proof of ownership.

No licensing server or payment integration is deployed in this task.
