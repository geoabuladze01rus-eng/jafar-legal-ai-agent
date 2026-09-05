from jafar.legal_chunking import semantic_legal_chunks


def test_keeps_legal_heading_with_following_section():
    text = """УСТАНОВИЛ:\n\nСуд установил обстоятельства дела.\n\nПОСТАНОВИЛ:\n\n1. Ходатайство удовлетворить.\n2. Меру пресечения изменить."""
    chunks = semantic_legal_chunks(text, source_page=7, target_chars=60, max_chars=120)

    assert chunks
    assert all(chunk.source_page == 7 for chunk in chunks)
    assert any("ПОСТАНОВИЛ" in chunk.content for chunk in chunks)
    assert any(chunk.section == "ПОСТАНОВИЛ" for chunk in chunks)


def test_prefers_sentence_boundaries_for_oversized_paragraph():
    sentence = "Обвиняемый заявил о несогласии с предъявленным обвинением. "
    text = sentence * 12
    chunks = semantic_legal_chunks(text, source_page=3, target_chars=180, max_chars=240)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 240 for chunk in chunks)
    assert all(chunk.content.endswith(".") for chunk in chunks)


def test_does_not_create_overlap_that_duplicates_legal_facts():
    text = "\n\n".join(f"Пункт {index}. Обстоятельство {index}." for index in range(1, 25))
    chunks = semantic_legal_chunks(text, source_page=1, target_chars=120, max_chars=180)
    joined = "\n".join(chunk.content for chunk in chunks)

    for index in range(1, 25):
        assert joined.count(f"Пункт {index}.") == 1


def test_empty_page_produces_no_chunks():
    assert semantic_legal_chunks("  \n\n ", source_page=4) == []
