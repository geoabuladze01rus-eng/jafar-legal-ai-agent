# Legal document pipeline

Jafar processes an incoming legal document in explicit stages:

1. **Extraction** — `DocumentExtractor` converts supported TXT/Markdown/PDF/DOCX input to text and computes a stable fingerprint.
2. **Matter matching** — `MatterMatcher` ranks existing matters using deterministic signals. Weak or ambiguous matches return no matter.
3. **Analysis** — legal analysis runs only after a confident matter match in the current orchestration layer.
4. **Persistence** — a later integration layer may attach the document, analysis, deadlines, and event to the matched matter. This pipeline does not mutate authoritative case data by itself.
5. **Review** — `needs_matter_review` is an explicit safe state for documents that cannot be confidently assigned.

The important invariant is: **no automatic case attachment on uncertainty**. The model may assist analysis, but it does not override deterministic identity or approval boundaries.
