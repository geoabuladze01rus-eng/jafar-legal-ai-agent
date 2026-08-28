# JAFAR Model Router foundation

The domain uses provider-neutral `ModelTier`, `ModelRequest`, `ModelResponse` and
`ModelRouter` contracts. Routing is deterministic: classification/extraction use
FAST, ordinary analysis/drafting STANDARD, complex legal position EXPERT, and an
explicit second opinion requires `SECOND_OPINION_ALLOWED` matter policy.

Matter provider policy is an authorization/confidentiality boundary. It is checked
before routing; there is no silent cross-provider fallback or automatic fan-out.
Model IDs are configuration concerns, never legal-domain constants. Safe
observability may record provider, tier, latency, token counts, outcome and a
correlation ID, but never document text, email bodies, analysis content or keys.

Future adapters may target OpenAI, Gemini, DeepSeek and a separate realtime voice
provider. LIVE EXTERNAL PROVIDERS = NOT IMPLEMENTED. EXTERNAL AI CALLS IN THIS
PACKAGE = 0.
