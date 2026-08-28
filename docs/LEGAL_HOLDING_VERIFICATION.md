# Semantic legal holding verification

A proposition candidate extracted from a judicial act is not automatically a legal holding.

`LegalHoldingVerifier` separates the court's own legal conclusion from:

- party arguments;
- prosecutor/defense submissions;
- lower-court reasoning;
- factual narrative;
- quotations or summaries of another authority;
- ambiguous reported speech that requires manual context review.

Only `verified_holding` with `may_enter_holding_base=true` may cross into the precedent-candidate boundary. This status is a semantic workflow classification, not a substitute for canonical source verification, applicability review, precedent treatment or lawyer judgment.

## Acceptance gates

- Party arguments must never enter the holding base as court holdings.
- Lower-court reasoning quoted in a higher-court act must remain separate from the higher court's own holding.
- Factual findings and procedural history must not be promoted to legal propositions.
- Quoted external authorities must be routed to authority verification rather than attributed to the current court.
- Ambiguous reported speech requires human review.
- A document with no verified holding cannot enter the precedent pipeline merely because it contains legal terminology.
- Canonical source verification, applicability and precedent freshness remain separate downstream gates.
