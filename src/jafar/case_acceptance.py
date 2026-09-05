from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class VerificationStatus(StrEnum):
    OCR_UNVERIFIED = "ocr_unverified"
    TEXT_LAYER_VERIFIED = "text_layer_verified"
    VISUALLY_VERIFIED = "visually_verified"

    @property
    def is_verified(self) -> bool:
        return self is not VerificationStatus.OCR_UNVERIFIED


@dataclass(frozen=True, slots=True)
class CaseObservation:
    field: str
    value: str
    source_id: str
    page: int | None
    verification: VerificationStatus

    @property
    def source_ref(self) -> str:
        suffix = f":page:{self.page}" if self.page is not None else ""
        return f"{self.source_id}{suffix}"


@dataclass(frozen=True, slots=True)
class AcceptanceConflict:
    field: str
    values: tuple[str, ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CaseAcceptanceReport:
    authoritative: dict[str, str]
    conflicts: tuple[AcceptanceConflict, ...]
    unresolved_fields: tuple[str, ...]

    @property
    def requires_human_review(self) -> bool:
        return bool(self.conflicts or self.unresolved_fields)


def evaluate_case_acceptance(observations: Iterable[CaseObservation]) -> CaseAcceptanceReport:
    """Resolve case facts without promoting OCR-only values to authoritative facts.

    Verified source observations may establish an authoritative value. OCR-only observations
    remain unresolved until corroborated. Any disagreement is preserved as a conflict with
    source/page provenance instead of being silently corrected or merged.
    """

    grouped: dict[str, list[CaseObservation]] = defaultdict(list)
    for observation in observations:
        if not observation.field.strip():
            raise ValueError("observation field is required")
        if not observation.value.strip():
            raise ValueError("observation value is required")
        if not observation.source_id.strip():
            raise ValueError("observation source_id is required")
        if observation.page is not None and observation.page <= 0:
            raise ValueError("observation page must be positive")
        grouped[observation.field].append(observation)

    authoritative: dict[str, str] = {}
    conflicts: list[AcceptanceConflict] = []
    unresolved: list[str] = []

    for field, items in grouped.items():
        verified = [item for item in items if item.verification.is_verified]
        verified_values = tuple(dict.fromkeys(item.value for item in verified))
        all_values = tuple(dict.fromkeys(item.value for item in items))

        if len(verified_values) == 1:
            authoritative[field] = verified_values[0]
        elif len(verified_values) > 1:
            unresolved.append(field)
        else:
            unresolved.append(field)

        if len(all_values) > 1:
            conflicts.append(
                AcceptanceConflict(
                    field=field,
                    values=all_values,
                    source_refs=tuple(item.source_ref for item in items),
                )
            )

    return CaseAcceptanceReport(
        authoritative=authoritative,
        conflicts=tuple(conflicts),
        unresolved_fields=tuple(dict.fromkeys(unresolved)),
    )
