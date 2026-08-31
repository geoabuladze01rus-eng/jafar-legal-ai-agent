from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .matter_rag import MatterChunk


_UNCERTAIN_MARKERS = (
    "возможно",
    "вероятно",
    "предположительно",
    "не исключает",
    "мог ",
    "могла ",
    "могло ",
    "не помн",
)
_NEGATION_RE = re.compile(r"\bне\s+", re.IGNORECASE)
_WORD_RE = re.compile(r"[а-яёa-z]+", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<!\w)\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?(?!\w)")
_DATE_RE = re.compile(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b")
_AMBIGUOUS_OCR_NUMBER_RE = re.compile(r"(?:\b[IlIОO]\s*\d{3}|\d\s*[IlIОO]\b)")
_STOP_WORDS = {
    "и",
    "в",
    "во",
    "на",
    "о",
    "об",
    "что",
    "это",
    "был",
    "была",
    "было",
    "деньги",
}


@dataclass(frozen=True, slots=True)
class DocumentClaim:
    matter_id: str
    document_id: str
    source_page: int
    chunk_index: int
    topic: str
    statement: str
    position: str
    owner_user_id: str | None = None
    stable_chunk_id: str | None = None
    source_section: str | None = None
    source_start: int | None = None
    source_end: int | None = None
    subject: str | None = None
    object: str | None = None
    event_time: str | None = None
    statement_time: str | None = None
    document_date: str | None = None
    document_kind: str | None = None
    witness_id: str | None = None
    modality: str = "asserted"
    ocr_confidence: float | None = None

    @property
    def evidence_id(self) -> str:
        if self.stable_chunk_id:
            return (
                f"document:{self.document_id}:stable:{self.stable_chunk_id}"
                f":page:{self.source_page}"
            )
        return f"document:{self.document_id}:page:{self.source_page}:chunk:{self.chunk_index}"

    @property
    def source_excerpt(self) -> str:
        return self.statement.strip()


@dataclass(frozen=True, slots=True)
class GroundedContradiction:
    topic: str
    left: DocumentClaim
    right: DocumentClaim
    kind: str
    label: str
    confidence: float
    explanation: str
    is_model_conclusion: bool = True
    requires_lawyer_review: bool = True

    @property
    def evidence_ids(self) -> tuple[str, str]:
        return (self.left.evidence_id, self.right.evidence_id)


@dataclass(frozen=True, slots=True)
class CrossDocumentReport:
    matter_id: str
    contradictions: tuple[GroundedContradiction, ...]
    documents_considered: tuple[str, ...]
    owner_user_id: str | None = None
    read_only: bool = True


class CrossDocumentContradictionService:
    """Produce grounded review candidates without persisting or deciding legal truth."""

    def compare(
        self,
        *,
        owner_user_id: str | None = None,
        matter_id: str,
        claims: Iterable[DocumentClaim],
    ) -> CrossDocumentReport:
        if owner_user_id is not None and not owner_user_id.strip():
            raise ValueError("owner_user_id is required")
        if not matter_id.strip():
            raise ValueError("matter_id is required")
        supplied_claims = list(claims)
        explicit_owners = {claim.owner_user_id for claim in supplied_claims if claim.owner_user_id}
        if owner_user_id is None and len(explicit_owners) > 1:
            raise ValueError("owner_user_id is required for mixed-owner claims")
        effective_owner = owner_user_id or next(iter(explicit_owners), None)
        scoped = self._deduplicate(
            claim
            for claim in supplied_claims
            if claim.matter_id == matter_id
            and (
                claim.owner_user_id == effective_owner
                if effective_owner is not None
                else claim.owner_user_id is None
            )
        )
        documents = tuple(sorted({claim.document_id for claim in scoped}))
        contradictions = [
            finding
            for left, right in combinations(scoped, 2)
            if left.document_id != right.document_id
            if (
                finding := self._compare_pair(
                    left,
                    right,
                    require_explicit_context=owner_user_id is not None,
                )
            )
            is not None
        ]
        contradictions.sort(key=lambda item: item.evidence_ids)
        return CrossDocumentReport(
            owner_user_id=effective_owner,
            matter_id=matter_id,
            contradictions=tuple(contradictions),
            documents_considered=documents,
        )

    @staticmethod
    def _deduplicate(claims: Iterable[DocumentClaim]) -> list[DocumentClaim]:
        unique: dict[tuple[str, ...], DocumentClaim] = {}
        for claim in claims:
            content_key = " ".join(claim.statement.casefold().split())
            unique.setdefault(
                (
                    content_key,
                    " ".join(claim.position.casefold().split()),
                    " ".join(claim.topic.casefold().split()),
                    " ".join((claim.subject or "").casefold().split()),
                    " ".join((claim.object or "").casefold().split()),
                    " ".join((claim.event_time or "").casefold().split()),
                ),
                claim,
            )
        return sorted(unique.values(), key=lambda claim: (claim.document_id, claim.evidence_id))

    def _compare_pair(
        self,
        left: DocumentClaim,
        right: DocumentClaim,
        *,
        require_explicit_context: bool,
    ) -> GroundedContradiction | None:
        if self._normalized(left.topic) != self._normalized(right.topic):
            return None
        if not self._same_optional_context(left.subject, right.subject):
            return None
        if not self._same_optional_context(left.object, right.object):
            return None
        if not self._same_optional_context(left.event_time, right.event_time):
            return None
        if require_explicit_context and not self._shared_explicit_context(left, right):
            return None
        if self._different_inline_dates(left.statement, right.statement):
            return None
        if self._is_uncertain(left) or self._is_uncertain(right):
            return None
        if self._has_ocr_number_uncertainty(left) or self._has_ocr_number_uncertainty(right):
            return None

        kind: str | None = None
        confidence = 0.0
        explanation = ""
        if self._direct_negation(left.position or left.statement, right.position or right.statement):
            kind = "direct_negation"
            confidence = 0.93
            explanation = "Один источник прямо отрицает утверждение другого в совпадающем контексте."
        else:
            left_numbers = self._numeric_values(left)
            right_numbers = self._numeric_values(right)
            if left_numbers and right_numbers and left_numbers != right_numbers:
                kind = "numeric_mismatch"
                confidence = 0.88
                explanation = "Источники указывают разные числовые значения для одного контекста."
            elif (
                self._normalized(left.modality) == "categorical"
                and self._normalized(right.modality) == "categorical"
                and self._strong_context(left, right)
                and self._normalized(left.position) != self._normalized(right.position)
            ):
                kind = "position_conflict"
                confidence = 0.72
                explanation = "Источники занимают несовместимые позиции в явно совпадающем контексте."
        if kind is None:
            return None

        label = "potential contradiction"
        if self._testimony_changed(left, right):
            kind = "testimony_change"
            label = "potential change in testimony"
            confidence = min(confidence, 0.85)
        confidence *= min(self._ocr_factor(left), self._ocr_factor(right))
        if confidence < 0.55:
            return None
        return GroundedContradiction(
            topic=left.topic,
            left=left,
            right=right,
            kind=kind,
            label=label,
            confidence=round(confidence, 3),
            explanation=explanation,
        )

    @staticmethod
    def _normalized(value: str | None) -> str:
        return " ".join((value or "").casefold().split())

    @classmethod
    def _same_optional_context(cls, left: str | None, right: str | None) -> bool:
        if left is None and right is None:
            return True
        if left is None or right is None:
            return False
        return cls._normalized(left) == cls._normalized(right)

    @classmethod
    def _is_uncertain(cls, claim: DocumentClaim) -> bool:
        if cls._normalized(claim.modality) not in {
            "",
            "asserted",
            "categorical",
            "точно",
            "confirmed",
        }:
            return True
        statement = cls._normalized(claim.statement)
        return any(marker in statement for marker in _UNCERTAIN_MARKERS)

    @classmethod
    def _direct_negation(cls, left: str, right: str) -> bool:
        left_normalized = cls._normalized(left)
        right_normalized = cls._normalized(right)
        left_negative = bool(_NEGATION_RE.search(left_normalized))
        right_negative = bool(_NEGATION_RE.search(right_normalized))
        if left_negative == right_negative:
            return False
        left_signature = cls._action_signature(left_normalized)
        right_signature = cls._action_signature(right_normalized)
        if not left_signature or not right_signature:
            return False
        overlap = len(left_signature & right_signature)
        return overlap >= max(1, min(len(left_signature), len(right_signature)) - 1)

    @staticmethod
    def _action_signature(value: str) -> set[str]:
        without_negation = _NEGATION_RE.sub("", value)
        return {
            token[:5]
            for token in _WORD_RE.findall(without_negation)
            if token not in _STOP_WORDS and len(token) > 2
        }

    @classmethod
    def _numeric_values(cls, claim: DocumentClaim) -> tuple[str, ...]:
        if _AMBIGUOUS_OCR_NUMBER_RE.search(claim.statement):
            return ()
        if claim.ocr_confidence is not None and claim.ocr_confidence < 0.9:
            return ()
        return tuple(match.group().replace(" ", "").replace("\u00a0", "") for match in _NUMBER_RE.finditer(claim.position or claim.statement))

    @staticmethod
    def _has_ocr_number_uncertainty(claim: DocumentClaim) -> bool:
        contains_number = bool(_NUMBER_RE.search(claim.statement) or _AMBIGUOUS_OCR_NUMBER_RE.search(claim.statement))
        return bool(
            _AMBIGUOUS_OCR_NUMBER_RE.search(claim.statement)
            or (contains_number and claim.ocr_confidence is not None and claim.ocr_confidence < 0.9)
        )

    @staticmethod
    def _different_inline_dates(left: str, right: str) -> bool:
        left_dates = set(_DATE_RE.findall(left))
        right_dates = set(_DATE_RE.findall(right))
        return bool(left_dates and right_dates and left_dates != right_dates)

    @classmethod
    def _strong_context(cls, left: DocumentClaim, right: DocumentClaim) -> bool:
        same_subject = bool(left.subject and right.subject and cls._same_optional_context(left.subject, right.subject))
        same_object = bool(left.object and right.object and cls._same_optional_context(left.object, right.object))
        same_time = bool(
            left.event_time and right.event_time and cls._same_optional_context(left.event_time, right.event_time)
        )
        return same_time and (same_subject or same_object)

    @classmethod
    def _shared_explicit_context(cls, left: DocumentClaim, right: DocumentClaim) -> bool:
        return any(
            left_value
            and right_value
            and cls._same_optional_context(left_value, right_value)
            for left_value, right_value in (
                (left.subject, right.subject),
                (left.object, right.object),
                (left.event_time, right.event_time),
            )
        )

    @classmethod
    def _testimony_changed(cls, left: DocumentClaim, right: DocumentClaim) -> bool:
        same_witness = bool(
            left.witness_id
            and right.witness_id
            and cls._same_optional_context(left.witness_id, right.witness_id)
        )
        return bool(same_witness and left.statement_time and right.statement_time and left.statement_time != right.statement_time)

    @staticmethod
    def _ocr_factor(claim: DocumentClaim) -> float:
        if claim.ocr_confidence is None:
            return 1.0
        return max(0.0, min(claim.ocr_confidence, 1.0))

    @staticmethod
    def claims_from_chunks(
        *,
        chunks: Iterable[MatterChunk],
        topic: str,
        position: str,
        subject: str | None = None,
        object: str | None = None,
        event_time: str | None = None,
    ) -> tuple[DocumentClaim, ...]:
        return tuple(
            DocumentClaim(
                owner_user_id=chunk.owner_user_id,
                matter_id=chunk.matter_id,
                document_id=chunk.document_id,
                source_page=chunk.source_page,
                chunk_index=chunk.chunk_index,
                stable_chunk_id=chunk.stable_chunk_id,
                source_section=chunk.source_section,
                source_start=chunk.source_start,
                source_end=chunk.source_end,
                topic=topic,
                statement=chunk.content,
                position=position,
                subject=subject,
                object=object,
                event_time=event_time,
            )
            for chunk in chunks
            if chunk.content.strip()
        )
