from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CaseRecord:
    case_id: str
    case_type: str  # criminal | civil | arbitration
    title: str
    case_number: str | None = None
    status: str = "active"
    parties: tuple[str, ...] = ()
    organizations: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class CaseDatabase:
    """Canonical in-memory contract for criminal, civil and arbitration matters."""

    CASE_TYPES = frozenset({"criminal", "civil", "arbitration"})

    def __init__(self) -> None:
        self._cases: dict[str, CaseRecord] = {}

    def upsert(self, case: CaseRecord) -> CaseRecord:
        if case.case_type not in self.CASE_TYPES:
            raise ValueError(f"Unsupported case type: {case.case_type}")
        self._cases[case.case_id] = case
        return case

    def get(self, case_id: str) -> CaseRecord | None:
        return self._cases.get(case_id)

    def attach_document(self, case_id: str, document_id: str) -> CaseRecord:
        case = self._require(case_id)
        updated = CaseRecord(**{**case.__dict__, "document_ids": tuple(dict.fromkeys((*case.document_ids, document_id)))})
        self._cases[case_id] = updated
        return updated

    def snapshot(self, case_id: str) -> dict[str, Any]:
        case = self._require(case_id)
        return {
            "case_id": case.case_id,
            "case_type": case.case_type,
            "title": case.title,
            "case_number": case.case_number,
            "status": case.status,
            "parties": list(case.parties),
            "organizations": list(case.organizations),
            "document_ids": list(case.document_ids),
            "evidence_ids": list(case.evidence_ids),
            "metadata": case.metadata,
        }

    def _require(self, case_id: str) -> CaseRecord:
        case = self.get(case_id)
        if case is None:
            raise KeyError(f"Unknown case: {case_id}")
        return case
