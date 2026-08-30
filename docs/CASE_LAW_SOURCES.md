# Case-Law Source Adapters

## Purpose

Jafar separates discovery from canonical provenance. A source that helps find a judicial act is not automatically allowed to verify that act.

## Trust levels

### Canonical

Official judicial sources, such as materials published by the Supreme Court of the Russian Federation, may supply canonical provenance candidates. Even official-source items still pass the normal legal-authority verification, applicability and precedent-freshness gates before entering drafting inputs.

### Discovery

Aggregators such as sudact.ru are useful for search and discovery. They may identify a potentially relevant decision, but they do not by themselves establish canonical provenance, authoritative text, current status or precedential force.

A discovery-only item must therefore be matched to an official/canonical counterpart before it can be converted into a canonical `CaseLawRecord`.

## Sync flow

1. Fetch source items from adapters.
2. Deduplicate repeated source records.
3. Separate canonical candidates from discovery-only candidates.
4. Match discovery records to canonical records by normalized citation, court and decision date where possible.
5. Keep unmatched discovery records in a review queue.
6. Send canonical candidates through authority verification.
7. Only after canonical fingerprint verification may the item become a `CaseLawRecord`.
8. Continue through applicability, precedent freshness and active-case impact analysis.

## Acceptance gates

- Discovery-only sources cannot directly create canonical case-law records.
- A canonical candidate still requires an externally verified canonical fingerprint.
- Matching an aggregator record to an official record does not change the aggregator record's trust level.
- Unmatched discovery records require review and cannot enter final drafting inputs.
- Source adapters never rewrite an active legal position automatically.
