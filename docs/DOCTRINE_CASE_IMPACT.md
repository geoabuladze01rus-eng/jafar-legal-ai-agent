# Doctrine to active-case impact

## Purpose

`DoctrineToCaseImpactEngine` connects verified doctrine evolution with concrete active case theory issues and work products. It does not rewrite strategy or filings automatically. It identifies where a lawyer must review an existing position because a verified doctrine event affects the same legal issue, authority, or normalized rule.

## Inputs

- `CaseTheoryReport` — the current source-traceable theory map for the matter.
- `DoctrineEvolutionTimeline` — verified doctrinal events assembled from rule relations and precedent freshness.
- optional `ActiveWorkProduct` items — motions, complaints, court-speech outlines, interrogation plans, or other prepared work products that depend on a topic, authority, or normalized rule.

## Urgency

- `low` — confirmation or stable development without a critical change.
- `medium` — broadening or a low-risk doctrine event that merits review.
- `high` — narrowing, exception, or unresolved review/freshness signal.
- `critical` — verified conflict or supersession. High-impact changes are also escalated to critical when they touch an already prepared work product.

Urgency is a workflow-priority signal, not a legal outcome prediction.

## Safety boundary

The engine never edits, sends, files, withdraws, or replaces a legal document. It returns issue IDs, doctrine event IDs, affected work-product IDs, reasons, and a lawyer-review requirement. Legal consequences, applicability to the facts, wording changes, procedural response, and filing decisions remain with the lawyer.

## Release gate

`release_ready()` fails when any active-case impact is `high` or `critical`. A medium broadening signal may pass the technical release gate but remains visible for lawyer review.

## Acceptance gates

- Only the matching legal issue is impacted by topic alone.
- Verified conflict or supersession produces critical urgency.
- Narrowing or exception produces at least high urgency.
- Impact on an already prepared work product raises urgency by one level, capped at critical.
- A work product may also match by explicit authority ID or normalized rule ID.
- No doctrine event automatically changes the theory, requested relief, authority citation, or procedural action.
- Every returned impact requires lawyer review.
