# Telegram visual pipeline

## Purpose

Ordinary editorial posts for «Уголовка наизнанку» must not silently fall back to plain text when an approved visual is required.

The visual layer is an editorial safety gate, not decoration added after publication.

## Editorial contract

For ordinary `text/photo` editorial material:

1. `Visual Required = true`.
2. `Visual Category` must be assigned explicitly.
3. The category must resolve to exactly one active, approved record in `Telegram Visual Library`.
4. `Visual Drive File ID` (or a future equivalent approved asset reference) must be present.
5. Production delivery uses `Publication Type = photo`.
6. Missing or unavailable media blocks publication. There is no production text fallback.
7. The caption/text should normally contain 2–5 meaningful Telegram emojis. Exact legal citations, article numbers and judicial details remain emoji-free.

Polls and quizzes are different: Telegram does not attach a cover image to the same poll payload. A cover requires a deliberate two-message flow. Until that flow is implemented and tested, the poll/quiz itself remains the canonical delivery object.

## Notion fields

`Social Media Content Calendar` contains:

- `Visual Required` — checkbox.
- `Visual Category` — deterministic category key.
- `Visual Drive File ID` — approved asset reference.
- `Publication Type` — must be `photo` for ordinary visual-required production delivery.

Current category keys:

- `what_to_do`
- `investigation_error`
- `court_practice`
- `quiz`
- `investigator_logic`
- `news_analysis`
- `personal_brand`
- `practice_case`

## Telegram Visual Library

The separate Notion database `Telegram Visual Library` is the approval registry.

A record is eligible only when:

- `Approved = true`
- `Active = true`
- `Category` exactly matches the publication's `Visual Category`
- the asset reference is present and readable

Known approved assets currently exist for:

- `what_to_do`
- `investigation_error`
- `court_practice`
- `quiz`

The remaining categories intentionally have inactive placeholders. Do not choose the “closest-looking” visual if a category lacks an approved asset.

## JAFAR machine gates

`TelegramPublication` carries:

- `visual_required`
- `visual_asset_id`
- `visual_category`

When `visual_required` is true, `publish_decision()` fails closed for:

- `visual_asset_missing`
- `visual_category_missing`
- `visual_required_but_text`

The AI editor also adds visual blockers before human review. AI still cannot set `Ready` or `Published`.

## Make v3 gate

The pre-claim gate must reject `text` delivery when `Visual Required = true`.

Target photo route:

`Notion Ready -> safety gate -> resolve approved visual -> download binary -> durable claim -> Notion In progress -> Telegram SendPhoto(data) -> Supabase SENT -> atomic Notion Published`

Media resolution must happen before the irreversible Telegram send.

## Preferred asset transport

### Primary: Google Drive binary download

Approved assets are stored in the dedicated Drive folder `Уголовка наизнанку`.

Target Make modules:

`Google Drive: Download a File` -> `Telegram: SendPhoto`

Telegram `SendPhoto` must use `send_bydata` and map:

- filename from the Drive download output
- binary `data` from the Drive download output

No public URL is required.

### Fallback: Supabase Base64 asset registry

A protected `telegram_visual_assets` table and service-role-only RPC exist as a fallback.

Make's documented expression:

`toBinary(base64_value; "base64")`

converts the stored Base64 string to binary data suitable for file inputs.

A live Make/Supabase probe on 2026-09-09 confirmed:

- Supabase RPC HTTP 200
- Base64 decoded by Make
- decoded length 68 bytes for the synthetic PNG probe
- no Telegram call was involved

Do not store production visual assets in this fallback until size/maintenance tradeoffs are accepted or the Drive route is unavailable.

## Failure behaviour

If media is required but cannot be resolved:

- do not claim the publication for delivery
- do not call Telegram
- do not send text instead
- keep or return the card to Review and surface a visual blocker when due

If Telegram may already have accepted a photo but downstream writeback fails, follow the normal durable-ledger `SENT/UNCERTAIN` reconciliation rules. Never blindly resend.

## Regression that motivated this gate

The first real v3 E2E post on 2026-09-09 was delivered successfully as Telegram message `582`, but the Notion card was still `Publication Type = text`, so the router correctly chose `sendMessage` and the post went out without its approved visual. The delivery system itself worked; the missing media-stage gate was the defect.

The v3 text pre-claim route has since been changed so `Visual Required = true` cannot pass as text.
