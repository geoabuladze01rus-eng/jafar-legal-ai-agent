from jafar.document_intelligence import DocumentIntelligence


def test_document_intelligence_normalizes_text_and_hashes_content():
    result = DocumentIntelligence().extract(
        document_id="doc-1",
        text="  Договор\n поставки   № 12  ",
        metadata={"source": "email"},
    )
    assert result.text == "Договор поставки № 12"
    assert len(result.content_hash) == 64
    assert result.facts[0]["type"] == "text"
