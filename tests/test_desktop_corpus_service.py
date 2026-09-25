from __future__ import annotations

from jafar.desktop_corpus_service import DesktopCorpusService
from jafar.encrypted_desktop_corpus import EncryptedDesktopCorpusStore


def test_explicit_import_builds_matter_scoped_local_citations(tmp_path):
    store = EncryptedDesktopCorpusStore(tmp_path / "corpus.sqlite3", tmp_path / "documents", b"k" * 32)
    document = DesktopCorpusService(store).import_document(
        matter_id="matter-1",
        filename="claim.txt",
        media_type="text/plain",
        original_bytes=b"SYNTHETIC LOCAL ARTICLE 10",
        extracted_text="СТАТЬЯ 10\n\nSYNTHETIC LOCAL ARTICLE 10 applies to the Matter.",
    )
    result = store.retrieve("matter-1", "ARTICLE 10")
    assert result.citations
    assert result.citations[0].startswith(f"document:{document.document_id}:page:1:chunk:")
    assert store.retrieve("other-matter", "ARTICLE 10").results == ()
    store.close()
