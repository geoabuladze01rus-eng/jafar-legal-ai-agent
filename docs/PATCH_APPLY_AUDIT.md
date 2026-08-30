# Explicit Patch Apply, Audit Ledger and Rollback

This layer is the only controlled mutation boundary after a lawyer-approved fragment proposal.

## Flow

1. A reviewed proposal passes legal/source gates.
2. A lawyer creates an immutable approval record.
3. A controlled patch is prepared for one exact fragment ID.
4. An explicit apply operation checks the current fragment hash again.
5. The operation returns a new fragment snapshot and appends a hash-chained audit entry.
6. The new full-text version is stored as an immutable `FragmentVersion`.
7. Rollback is a separate explicit operation and creates another version plus another audit entry.

There is no automatic patch application.

## Audit / text separation

`PatchAuditLedger` intentionally stores no raw legal-document body. It records:

- patch ID;
- approval ID;
- fragment/work-product IDs;
- before/after text hashes;
- actor;
- timestamp;
- authority/rule IDs;
- previous audit hash;
- related apply entry for rollback.

The ledger is append-only and hash-chained. `verify_chain()` detects modified or reordered entries.

Full legal text is retained in `FragmentVersionStore`, which is a storage contract and must use privileged/confidential deployment storage in production.

## Apply gates

A patch cannot be applied when:

- `may_auto_apply=True`;
- it is not marked `ready_for_explicit_apply`;
- fragment ID or work-product ID differs;
- the current fragment hash differs from the approved original hash;
- the replacement hash is invalid;
- the applying actor is missing;
- the timestamp is not timezone-aware.

## Version history

The version store preserves every state:

- version 1: initial/seed text;
- version 2: explicitly applied lawyer-approved text;
- version 3+: later approved edits or rollback states.

Rollback never deletes the applied version.

## Rollback gates

Rollback requires:

- the exact apply audit entry;
- the same patch and fragment;
- the fragment to still equal the text produced by that apply entry;
- the exact original text bound to the patch;
- an identified rollback actor.

If the fragment was edited after patch application, rollback is blocked so it cannot overwrite later work.

## Safety invariant

Approval authorizes preparation and explicit controlled application of one bound patch. It does not authorize autonomous mutation of other fragments, documents, filings or external systems.
