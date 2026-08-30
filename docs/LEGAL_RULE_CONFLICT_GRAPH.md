# Legal Rule Conflict Graph

## Purpose

`LegalRuleConflictGraph` compares already normalized legal rules and records explicit relationships between them. It exists to prevent text-level similarity or model confidence from being mistaken for a legal relationship.

## Supported relationships

- `same_rule`
- `narrower`
- `broader`
- `exception`
- `conflict`
- `superseded`
- `unknown`

Exact semantic-key equality may establish `same_rule` deterministically. Every material doctrinal relationship (`narrower`, `broader`, `exception`, `conflict`, `superseded`) must come from a separately verified relationship supplied by an upstream legal-review or canonical-treatment resolver.

## Unresolved pairs

When two normalized rules concern the same legal issue but have different semantic keys and no verified relationship, they are placed in `unresolved_pairs`. Jafar must not guess whether one is narrower, broader, conflicting, or superseding.

## Release gate

Final drafting is blocked when:

- unresolved rule pairs remain;
- a verified `conflict` exists;
- a verified `superseded` relationship exists.

Verified `same_rule`, `narrower`, or `broader` relationships may pass the graph release gate, but applicability, precedent freshness, authority weight, and lawyer review remain separate gates.

## Safety boundary

The graph is not a legal conclusion engine. It never decides which rule is controlling merely because one is newer or worded more broadly. Relationship verification and final legal effect remain subject to canonical source research and lawyer judgment.
