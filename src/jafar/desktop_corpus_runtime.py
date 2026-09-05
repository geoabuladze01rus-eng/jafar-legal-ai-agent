"""Desktop-only corpus construction without changing server/Supabase behavior."""

from __future__ import annotations

from .desktop_runtime import desktop_paths, is_desktop_runtime
from .encrypted_desktop_corpus import EncryptedDesktopCorpusStore, corpus_key_from_environment


def build_desktop_corpus_from_env() -> EncryptedDesktopCorpusStore | None:
    if not is_desktop_runtime():
        return None
    paths = desktop_paths().create()
    return EncryptedDesktopCorpusStore(
        paths.corpus_database, paths.documents, corpus_key_from_environment()
    )
