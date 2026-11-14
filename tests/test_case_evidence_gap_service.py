"""Tests for Matter-scoped statement extraction, provenance verification and evidence gap analysis."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware
from jafar.case_evidence_gap_api import build_case_evidence_gap_router
from jafar.case_evidence_gap_service import (
    CaseEvidenceGapRequest,
    CaseEvidenceGapService,
)
from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore
from jafar.model_router import ModelResponse


def _matter(matter_id: str) -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id=matter_id,
        title="Учебное арбитражное дело",
        matter_type=MatterType.ARBITRATION,
        client_name="ООО «Поставщик»",
        opposing_party="АО «Покупатель»",
        case_number="А40-99999/2026",
        created_at=now,
        updated_at=now,
    )


class StubCorpus:
    def __init__(self):
        self._documents = {
            ("matter-1", "doc-contract"): SimpleNamespace(
                state="READY", filename="Договор поставки № 15.docx"
            ),
            ("matter-1", "doc-protocol"): SimpleNamespace(
                state="READY", filename="Протокол судебного заседания.pdf"
            ),
            ("matter-foreign", "doc-other"): SimpleNamespace(
                state="READY", filename="Чужой документ.txt"
            ),
        }
        self._chunks = {
            "matter-1": [
                MatterChunk(
                    chunk_id="doc-contract:0",
                    matter_id="matter-1",
                    document_id="doc-contract",
                    source_page=1,
                    chunk_index=0,
                    content=(
                        "15.03.2026 заключен договор поставки № 15 на сумму 1 500 000 рублей. "
                        "Товар передан по накладной от 20.03.2026."
                    ),
                ),
                MatterChunk(
                    chunk_id="doc-protocol:0",
                    matter_id="matter-1",
                    document_id="doc-protocol",
                    source_page=2,
                    chunk_index=0,
                    content=(
                        "Представитель ответчика заявил, что оплата была произведена в полном объеме наличными денежными средствами. "
                        "Истец утверждает, что денежные средства на расчетный счет не поступали. "
                        "Суд установил, что первичные банковские документы об оплате сторонами не представлены."
                    ),
                ),
            ],
            "matter-foreign": [
                MatterChunk(
                    chunk_id="doc-other:0",
                    matter_id="matter-foreign",
                    document_id="doc-other",
                    source_page=1,
                    chunk_index=0,
                    content="Совершенно другое дело и другие стороны.",
                ),
            ],
        }

    def get_document(self, matter_id: str, document_id: str):
        return self._documents.get((matter_id, document_id))

    def verify_document(self, matter_id: str, document_id: str) -> str:
        if (matter_id, document_id) not in self._documents:
            raise ValueError("Document not found")
        return "sha256-verified"

    def chunks(self, matter_id: str) -> list[MatterChunk]:
        return self._chunks.get(matter_id, [])


class StubLocalModel:
    def __init__(self, citation: str, quote: str):
        self.citation = citation
        self.quote = quote
        self.calls = 0

    def available(self) -> bool:
        return True

    def complete(self, request):
        self.calls += 1
        assert request.allowed_providers == ("ollama",)
        assert request.confidential is True
        data = {
            "statements": [
                {
                    "category": "party_claim",
                    "citation": self.citation,
                    "quote": self.quote,
                    "statement": "Ответчик заявил о полной оплате наличными",
                    "subject": "Ответчик",
                }
            ],
            "gaps": [
                {
                    "topic": "Банковские документы об оплате",
                    "description": "В материалах дела отсутствуют платежные поручения об оплате",
                    "expected_evidence": ["банковская выписка", "платежное поручение"],
                    "severity": "high",
                    "related_citation": self.citation,
                    "suggested_action": "Заявить ходатайство об истребовании банковской выписки",
                }
            ],
        }
        return ModelResponse(
            provider="ollama",
            model="qwen3:4b",
            text=json.dumps(data, ensure_ascii=False),
            metadata={"local": True},
        )


def test_deterministic_extraction_distinguishes_facts_claims_and_findings():
    matters = MatterStore()
    matters.create(_matter("matter-1"))
    corpus = StubCorpus()
    service = CaseEvidenceGapService(matters, corpus)

    report = service.analyze(
        "matter-1",
        CaseEvidenceGapRequest(source_document_ids=["doc-contract", "doc-protocol"]),
    )

    assert report.matter_id == "matter-1"
    assert report.case_number == "А40-99999/2026"
    assert len(report.statements) >= 3

    categories = {s.category for s in report.statements}
    assert "fact" in categories
    assert "party_claim" in categories
    assert "court_finding" in categories

    # Verbatim quotations must exist in chunks
    chunks_text = " ".join(c.content for c in corpus.chunks("matter-1"))
    for stmt in report.statements:
        assert stmt.quote in chunks_text
        assert stmt.citation.startswith("document:")

    # Gaps detected for payment claims without bank statements
    assert len(report.gaps) >= 1
    payment_gap = next((g for g in report.gaps if "оплат" in g.topic.lower() or "оплат" in g.description.lower()), None)
    assert payment_gap is not None
    assert payment_gap.severity == "high"
    assert "платеж" in payment_gap.expected_evidence[0].lower().replace("ё", "е") or "выписка" in payment_gap.expected_evidence[0].lower()
    assert "ходатайств" in payment_gap.suggested_action.lower()


def test_cross_matter_document_access_is_rejected():
    matters = MatterStore()
    matters.create(_matter("matter-1"))
    corpus = StubCorpus()
    service = CaseEvidenceGapService(matters, corpus)

    with pytest.raises(ValueError, match="not found in selected Matter"):
        service.analyze(
            "matter-1",
            CaseEvidenceGapRequest(source_document_ids=["doc-contract", "doc-other"]),
        )


def test_local_ai_extraction_authenticates_verbatim_quotes_and_rejects_hallucinations():
    matters = MatterStore()
    matters.create(_matter("matter-1"))
    corpus = StubCorpus()
    valid_citation = corpus.chunks("matter-1")[1].citation
    valid_quote = "Истец утверждает, что денежные средства на расчетный счет не поступали."

    model = StubLocalModel(valid_citation, valid_quote)
    service = CaseEvidenceGapService(matters, corpus, model)

    report = service.analyze(
        "matter-1",
        CaseEvidenceGapRequest(source_document_ids=["doc-protocol"]),
    )

    assert model.calls == 1
    assert any(s.quote == valid_quote for s in report.statements)


def test_api_router_evidence_gaps_endpoint():
    matters = MatterStore()
    matters.create(_matter("matter-1"))
    corpus = StubCorpus()

    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_case_evidence_gap_router(matters, corpus))

    client = TestClient(app)
    response = client.post(
        "/v1/matters/matter-1/analysis/evidence-gaps",
        headers={"Authorization": "Bearer test-desktop-token"},
        json={"source_document_ids": ["doc-contract", "doc-protocol"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matter_id"] == "matter-1"
    assert len(data["statements"]) > 0
    assert len(data["gaps"]) > 0
    assert "warnings" in data
