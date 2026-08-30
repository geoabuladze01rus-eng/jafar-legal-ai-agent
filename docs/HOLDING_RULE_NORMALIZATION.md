# Holding Rule Normalization

Verified court holdings are converted into a stable legal-rule structure only after the semantic holding gate has confirmed that the text is the court's own holding.

The normalized structure is:

`legal_issue -> rule -> conditions -> exceptions -> consequence -> authority`

`HoldingRuleNormalizer` does not invent missing doctrine. The legal issue, rule, conditions, exceptions and consequence must be supplied explicitly by an upstream extraction/review step. Missing required fields fail closed rather than being inferred from the holding text.

A normalized rule receives a stable semantic key for deterministic deduplication of wording variants that differ only in punctuation, casing, whitespace or order of conditions/exceptions.

For broader semantic equivalence, `LegalRuleOntology` provides explicit curated concepts and aliases. This allows differently worded positions to map to the same legal issue/rule concept when that mapping has been approved. Unknown wording remains unresolved; model similarity alone cannot silently merge legal rules.

`LegalRuleIndex` stores normalized rules by explicit issue and rule concepts and can report whether two rules are equivalent under the curated ontology. Ambiguous aliases are rejected.

## Acceptance gates

- only `verified_holding` text may enter normalization;
- missing `legal_issue` or `rule` must not be inferred;
- source holding text and source refs must remain preserved;
- unknown wording must remain unresolved until mapped to an approved ontology concept;
- ambiguous aliases must fail closed;
- semantic equivalence must never be inferred solely from model confidence or lexical similarity;
- normalized rules still require lawyer review before they are used to change a case theory or final legal document.
