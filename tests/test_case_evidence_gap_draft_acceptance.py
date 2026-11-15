"""End-to-end synthetic user scenario acceptance:
Upload PDF/DOCX to Matter -> Extract and verify facts with source citations ->
Analyze evidence gaps -> Prepare editable motion/complaint DOCX -> Lawyer review gates.

All parties, companies, court numbers and documents are completely synthetic.
No live client materials, production databases or external cloud models are touched.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pytest
from docx import Document

from jafar.case_evidence_gap_service import (
    CaseEvidenceGapRequest,
    CaseEvidenceGapService,
)
from jafar.desktop_corpus_service import DesktopCorpusService
from jafar.document_parsers import ParsedPage
from jafar.domains import MatterType
from jafar.encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from jafar.legal_draft_service import (
    LegalDraftRequest,
    LegalDraftService,
    render_legal_draft_docx,
)
from jafar.legal_models import Matter
from jafar.matters import MatterStore


def _create_synthetic_docx_bytes() -> bytes:
    doc = Document()
    doc.add_paragraph(
        "10.01.2026 между ООО «Альфа» и ООО «Бета» заключен договор поставки № 42 на сумму 2 000 000 рублей. "
        "По условиям договора оплата производится в течение 10 банковских дней с момента отгрузки. "
        "Товар передан по товарной накладной от 15.01.2026."
    )
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_end_to_end_case_evidence_gap_and_docx_draft_scenario(tmp_path):
    # -------------------------------------------------------------------------
    # 1. Загрузка PDF/DOCX в конкретное дело (Ingestion into Matter)
    # -------------------------------------------------------------------------
    matters = MatterStore()
    now = datetime.now(timezone.utc)
    matter_id = "matter-synthetic-audit"
    matters.create(
        Matter(
            id=matter_id,
            title="Учебное арбитражное дело № А40-54321/2026",
            matter_type=MatterType.ARBITRATION,
            client_name="ООО «Альфа»",
            opposing_party="ООО «Бета»",
            court_or_authority="Арбитражный суд города Москвы",
            case_number="А40-54321/2026",
            created_at=now,
            updated_at=now,
        )
    )

    master_key = b"S" * 32
    corpus_db = tmp_path / "corpus.sqlite3"
    originals_dir = tmp_path / "originals"
    corpus = EncryptedDesktopCorpusStore(corpus_db, originals_dir, master_key)
    desktop_service = DesktopCorpusService(corpus)

    # DOCX upload
    docx_bytes = _create_synthetic_docx_bytes()
    docx_text = (
        "10.01.2026 между ООО «Альфа» и ООО «Бета» заключен договор поставки № 42 на сумму 2 000 000 рублей. "
        "По условиям договора оплата производится в течение 10 банковских дней с момента отгрузки. "
        "Товар передан по товарной накладной от 15.01.2026."
    )
    doc_docx = desktop_service.import_document(
        matter_id=matter_id,
        filename="Договор поставки № 42.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_bytes=docx_bytes,
        extracted_text=docx_text,
    )
    assert doc_docx.state == "READY"

    # PDF upload with physical page provenance
    pdf_pages = (
        ParsedPage(
            page_number=1,
            text="Представитель ООО «Бета» заявил, что товар получен не в полном объеме и имел существенные недостатки.",
        ),
        ParsedPage(
            page_number=2,
            text=(
                "Ответчик утверждает, что оплата была частично произведена наличными средствами через третье лицо. "
                "Суд установил, что первичные платежные документы и акты сдачи-приемки с мотивированными возражениями в материалах дела отсутствуют."
            ),
        ),
    )
    pdf_text = "\n".join(page.text for page in pdf_pages)
    doc_pdf = desktop_service.import_document(
        matter_id=matter_id,
        filename="Протокол и отзыв ответчика.pdf",
        media_type="application/pdf",
        original_bytes=b"%PDF-1.4 synthetic protocol bytes",
        extracted_text=pdf_text,
        pages=pdf_pages,
    )
    assert doc_pdf.state == "READY"

    chunks = corpus.chunks(matter_id)
    assert len(chunks) >= 3

    # -------------------------------------------------------------------------
    # 2. Извлечение и проверка фактов с указанием источника
    #    (Facts, party claims, court findings with verified quotations)
    # -------------------------------------------------------------------------
    gap_service = CaseEvidenceGapService(matters, corpus)
    report = gap_service.analyze(
        matter_id,
        CaseEvidenceGapRequest(
            source_document_ids=[doc_docx.document_id, doc_pdf.document_id]
        ),
    )

    assert report.matter_id == matter_id
    assert report.case_number == "А40-54321/2026"
    assert len(report.statements) >= 3

    # Check distinct categories
    categories = {s.category for s in report.statements}
    assert "fact" in categories
    assert "party_claim" in categories
    assert "court_finding" in categories

    # Verify physical page provenance on PDF statements
    pdf_statements = [s for s in report.statements if s.document_id == doc_pdf.document_id]
    assert any(s.physical_page in (1, 2) for s in pdf_statements)

    # Verify every quote is authentic substring of actual chunk
    chunks_by_citation = {c.citation: c for c in chunks}
    for stmt in report.statements:
        chunk = chunks_by_citation[stmt.citation]
        assert " ".join(stmt.quote.split()) in " ".join(chunk.content.split())
        assert stmt.filename in ("Договор поставки № 42.docx", "Протокол и отзыв ответчика.pdf")

    # -------------------------------------------------------------------------
    # 3. Анализ и выявление пробелов (Evidence Gap Analysis)
    # -------------------------------------------------------------------------
    assert len(report.gaps) >= 1
    # Cash payment claim without bank receipt is flagged
    payment_gap = next((g for g in report.gaps if "оплат" in g.topic.lower() or "оплат" in g.description.lower()), None)
    assert payment_gap is not None
    assert payment_gap.severity == "high"
    assert len(payment_gap.expected_evidence) > 0
    assert "ходатайств" in payment_gap.suggested_action.lower()

    # -------------------------------------------------------------------------
    # 4. Подготовка редактируемой жалобы или ходатайства в DOCX
    # -------------------------------------------------------------------------
    draft_service = LegalDraftService(matters, corpus)

    # 4a. Motion (Ходатайство об истребовании доказательств)
    motion_request = LegalDraftRequest(
        kind="motion",
        recipient="В Арбитражный суд города Москвы",
        author="Представитель ООО «Альфа» (истец)",
        position=(
            "В судебном заседании представитель ответчика заявил о частичной оплате наличными "
            "денежными средствами через третье лицо. Данное утверждение является бездоказательным."
        ),
        legal_basis="Статьи 65, 66 Арбитражного процессуального кодекса РФ (проверено юристом)",
        requested_action="Истребовать из банка выписку по операциям на счете ответчика за период с 10.01.2026 по 01.03.2026.",
        source_document_ids=[doc_docx.document_id, doc_pdf.document_id],
        evidence_gaps=report.gaps,
        categorized_statements=report.statements,
    )

    motion_preview = draft_service.preview(matter_id, motion_request)
    assert motion_preview.can_export is True
    assert len(motion_preview.evidence_gaps) == len(report.gaps)
    assert len(motion_preview.categorized_statements) == len(report.statements)
    assert any("ходатайств" in w.lower() for w in motion_preview.warnings)

    motion_docx_bytes = render_legal_draft_docx(motion_preview)
    assert len(motion_docx_bytes) > 1000

    motion_doc = Document(BytesIO(motion_docx_bytes))
    motion_text = "\n".join(p.text for p in motion_doc.paragraphs).replace("\u00a0", " ")

    # Filing body is separated from internal review sheet
    filing_part, internal_part = motion_text.split("СЛУЖЕБНЫЙ ЛИСТ ПРОВЕРКИ ИСТОЧНИКОВ", 1)

    # Filing part contains procedural request and user's legal grounds
    assert "ХОДАТАЙСТВО" in filing_part
    assert "По делу № А40-54321/2026" in filing_part
    assert "Истребовать из банка выписку" in filing_part
    assert "Статьи 65, 66" in filing_part

    # Internal sheet contains categorized statements and evidence gaps
    assert "РАЗГРАНИЧЕНИЕ ФАКТОВ, УТВЕРЖДЕНИЙ СТОРОН И ВЫВОДОВ СУДА" in internal_part
    assert "[ФАКТИЧЕСКОЕ ОБСТОЯТЕЛЬСТВО]" in internal_part
    assert "[УТВЕРЖДЕНИЕ СТОРОНЫ]" in internal_part
    assert "[ВЫВОД СУДА / ОРГАНА]" in internal_part
    assert "ВЫЯВЛЕННЫЕ ПРОБЕЛЫ В ДОКАЗАТЕЛЬСТВАХ И ОБСТОЯТЕЛЬСТВАХ" in internal_part
    assert payment_gap.topic in internal_part
    assert payment_gap.suggested_action in internal_part

    # 4b. Complaint (Апелляционная жалоба на неисследованность обстоятельств)
    appeal_request = LegalDraftRequest(
        kind="appeal",
        recipient="В Девятый арбитражный апелляционный суд",
        author="Представитель ООО «Альфа»",
        position="Судом первой инстанции не дана надлежащая оценка отсутствию первичных доказательств.",
        legal_basis="Статьи 270, 271 АПК РФ (проверено юристом)",
        requested_action="Отменить решение суда первой инстанции в части отказа во взыскании процентов.",
        source_document_ids=[doc_docx.document_id, doc_pdf.document_id],
        evidence_gaps=report.gaps,
        categorized_statements=report.statements,
    )
    appeal_preview = draft_service.preview(matter_id, appeal_request)
    assert appeal_preview.can_export is True
    appeal_docx_bytes = render_legal_draft_docx(appeal_preview)
    appeal_doc = Document(BytesIO(appeal_docx_bytes))
    appeal_text = "\n".join(p.text for p in appeal_doc.paragraphs).replace("\u00a0", " ")
    assert "АПЕЛЛЯЦИОННАЯ ЖАЛОБА" in appeal_text

    # -------------------------------------------------------------------------
    # 5. Проверка юристом перед использованием (Lawyer review gates)
    # -------------------------------------------------------------------------
    # Incomplete required fields block export
    incomplete_request = LegalDraftRequest(
        kind="motion",
        recipient="",  # Missing recipient
        author="Представитель",
        position="Позиция",
        legal_basis="Основания",
        requested_action="Прошу удовлетворить",
        source_document_ids=[doc_docx.document_id],
    )
    incomplete_preview = draft_service.preview(matter_id, incomplete_request)
    assert incomplete_preview.can_export is False
    assert any("Не указан адресат" in w for w in incomplete_preview.warnings)
    with pytest.raises(ValueError, match="Draft has unresolved required fields"):
        render_legal_draft_docx(incomplete_preview)

    # Tampered quote rejection
    fake_statement = report.statements[0].model_copy(
        update={"quote": "Полностью выдуманная цитата, которой нет в документе"}
    )
    tampered_request = LegalDraftRequest(
        kind="motion",
        recipient="Суд",
        author="Заявитель",
        position="Позиция",
        legal_basis="Основания",
        requested_action="Просьба",
        source_document_ids=[doc_docx.document_id, doc_pdf.document_id],
        categorized_statements=[fake_statement],
    )
    with pytest.raises(ValueError, match="failed source verification"):
        draft_service.preview(matter_id, tampered_request)

    # Cross-matter isolation
    foreign_gap = report.gaps[0].model_copy(
        update={"related_citation": "document:other-matter:foreign-doc:page:1:chunk:0"}
    )
    cross_matter_request = LegalDraftRequest(
        kind="motion",
        recipient="Суд",
        author="Заявитель",
        position="Позиция",
        legal_basis="Основания",
        requested_action="Просьба",
        source_document_ids=[doc_docx.document_id, doc_pdf.document_id],
        evidence_gaps=[foreign_gap],
    )
    with pytest.raises(ValueError, match="not in selected documents"):
        draft_service.preview(matter_id, cross_matter_request)

    # Unsigned draft warning in footer
    footer_text = motion_doc.sections[0].footer.paragraphs[0].text
    assert "ПРОЕКТ. НЕ ПОДПИСАН. ТРЕБУЕТ ПРОВЕРКИ ЮРИСТОМ." in footer_text

    corpus.close()
