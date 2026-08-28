# Jafar AI Council

## Purpose

AI Council is Jafar's multi-model review layer. It is designed for legal work where a single model should not silently become the sole source of reasoning.

## Default roles

- OpenAI: primary legal analysis and final orchestration.
- Qwen: independent second opinion and alternative reasoning.
- Kimi: long-context and cross-document review.
- DeepSeek: technical analysis and adversarial reasoning where configured.
- Gemini: vision and Google-context workloads.

## Processing pattern

1. The router chooses the primary provider for the task.
2. Privacy policy determines which providers are permitted to receive the material.
3. AI Council can send the same sanitized/non-confidential request to multiple independent providers.
4. Every successful response is preserved.
5. Provider failures are recorded separately.
6. Divergent conclusions are surfaced for human review instead of being averaged away.
7. No external action is authorized by model consensus alone.

## Confidentiality

The default policy is fail-closed: confidential requests are restricted to explicitly trusted providers. Adding a provider to confidential processing is a deployment decision and requires review of data residency, retention, contractual terms and professional-secrecy requirements.

## Acceptance gates

- At least two independent successful responses for council mode unless the caller explicitly requests a different minimum.
- No silent downgrade when the required number of council members fails.
- Qwen/Kimi must not receive confidential requests under the default privacy policy.
- Disagreements must remain visible to the calling application.
- Sending email, modifying records, publishing, filing or scheduling remains behind Jafar's action-approval layer.
