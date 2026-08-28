# Structured model providers and AI Council

Jafar uses provider-agnostic routing for model calls. OpenAI remains the default legal-analysis provider, while Gemini, DeepSeek, Qwen and Kimi can be selected for specialized tasks or independent verification.

## Provider roles

- `openai` — primary legal analysis and final orchestration.
- `qwen` — second-opinion analysis and alternative reasoning.
- `kimi` — long-context, case timeline and cross-document analysis.
- `deepseek` — coding and technical analysis.
- `gemini` — vision and Google-context workloads.

## AI Council

`AICouncil` can run the same request through several independent providers and returns every response. It does not silently average conflicting conclusions. If providers disagree, the result contains an explicit disagreement marker so the application can surface the conflict for human review.

The council defaults to the order `openai`, `qwen`, `kimi`, `deepseek`, `gemini` and requires at least two successful independent responses unless configured otherwise.

## Configuration

Keep credentials outside Git.

### OpenAI

- `OPENAI_API_KEY`
- `OPENAI_MODEL`

### DeepSeek

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `DEEPSEEK_BASE_URL`

### Alibaba Cloud Model Studio (Qwen and Kimi)

- `DASHSCOPE_API_KEY`
- `ALIBABA_MODEL_STUDIO_CHAT_URL` — full OpenAI-compatible `/chat/completions` endpoint for the selected Alibaba region/workspace.
- `QWEN_MODEL`
- `KIMI_MODEL`

Alibaba Cloud Model Studio exposes Qwen and third-party models through an OpenAI-compatible API, so Jafar reuses the generic HTTP provider adapter instead of introducing provider-specific networking code.

## Confidentiality contract

Confidential legal requests fail closed. The default `ProviderPrivacyPolicy` permits only OpenAI for confidential material. Qwen, Kimi, DeepSeek and Gemini are enabled for non-confidential or sanitized workloads by default.

A deployment may explicitly construct a trusted `ProviderPrivacyPolicy` that opts additional providers into confidential processing after data-residency, retention, professional-secrecy and contractual requirements have been reviewed.

## Authorization boundary

Model analysis is not an authorization layer. Consequential actions such as sending messages, changing matters, creating deadlines or publishing content remain behind explicit application controls.
