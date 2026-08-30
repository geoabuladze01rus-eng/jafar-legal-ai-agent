# Legal doctrine evolution timeline

`DoctrineEvolutionEngine` combines the normalized legal-rule conflict graph with verified precedent chronology. It is intended to show how a legal position develops over time without treating chronology alone as doctrine.

## Event model

The timeline can represent:

- `origin` — a normalized rule first appears in a verified holding;
- `confirmation` — another normalized rule has the same semantic rule;
- `narrowing` — a verified relation narrows an earlier rule;
- `broadening` — a verified relation broadens an earlier rule;
- `exception` — a verified exception is added;
- `conflict` — verified authorities contain materially conflicting rules;
- `supersession` — a verified later rule supersedes another rule;
- `review_required` — precedent freshness or another upstream gate remains unresolved.

## Trust boundary

The timeline does not infer doctrinal relationships from dates or textual similarity. Dates come from verified precedent records. Narrowing, broadening, exception, conflict and supersession events come only from verified rule relationships in `LegalRuleConflictGraph`.

A newer authority therefore does not automatically replace an older authority. An unresolved pair remains unresolved until a canonical research/review step supplies a verified relation.

## Current-rule set

`current_rule_ids` excludes a rule only when the conflict graph contains a verified `superseded` relation identifying that rule as the displaced side. Conflicting, limited or unresolved rules remain visible for lawyer review rather than being silently removed.

## Release gate

`release_ready` is fail-closed. Final drafting is blocked when:

- unresolved rule pairs remain;
- precedent freshness requires review;
- the timeline contains a verified conflict;
- the timeline contains a verified supersession event that still needs lawyer treatment in the drafting context.

A same-rule confirmation chain can pass the doctrine gate, subject to the independent authority verification, applicability and lawyer-approval gates.

## Acceptance requirements

- Doctrine chronology must be based on verified dates, not model-generated dates.
- Material doctrinal relations must already be verified upstream.
- `newer wins` is prohibited.
- Superseded rules must remain auditable in the timeline even when excluded from `current_rule_ids`.
- Unresolved relations must remain visible.
- The timeline never changes a legal strategy, pleading or court filing automatically.
