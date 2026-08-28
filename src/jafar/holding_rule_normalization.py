from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from .legal_holding_verifier import HoldingStatus, HoldingVerificationResult


@dataclass(frozen=True, slots=True)
class RuleNormalizationInput:
    holding: HoldingVerificationResult
    authority_id: str
    legal_issue: str
    rule: str
    conditions: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    consequence: str = ""
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NormalizedLegalRule:
    rule_id: str
    authority_id: str
    legal_issue: str
    rule: str
    conditions: tuple[str, ...]
    exceptions: tuple[str, ...]
    consequence: str
    source_refs: tuple[str, ...]
    semantic_key: str
    source_holding_text: str
    requires_lawyer_review: bool = True


class HoldingRuleNormalizer:
    """Normalize verified holdings into stable rule structures without inventing doctrine.

    Legal issue, rule, conditions, exceptions and consequence must be supplied explicitly by
    an upstream extraction/review step. This class only validates and normalizes those fields.
    It never infers a missing rule from the holding text.
    """

    _SPACE = re.compile(r"\s+")
    _PUNCT = re.compile(r"[^0-9a-zа-яё]+", re.IGNORECASE)

    def normalize(self, item: RuleNormalizationInput) -> NormalizedLegalRule:
        if item.holding.status != HoldingStatus.VERIFIED_HOLDING:
            raise ValueError("Only verified holdings may enter rule normalization")
        if not item.holding.may_enter_holding_base:
            raise ValueError("Holding is not approved for the holding base")

        issue = self._clean_required(item.legal_issue, "legal_issue")
        rule = self._clean_required(item.rule, "rule")
        conditions = self._clean_many(item.conditions)
        exceptions = self._clean_many(item.exceptions)
        consequence = self._clean_optional(item.consequence)
        source_refs = tuple(dict.fromkeys(ref.strip() for ref in item.source_refs if ref.strip()))

        semantic_key = self.semantic_key(
            legal_issue=issue,
            rule=rule,
            conditions=conditions,
            exceptions=exceptions,
            consequence=consequence,
        )
        return NormalizedLegalRule(
            rule_id=f"rule:{item.authority_id}:{semantic_key[:16]}",
            authority_id=item.authority_id,
            legal_issue=issue,
            rule=rule,
            conditions=conditions,
            exceptions=exceptions,
            consequence=consequence,
            source_refs=source_refs,
            semantic_key=semantic_key,
            source_holding_text=" ".join(item.holding.proposition.text.split()),
        )

    @classmethod
    def semantic_key(
        cls,
        *,
        legal_issue: str,
        rule: str,
        conditions: tuple[str, ...] = (),
        exceptions: tuple[str, ...] = (),
        consequence: str = "",
    ) -> str:
        parts = [
            cls._semantic_text(legal_issue),
            cls._semantic_text(rule),
            "|".join(sorted(cls._semantic_text(value) for value in conditions)),
            "|".join(sorted(cls._semantic_text(value) for value in exceptions)),
            cls._semantic_text(consequence),
        ]
        return sha256("\n".join(parts).encode("utf-8")).hexdigest()

    @classmethod
    def equivalent(cls, left: NormalizedLegalRule, right: NormalizedLegalRule) -> bool:
        return left.semantic_key == right.semantic_key

    @classmethod
    def _clean_required(cls, value: str, field: str) -> str:
        cleaned = cls._clean_optional(value)
        if not cleaned:
            raise ValueError(f"{field} is required; the normalizer must not infer it")
        return cleaned

    @classmethod
    def _clean_optional(cls, value: str) -> str:
        return cls._SPACE.sub(" ", value.strip())

    @classmethod
    def _clean_many(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = [cls._clean_optional(value) for value in values]
        return tuple(dict.fromkeys(value for value in cleaned if value))

    @classmethod
    def _semantic_text(cls, value: str) -> str:
        normalized = value.casefold().replace("ё", "е")
        normalized = cls._PUNCT.sub(" ", normalized)
        return cls._SPACE.sub(" ", normalized).strip()
