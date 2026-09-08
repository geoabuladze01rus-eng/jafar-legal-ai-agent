from __future__ import annotations

import hashlib


_FIELDS = (
    "chat",
    "type",
    "content",
    "caption",
    "photo",
    "question",
    "options",
    "correct",
    "explanation",
)


def telegram_delivery_fingerprint(
    *,
    chat_id: int | str,
    publication_type: str,
    content: str | None = None,
    caption: str | None = None,
    photo_url: str | None = None,
    question: str | None = None,
    options_json: str | None = None,
    correct_option_ids_json: str | None = None,
    explanation: str | None = None,
) -> str:
    """Return the cross-runtime SHA-256 used by JAFAR and Make before delivery claim.

    The serialization format is intentionally simple so Make can reproduce it without
    custom code. It is a change detector/idempotency binding, not a signed message format.
    Do not change the labels/order without a coordinated Make migration.
    """

    values = (
        str(chat_id),
        publication_type,
        content or "",
        caption or "",
        photo_url or "",
        question or "",
        options_json or "",
        correct_option_ids_json or "",
        explanation or "",
    )
    canonical = "|".join(f"{key}={value}" for key, value in zip(_FIELDS, values, strict=True))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
