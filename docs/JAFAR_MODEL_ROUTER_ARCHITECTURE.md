# JAFAR Model Router foundation

ROUTER EXECUTABLE = YES  
OPENAI ADAPTER IMPLEMENTED = YES (configuration-driven `OpenAICompatibleProvider`)  
GEMINI CONTRACT = YES (`GeminiProvider`, injected transport only)  
LIVE OPENAI CALLS = 0 in this package; network is opt-in only.  
GEMINI ADAPTER = NOT IMPLEMENTED  
DEEPSEEK ADAPTER = NOT IMPLEMENTED  
REALTIME VOICE ADAPTER = NOT IMPLEMENTED

NETWORK EXECUTION POLICY: synthetic-only by default; live calls require explicit
opt-in, enabled provider, credential reference and synthetic data classification.
Private-client data is rejected by the smoke gate. `scripts/openai_live_smoke.py`
exits with `LIVE_AI_NETWORK=DISABLED` and `SMOKE=NOT_RUN` unless explicitly opted in.
DeepSeek has a disabled-by-default contract skeleton; it is not added to fallback
priority automatically.

Controlled live smoke is a separate acceptance state. `scripts/openai_live_smoke.py`
never performs a request by default and refuses the opt-in path without a local
credential reference. A credential being present alone cannot activate network
access. Smoke input is synthetic-only, one request maximum, no retry/fallback, and
the response is not persisted.

Failure diagnostics use status/transport categories only and never include request,
response, authorization or credential material. The first observed smoke cannot be
retrospectively assigned an HTTP category because the original adapter intentionally
discarded status/body; its safe classification is `UNKNOWN`. The adapter accepts
both legacy chat-completions content and Responses-style `output_text`, but the
request endpoint/schema remains chat-completions and must be verified before a
second smoke.

The domain uses provider-neutral `ModelTier`, `ModelRequest`, `ModelResponse` and
`ModelRouter` contracts. Routing is deterministic: classification/extraction use
FAST, ordinary analysis/drafting STANDARD, complex legal position EXPERT, and an
explicit second opinion requires `SECOND_OPINION_ALLOWED` matter policy.

Matter provider policy is an authorization/confidentiality boundary. It is checked
before routing; there is no silent cross-provider fallback or automatic fan-out.
Model IDs are configuration concerns, never legal-domain constants. Safe
observability may record provider, tier, latency, token counts, outcome and a
correlation ID, but never document text, email bodies, analysis content or keys.

The OpenAI-compatible adapter is isolated in `src/jafar/model_provider.py`; model
IDs, endpoint and key are supplied by configuration. Future adapters may target
Gemini, DeepSeek and a separate realtime voice provider. EXTERNAL AI CALLS IN THIS
PACKAGE = 0.
