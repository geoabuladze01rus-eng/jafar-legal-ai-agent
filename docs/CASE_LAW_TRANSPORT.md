# Case-law transport and parsers

## Purpose

This layer connects Jafar's source-adapter contracts to real HTTP pages while preserving the trust boundary between canonical and discovery sources.

## Official Supreme Court source

`SupremeCourtHttpFetcher` reads the official Supreme Court of the Russian Federation electronic-reference page on `vsrf.ru`. The official source is treated as a canonical candidate only; every discovered item still passes canonical authority verification before it can enter the working case-law repository.

The fetcher stores raw-page provenance through `ParsedCaseLawPage`: resolved URL, response-body SHA-256 fingerprint, content type, ETag and Last-Modified when supplied by the server.

## Sudact discovery

`SudactHttpFetcher` reads public Supreme Court result pages on `sudact.ru` for discovery. Every parsed item remains `SourceTrust.DISCOVERY`. A Sudact URL, text or fingerprint can never supply canonical provenance and cannot be converted directly into a canonical `CaseLawRecord`.

## HTTP transport

`ResilientHttpTransport` provides:

- explicit user agent;
- request timeout;
- bounded retry attempts;
- exponential retry delay;
- retry only for transient HTTP statuses and transport failures;
- configurable minimum request interval;
- SHA-256 fingerprinting of every fetched response body.

Retries are intentionally bounded. Source adapters must fail visibly rather than loop indefinitely or silently downgrade provenance.

## Parser boundary

`LinkBasedCaseLawParser` is intentionally conservative. It discovers links whose visible label looks like a judicial act or Supreme Court review. It does not infer legal holdings, topics or propositions from HTML navigation text. Those fields remain unclassified until a later deterministic extraction / reviewed enrichment stage.

A parser finding is not authority verification.

## Acceptance gates

- `vsrf.ru` data remains canonical-candidate material until normal verification succeeds.
- Sudact remains discovery-only regardless of apparent citation accuracy.
- Raw response fingerprints survive parsing.
- Transport retries are bounded and rate-limited.
- Parser failures or site markup changes must not promote partial data to verified law.
- Unknown dates/topics/propositions remain explicitly unclassified rather than guessed.
