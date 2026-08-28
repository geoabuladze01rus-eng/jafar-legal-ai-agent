# Lawyer Approval + Controlled Patch

This layer separates legal approval from document mutation.

## Flow

1. A reviewed redraft proposal passes authority and source-reference gates.
2. A lawyer explicitly approves one exact proposal.
3. The system creates an immutable `LawyerApprovalRecord` bound to a proposal hash.
4. The engine may prepare a `ControlledFragmentPatch` only if the current fragment still exactly matches the proposal's original text.
5. The patch may be offered for a separate explicit apply operation.

## Safety invariants

- Approval is bound to fragment ID, proposed text, authorities, rules and proposal style through a stable hash.
- Any proposal modification after approval invalidates the approval.
- Any source-fragment modification after proposal generation blocks patch creation and requires re-review.
- `may_auto_apply` is always false.
- `ready_for_explicit_apply` means only that the patch passed integrity gates; it does not mutate a document.
- Lawyer identity is required for approval.
- Approval timestamps must be timezone-aware.

## Mutation boundary

This module deliberately contains no document writer. Applying a patch to DOCX/PDF/other work products must be a distinct operation with its own explicit user/lawyer command and audit record.
