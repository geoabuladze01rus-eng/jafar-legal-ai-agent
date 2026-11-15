"""Complex multi-scenario tests for legal analysis integrity, evidence gaps and contradictions."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from jafar.case_evidence_gap_service import (
    CaseEvidenceGapRequest,
    CaseEvidenceGapService,
    _classify_sentence,
)
from jafar.domains import MatterType
from jafar.legal_draft_service import (
    LegalDraftRequest,
    LegalDraftService,
    render_legal_draft_docx,
)
from jafar.legal_models import Matter
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore


def _matter(matter_id: str = "matter-complex") -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id=matter_id,
        title="Сложное судебное дело: поставка оборудования",
        matter_type=MatterType.ARBITRATION,
        client_name="ООО «ПромСнаб»",
        opposing_party="АО «СтройКомплект»",
        case_number="А40-12345/2026",
        created_at=now,
        updated_at=now,
    )


def test_scenario_contradicting_testimony_delivery():
    """Scenario 1: Contradicting testimony on delivery:
    One party affirms delivery/receipt vs opposing party denies delivery/receipt.
    Must produce GroundedContradiction with severity='high' and page tracking."""
    matters = MatterStore()
    matters.create(_matter("matter-contra-deliv"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-supplier:0",
                matter_id="matter-contra-deliv",
                document_id="doc-supplier",
                source_page=2,
                chunk_index=0,
                content="Водитель-экспедитор показал, что товар передан по накладной от 15.02.2026 на складе покупателя.",
            ),
            MatterChunk(
                chunk_id="doc-buyer:0",
                matter_id="matter-contra-deliv",
                document_id="doc-buyer",
                source_page=5,
                chunk_index=0,
                content="Заведующий складом ответчика пояснил, что продукцию не получал и склад в этот день был закрыт.",
            ),
        ],
    )
    service = CaseEvidenceGapService(matters, corpus)
    report = service.analyze(
        "matter-contra-deliv",
        CaseEvidenceGapRequest(source_document_ids=["doc-supplier", "doc-buyer"]),
    )

    assert len(report.contradictions) >= 1
    deliv_contra = next((c for c in report.contradictions if "передачи" in c.topic.lower() or "товар" in c.topic.lower()), None)
    assert deliv_contra is not None
    assert deliv_contra.severity == "high"
    assert 2 in deliv_contra.pages
    assert 5 in deliv_contra.pages
    assert "накладн" in deliv_contra.suggested_inquiry.lower() or "допрос" in deliv_contra.suggested_inquiry.lower()


def test_scenario_contradicting_testimony_payment():
    """Scenario 2: Contradicting claims on payment:
    One party claims payment was made vs plaintiff says money was not received.
    Must detect contradiction and suggest bank statements inquiry."""
    matters = MatterStore()
    matters.create(_matter("matter-contra-pay"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-buyer:0",
                matter_id="matter-contra-pay",
                document_id="doc-buyer",
                source_page=3,
                chunk_index=0,
                content="Ответчик заявил, что перечислил денежные средства по договору в полном объеме.",
            ),
            MatterChunk(
                chunk_id="doc-supplier:0",
                matter_id="matter-contra-pay",
                document_id="doc-supplier",
                source_page=1,
                chunk_index=0,
                content="Истец пояснил, что денежные средства не поступали и долг не погашен.",
            ),
        ],
    )
    service = CaseEvidenceGapService(matters, corpus)
    report = service.analyze(
        "matter-contra-pay",
        CaseEvidenceGapRequest(source_document_ids=["doc-buyer", "doc-supplier"]),
    )

    assert len(report.contradictions) >= 1
    pay_contra = next((c for c in report.contradictions if "оплат" in c.topic.lower() or "расчет" in c.topic.lower()), None)
    assert pay_contra is not None
    assert pay_contra.severity == "high"
    assert "банковскую выписку" in pay_contra.suggested_inquiry.lower()


def test_scenario_incomplete_materials_payment_and_delivery_gaps():
    """Scenario 3: Missing supporting documents:
    Uncorroborated payments or deliveries must generate gaps containing the mandatory
    Russian phrase 'В выбранных материалах подтверждение этой операции не найдено'."""
    matters = MatterStore()
    matters.create(_matter("matter-gaps"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-claim:0",
                matter_id="matter-gaps",
                document_id="doc-claim",
                source_page=1,
                chunk_index=0,
                content=(
                    "Истец требует взыскать задолженность по договору поставки № 15 в сумме 1 200 000 рублей. "
                    "Ответчик возражает и утверждает, что оплатил аванс в размере 500 000 рублей."
                ),
            ),
        ],
    )
    service = CaseEvidenceGapService(matters, corpus)
    report = service.analyze(
        "matter-gaps",
        CaseEvidenceGapRequest(source_document_ids=["doc-claim"]),
    )

    assert len(report.gaps) >= 1
    for gap in report.gaps:
        if "оплат" in gap.topic.lower() or "поставк" in gap.topic.lower():
            assert "В выбранных материалах подтверждение этой операции не найдено" in gap.description


def test_scenario_multiple_contracts_segregated_accounting():
    """Scenario 4: Multiple contracts:
    Payment under contract № 10 cannot clear a debt under contract № 15."""
    matters = MatterStore()
    matters.create(_matter("matter-contracts"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-claim15:0",
                matter_id="matter-contracts",
                document_id="doc-claim15",
                source_page=1,
                chunk_index=0,
                content="Истец требует взыскать задолженность по договору № 15 в размере 800 000 рублей.",
            ),
            MatterChunk(
                chunk_id="doc-pay10:0",
                matter_id="matter-contracts",
                document_id="doc-pay10",
                source_page=2,
                chunk_index=0,
                content="Платежным поручением № 112 от 10.03.2026 перечислены денежные средства по договору № 10.",
            ),
        ],
    )
    service = CaseEvidenceGapService(matters, corpus)
    report = service.analyze(
        "matter-contracts",
        CaseEvidenceGapRequest(source_document_ids=["doc-claim15", "doc-pay10"]),
    )

    # Gap for contract 15 must remain because payment was for contract 10!
    pay_gap = next((g for g in report.gaps if "оплат" in g.topic.lower()), None)
    assert pay_gap is not None
    assert "В выбранных материалах подтверждение этой операции не найдено" in pay_gap.description


def test_scenario_defense_hypothesis_and_legal_assessment_distinction():
    """Scenario 5: Strict distinction of legal conclusions:
    Defense hypotheses ('сторона защиты полагает возможным...', 'не исключено')
    and legal assessments must never be classified as facts."""
    # Sentence-level checks
    stmt_hypo = "Сторона защиты полагает возможным, что повреждение пломбы произошло при погрузке."
    assert _classify_sentence(stmt_hypo) == "defense_hypothesis"

    stmt_hypo2 = "Не исключено, что спорный товар был поставлен неустановленным третьим лицом."
    assert _classify_sentence(stmt_hypo2) == "defense_hypothesis"

    stmt_assessment = "Действия генерального директора представляют собой злоупотребление правом и влекут недействительность договора."
    assert _classify_sentence(stmt_assessment) == "legal_assessment"

    stmt_fact = "Платежным поручением № 50 от 04.05.2026 денежные средства перечислены на счет поставщика."
    assert _classify_sentence(stmt_fact) == "fact"

    stmt_claim = "Истец просит взыскать неустойку в размере 100 000 рублей."
    assert _classify_sentence(stmt_claim) == "party_claim"

    # Corpus extraction check
    matters = MatterStore()
    matters.create(_matter("matter-eval"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-complex:0",
                matter_id="matter-eval",
                document_id="doc-complex",
                source_page=1,
                chunk_index=0,
                content=(
                    "10.01.2026 заключен договор поставки № 15 на сумму 1 000 000 рублей. "
                    "В судебном заседании сторона защиты полагает возможным, что товар не вывозился со склада. "
                    "Истец просит удовлетворить иск в полном объеме. "
                    "Суд постановил: квалифицирует действия ответчика как злоупотребление правом."
                ),
            )
        ],
    )
    service = CaseEvidenceGapService(matters, corpus)
    report = service.analyze("matter-eval", CaseEvidenceGapRequest(source_document_ids=["doc-complex"]))

    categories = {s.quote: s.category for s in report.statements}
    subjects = {s.quote: s.subject for s in report.statements}

    hypo_quote = next(q for q in categories if "сторона защиты полагает" in q.lower())
    assert categories[hypo_quote] == "defense_hypothesis"
    assert subjects[hypo_quote] == "Сторона защиты (версия)"

    fact_quote = next(q for q in categories if "заключен договор" in q.lower())
    assert categories[fact_quote] == "fact"
    assert subjects[fact_quote] == "Обстоятельство дела"


def test_scenario_procedural_document_generation_with_review_sheet():
    """Scenario 6: Preparation of an official procedural document conforming to Russian procedural law:
    - Main body contains applicant's verified position and procedural requests.
    - Contradictions, evidence gaps, and classified statements are placed in the internal review sheet.
    - Word document (.docx) generation succeeds and embeds review sections with appropriate warnings."""
    matters = MatterStore()
    matters.create(_matter("matter-doc"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-1:0",
                matter_id="matter-doc",
                document_id="doc-1",
                source_page=1,
                chunk_index=0,
                content="15.02.2026 заключен договор поставки № 15 между ООО «ПромСнаб» и АО «СтройКомплект».",
            ),
            MatterChunk(
                chunk_id="doc-2:0",
                matter_id="matter-doc",
                document_id="doc-2",
                source_page=4,
                chunk_index=0,
                content="Ответчик заявил, что товар не получал и накладную не подписывал.",
            ),
        ],
    )
    gap_service = CaseEvidenceGapService(matters, corpus)
    gap_report = gap_service.analyze("matter-doc", CaseEvidenceGapRequest(source_document_ids=["doc-1", "doc-2"]))

    draft_service = LegalDraftService(matters, corpus)
    request = LegalDraftRequest(
        kind="motion",
        recipient="Арбитражный суд города Москвы",
        author="ООО «ПромСнаб» (Истец)",
        position=(
            "В производстве суда находится дело № А40-12345/2026 по иску о взыскании задолженности по договору поставки. "
            "Ответчик отрицает факт получения продукции. В связи с необходимостью установления действительных обстоятельств "
            "требуется истребование первичных документов."
        ),
        legal_basis="Статья 66 Арбитражного процессуального кодекса Российской Федерации",
        requested_action=(
            "Истребовать у АО «СтройКомплект» подлинники товарных накладных, журналы въезда транспортных средств "
            "на складскую территорию за период с 15.02.2026 по 28.02.2026."
        ),
        source_document_ids=["doc-1", "doc-2"],
        categorized_statements=gap_report.statements,
        evidence_gaps=gap_report.gaps,
        contradictions=gap_report.contradictions,
    )

    preview = draft_service.preview("matter-doc", request)
    assert preview.can_export is True
    assert len(preview.categorized_statements) >= 2
    assert len(preview.evidence_gaps) >= 1
    assert any("В служебный лист включены выявленные противоречия" in w or "ходатайств" in w for w in preview.warnings)

    # Render DOCX bytes
    docx_bytes = render_legal_draft_docx(preview)
    assert len(docx_bytes) > 2000
    assert docx_bytes.startswith(b"PK")  # Valid zip / DOCX signature


def test_scenario_analysis_mode_selection_and_explicit_reporting():
    """Scenario 7: Explicit analysis method reporting and failure modes (item 1)."""
    matters = MatterStore()
    matters.create(_matter("matter-mode"))

    corpus = SimpleNamespace(
        get_document=lambda m, d: SimpleNamespace(state="READY", filename=f"{d}.pdf"),
        verify_document=lambda m, d: "sha256-verified",
        chunks=lambda m: [
            MatterChunk(
                chunk_id="doc-1:0",
                matter_id="matter-mode",
                document_id="doc-1",
                source_page=1,
                chunk_index=0,
                content="20.02.2026 заключен договор поставки № 88 на сумму 500 000 рублей.",
            ),
        ],
    )
    service = CaseEvidenceGapService(matters, corpus, model=None)

    # 1. Deterministic mode explicitly reports deterministic method
    rep_det = service.analyze(
        "matter-mode",
        CaseEvidenceGapRequest(source_document_ids=["doc-1"], analysis_mode="deterministic"),
    )
    assert rep_det.analysis_method_used == "deterministic"
    assert "детерминированный" in rep_det.analysis_details.lower()

    # 2. Local AI mode with no Ollama running MUST raise explicit error rather than silently fallback
    with pytest.raises(ValueError, match="Ollama недоступна"):
        service.analyze(
            "matter-mode",
            CaseEvidenceGapRequest(source_document_ids=["doc-1"], analysis_mode="local_ai"),
        )
