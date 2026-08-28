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
