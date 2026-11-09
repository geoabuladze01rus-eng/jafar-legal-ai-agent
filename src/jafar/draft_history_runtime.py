"""Desktop-only encrypted legal draft archive construction."""

from __future__ import annotations

from .desktop_runtime import desktop_paths, is_desktop_runtime
from .desktop_key_material import desktop_corpus_key
from .encrypted_draft_history import EncryptedDraftHistory, derive_draft_history_key


def build_draft_history_from_env() -> EncryptedDraftHistory | None:
    if not is_desktop_runtime():
        return None
    paths = desktop_paths().create()
    return EncryptedDraftHistory(
        paths.application_support / "drafts.sqlite3",
        derive_draft_history_key(desktop_corpus_key()),
    )
