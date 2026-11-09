"""End-to-end synthetic Matter acceptance: originals → local AI → lawyer note → Word.

No network, user accounts, production projects or real-client data are involved.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

import pytest
from docx import Document

from jafar.claim_review import ClaimReviewRequest, ClaimReviewService
from jafar.desktop_corpus_service import DesktopCorpusService
from jafar.domains import MatterType
from jafar.encrypted_claim_decisions import (
    EncryptedClaimDecisionLedger,
    ReviewDecisionInput,
    derive_decision_ledger_key,
)
from jafar.encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from jafar.encrypted_draft_history import (
    EncryptedDraftHistory, derive_draft_history_key,
)
from jafar.legal_draft_service import LegalDraftRequest, LegalDraftService, render_legal_draft_docx
from jafar.legal_models import Matter
from jafar.matters import MatterStore
from jafar.model_router import ModelResponse


A = "По договору №44 Иванов передал автомобиль 12.05.2026."
B = "По договору №44 Иванов не передал автомобиль 12.05.2026."


class LocalModel:
    def __init__(self, first_citation: str, second_citation: str):
        self.citations = (first_citation, second_citation)
        self.calls = 0

    def available(self):
        return True

    def complete(self, request):
        self.calls += 1
        assert request.allowed_providers == ("ollama",)
        assert request.confidential is True
        data = {
            "claims": [
                {
                    "citation": citation,
                    "quote": quote,
                    "subject": "Иванов",
                    "event_anchor": "договору №44",
                    "action_key": "передача автомобиля",
                    "polarity": polarity,
                }
                for citation, quote, polarity in zip(
                    self.citations, (A, B), ("affirmed", "denied")
                )
            ]
        }
        return ModelResponse(
            provider="ollama",
            model="synthetic-offline-model",
            text=json.dumps(data, ensure_ascii=False),
            metadata={"local": True},
        )


def test_full_private_case_flow_and_superseded_review_protection(tmp_path):
    matters = MatterStore()
    now = datetime.now(timezone.utc)
    matters.create(
        Matter(
            id="training-case", title="Учебное дело",
            matter_type=MatterType.CRIMINAL, created_at=now, updated_at=now,
        )
    )
    master_key = b"K" * 32
    corpus = EncryptedDesktopCorpusStore(
        tmp_path / "corpus.sqlite3", tmp_path / "originals", master_key
    )
    service = DesktopCorpusService(corpus)
    first = service.import_document(
        matter_id="training-case", filename="Акт А.txt",
        media_type="text/plain",
        original_bytes=A.encode("utf-8"), extracted_text=A,
    )
    second = service.import_document(
        matter_id="training-case", filename="Акт Б.txt",
        media_type="text/plain",
        original_bytes=B.encode("utf-8"), extracted_text=B,
    )
    assert len(corpus.chunks("training-case")) == 2
    citations = {
        chunk.document_id: chunk.citation for chunk in corpus.chunks("training-case")
    }
    model = LocalModel(citations[first.document_id], citations[second.document_id])
    report = ClaimReviewService(matters, corpus, model).inspect(
        "training-case",
        ClaimReviewRequest(
            source_document_ids=[first.document_id, second.document_id],
            focus="передача автомобиля по договору №44",
        ),
    )
    assert len(report.possible_differences) == 1

    ledger = EncryptedClaimDecisionLedger(
        tmp_path / "reviews.sqlite3", derive_decision_ledger_key(master_key)
    )
    pair = report.possible_differences[0]
    event = ledger.append(
        "training-case", pair,
        ReviewDecisionInput(
            candidate_id=pair.id, decision="keep_for_work",
            note="Проверить расхождение по датам передачи и подлинники",
        ),
    )
    draft = LegalDraftRequest(
        kind="motion",
        recipient="В учебный суд",
        author="Учебный заявитель",
        position="Прошу проверить представленные материалы.",
        legal_basis="Правовое обоснование сформулировано юристом.",
        requested_action="Истребовать первичные документы.",
        source_document_ids=[first.document_id, second.document_id],
        review_record_ids=[event.record_id],
    )
    history = EncryptedDraftHistory(
        tmp_path / "drafts.sqlite3",
        derive_draft_history_key(master_key),
    )
    saved = history.create("training-case", draft)
    history.close()
    reopened = EncryptedDraftHistory(
        tmp_path / "drafts.sqlite3",
        derive_draft_history_key(master_key),
    )
    restored_draft = reopened.get("training-case", saved.draft_id).draft
    assert restored_draft.review_record_ids == [event.record_id]

    composer = LegalDraftService(matters, corpus, ledger)
    preview = composer.preview("training-case", restored_draft)
    assert preview.can_export
    assert len(preview.review_notes) == 1
    assert model.calls == 1  # No second AI call to compose or export.
    word = Document(BytesIO(render_legal_draft_docx(preview)))
    content = "\n".join(paragraph.text for paragraph in word.paragraphs).replace(
        "\u00a0", " "
    )
    filing, internal = content.split("СЛУЖЕБНЫЙ ЛИСТ ПРОВЕРКИ ИСТОЧНИКОВ", 1)
    assert "Проверить расхождение по датам" not in filing
    assert "Проверить расхождение по датам" in internal
    assert A in internal and B in internal

    # A new reviewer decision supersedes the earlier 'keep for work'.
    ledger.append(
        "training-case", pair,
        ReviewDecisionInput(
            candidate_id=pair.id, decision="dismissed",
            note="Фактический эпизод требует уточнения и иной проверки",
        ),
    )
    with pytest.raises(ValueError, match="superseded"):
        composer.preview("training-case", restored_draft)
    assert corpus.retrieve("foreign-case", "Иванов").results == ()

    reopened.close()
    ledger.close()
    corpus.close()
