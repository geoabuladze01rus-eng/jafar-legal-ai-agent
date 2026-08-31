import pytest

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


def test_never_joins_distinct_legal_sections_even_when_short():
    chunks = semantic_legal_chunks(
        "УСТАНОВИЛ:\n\nКраткий вводный текст.\n\nПОСТАНОВИЛ:\n\nХодатайство удовлетворить.",
        source_page=2,
        target_chars=500,
        max_chars=800,
    )

    assert [chunk.section for chunk in chunks] == ["УСТАНОВИЛ", "ПОСТАНОВИЛ"]
    assert "ПОСТАНОВИЛ" not in chunks[0].content


def test_preserves_article_heading_and_stable_source_traceability():
    text = "Статья 159.4 УК РФ\n\n1. Обвинение должно быть конкретным.\n\n2. Суд оценивает доказательства."
    first = semantic_legal_chunks(text, source_page=8, target_chars=500, max_chars=800)
    second = semantic_legal_chunks(text, source_page=8, target_chars=500, max_chars=800)

    assert len(first) == 1
    assert first[0].section == "Статья 159.4 УК РФ"
    assert first[0].stable_id == second[0].stable_id
    assert text[first[0].source_start:first[0].source_end] == first[0].content


def test_preserves_markdown_table_headers_when_a_table_is_split():
    rows = "\n".join(f"| {index} | Доказательство {index} |" for index in range(1, 25))
    text = "# Доказательства\n\n| № | Документ |\n| --- | --- |\n" + rows
    chunks = semantic_legal_chunks(text, source_page=5, target_chars=120, max_chars=160)

    table_chunks = [chunk for chunk in chunks if "| № | Документ |" in chunk.content]
    assert len(table_chunks) > 1
    assert all("| --- | --- |" in chunk.content for chunk in table_chunks)
    assert sum(chunk.content.count("Доказательство") for chunk in table_chunks) == 24


def test_handles_spaced_ocr_heading_and_rejects_invalid_limits():
    chunks = semantic_legal_chunks("У С Т А Н О В И Л :\n\nСуд установил обстоятельства.", source_page=1)

    assert chunks[0].section == "УСТАНОВИЛ"
    with pytest.raises(ValueError, match="target_chars"):
        semantic_legal_chunks("текст", source_page=1, target_chars=0)
    with pytest.raises(ValueError, match="source_page"):
        semantic_legal_chunks("текст", source_page=0)


def test_source_offsets_reconstruct_irregularly_spaced_source_text():
    text = "Глава 1. Общие положения\n\nПервое предложение.   Второе предложение!\n\nТретий абзац."
    chunks = semantic_legal_chunks(text, source_page=3, target_chars=30, max_chars=48)

    assert all(text[chunk.source_start:chunk.source_end] == chunk.content for chunk in chunks)
    assert all(len(chunk.content) <= 48 for chunk in chunks)


def test_mixed_language_chapters_remain_distinct_sections():
    text = "CHAPTER I General provisions\n\nEnglish source text.\n\nГлава 2. Доказательства\n\nРусский текст."
    chunks = semantic_legal_chunks(text, source_page=9, target_chars=500, max_chars=800)

    assert [chunk.section for chunk in chunks] == ["CHAPTER I General provisions", "Глава 2. Доказательства"]
