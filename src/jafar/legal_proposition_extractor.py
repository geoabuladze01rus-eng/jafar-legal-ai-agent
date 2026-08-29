from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from .case_law_document import CaseLawDocument


@dataclass(frozen=True, slots=True)
class LegalReferenceCandidate:
    raw_text: str
    kind: str


@dataclass(frozen=True, slots=True)
class PropositionCandidate:
    text: str
    confidence: float
    rationale: str


@dataclass(frozen=True, slots=True)
class CaseLawEnrichment:
    citation_candidates: tuple[str, ...]
    date_candidates: tuple[date, ...]
    legal_reference_candidates: tuple[LegalReferenceCandidate, ...]
    topic_candidates: tuple[str, ...]
    proposition_candidates: tuple[PropositionCandidate, ...]
    document_text_fingerprint: str
    requires_human_review: bool = True


class LegalPropositionExtractor:
    """Extract candidate metadata and propositions without promoting them to verified law."""

    ARTICLE_PATTERN = re.compile(
        r"(?:стать[ьяи]|ст\.)\s*\d+(?:\.\d+)?(?:\s*(?:част[ьи]|ч\.)\s*\d+)?\s*(?:УПК|УК|ГК|АПК|ГПК|КАС|КоАП)\s*РФ",
        re.IGNORECASE,
    )
    CASE_PATTERN = re.compile(r"(?:дел[оа]\s*№\s*|№\s*)[А-ЯA-Z0-9\-–/\.]+", re.IGNORECASE)
    DATE_PATTERN = re.compile(r"\b(\d{1,2})[.](\d{1,2})[.](\d{4})\b")
    PROPOSITION_MARKERS = (
        "суд указал",
        "верховный суд указал",
        "судебная коллегия указала",
        "суд пришел к выводу",
        "суд пришёл к выводу",
        "подлежит",
        "не допускается",
        "не может",
        "следует исходить",
    )

    def extract(self, document: CaseLawDocument) -> CaseLawEnrichment:
        text = document.text
        refs = self._legal_refs(text)
        dates = self._dates(text)
        citations = self._citations(text)
        topics = self._topics(text, refs)
        propositions = self._propositions(text)
        return CaseLawEnrichment(
            citation_candidates=citations,
            date_candidates=dates,
            legal_reference_candidates=refs,
            topic_candidates=topics,
            proposition_candidates=propositions,
            document_text_fingerprint=document.text_fingerprint,
            requires_human_review=True,
        )

    def snapshot(self, enrichment: CaseLawEnrichment) -> dict[str, Any]:
        return {
            "citation_candidates": list(enrichment.citation_candidates),
            "date_candidates": [item.isoformat() for item in enrichment.date_candidates],
            "legal_reference_candidates": [
                {"raw_text": item.raw_text, "kind": item.kind}
                for item in enrichment.legal_reference_candidates
            ],
            "topic_candidates": list(enrichment.topic_candidates),
            "proposition_candidates": [
                {"text": item.text, "confidence": item.confidence, "rationale": item.rationale}
                for item in enrichment.proposition_candidates
            ],
            "document_text_fingerprint": enrichment.document_text_fingerprint,
            "requires_human_review": enrichment.requires_human_review,
        }

    def _legal_refs(self, text: str) -> tuple[LegalReferenceCandidate, ...]:
        found = [
            LegalReferenceCandidate(raw_text=match.group(0), kind="statute_article")
            for match in self.ARTICLE_PATTERN.finditer(text)
        ]
        unique: dict[str, LegalReferenceCandidate] = {}
        for item in found:
            unique[item.raw_text.casefold()] = item
        return tuple(unique.values())

    def _dates(self, text: str) -> tuple[date, ...]:
        result: list[date] = []
        for match in self.DATE_PATTERN.finditer(text):
            day, month, year = (int(value) for value in match.groups())
            try:
                result.append(date(year, month, day))
            except ValueError:
                continue
        return tuple(dict.fromkeys(result))

    def _citations(self, text: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(match.group(0) for match in self.CASE_PATTERN.finditer(text)))

    @staticmethod
    def _topics(text: str, refs: tuple[LegalReferenceCandidate, ...]) -> tuple[str, ...]:
        candidates: list[str] = []
        lowered = text.casefold()
        rules = {
            "допустимость доказательств": ("недопустим", "допустимост", "ст. 75 упк", "статья 75 упк"),
            "сроки уголовного судопроизводства": ("разумный срок", "ст. 6.1 упк", "статья 6.1 упк"),
            "меры пресечения": ("мера пресечения", "домашний арест", "заключение под стражу"),
            "кассационное производство": ("кассацион",),
            "апелляционное производство": ("апелляцион",),
            "оценка доказательств": ("оценк доказательств", "достоверност", "достаточност"),
        }
        for topic, markers in rules.items():
            if any(marker in lowered for marker in markers):
                candidates.append(topic)
        for ref in refs:
            candidates.append(f"применение {ref.raw_text}")
        return tuple(dict.fromkeys(candidates))

    def _propositions(self, text: str) -> tuple[PropositionCandidate, ...]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        result: list[PropositionCandidate] = []
        for sentence in sentences:
            normalized = " ".join(sentence.split())
            if len(normalized) < 40 or len(normalized) > 700:
                continue
            lowered = normalized.casefold()
            marker = next((item for item in self.PROPOSITION_MARKERS if item in lowered), None)
            if marker is None:
                continue
            confidence = 0.45
            if "верховный суд" in lowered or "судебная коллегия" in lowered:
                confidence = 0.55
            result.append(
                PropositionCandidate(
                    text=normalized,
                    confidence=confidence,
                    rationale=f"Кандидат выделен по маркеру судебного вывода: {marker}.",
                )
            )
        return tuple(result[:20])
