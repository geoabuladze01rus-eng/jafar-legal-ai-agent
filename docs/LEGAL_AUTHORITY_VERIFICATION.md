# Legal Authority Verification

Jafar must not promote a statute, Supreme Court position, case citation or other legal authority to verified status merely because a language model generated it.

## Pipeline

1. Legal questions are produced by the court-outline layer.
2. Retrieval is performed by an external authority source/resolver.
3. Retrieved items enter Jafar as `AuthorityCandidate` objects.
4. `LegalAuthorityVerifier` resolves each candidate against a canonical source.
5. Verification requires all of the following: canonical citation, canonical source URL and stable source fingerprint.
6. A conflicting supplied URL produces `conflicting`, not `verified`.
7. Missing canonical provenance produces `unverified`.
8. Only `verified` results may be converted to verified `LegalAuthorityRef` objects for the court outline.

## Release gate

`LegalAuthorityPipeline.outline_is_release_ready()` returns false when either the outline itself contains an unverified authority or any topic-level authority verification report contains a non-verified result.

This is a drafting/review gate only. It does not mean the authority is applicable to the facts, binding on the court, current for the relevant date, or sufficient to support the requested remedy. Those questions remain subject to lawyer review and, where relevant, a separate applicability/effective-date check.

## Safety boundary

- Models may propose legal questions but cannot self-verify their own citations.
- A resolver must be external to the model output and provide canonical provenance.
- No authority is considered verified without source fingerprinting.
- Verification does not authorize filing, sending or making any external legal submission.
