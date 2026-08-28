# JAFAR Model Router foundation

ROUTER EXECUTABLE = YES  
OPENAI ADAPTER IMPLEMENTED = YES (configuration-driven `OpenAICompatibleProvider`)  
LIVE OPENAI CALLS = 0 in this package; network is opt-in only.  
GEMINI ADAPTER = NOT IMPLEMENTED  
DEEPSEEK ADAPTER = NOT IMPLEMENTED  
REALTIME VOICE ADAPTER = NOT IMPLEMENTED

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
