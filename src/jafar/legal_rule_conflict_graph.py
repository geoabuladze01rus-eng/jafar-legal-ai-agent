from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations

from .holding_rule_normalization import NormalizedLegalRule


class RuleRelationType(StrEnum):
    SAME_RULE = "same_rule"
    NARROWER = "narrower"
    BROADER = "broader"
    EXCEPTION = "exception"
    CONFLICT = "conflict"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RuleRelation:
    left_rule_id: str
    right_rule_id: str
    relation: RuleRelationType
    explanation: str
    verified: bool = False


@dataclass(frozen=True, slots=True)
class RuleConflictEdge:
    left: NormalizedLegalRule
    right: NormalizedLegalRule
    relation: RuleRelationType
    explanation: str
    verified: bool


@dataclass(frozen=True, slots=True)
class LegalRuleConflictReport:
    legal_issue: str
    rules: tuple[NormalizedLegalRule, ...]
    edges: tuple[RuleConflictEdge, ...]
    unresolved_pairs: tuple[tuple[str, str], ...]
    requires_human_review: bool


class LegalRuleConflictGraph:
    """Compare normalized legal rules using only explicit or deterministic relationships.

    Exact semantic-key equality may establish SAME_RULE deterministically. Material
    relationships such as narrower, broader, exception, conflict or superseded must be
    supplied as verified relationships by an upstream legal-review/resolver layer.
    """

    def build(
        self,
        *,
        legal_issue: str,
        rules: tuple[NormalizedLegalRule, ...],
        relations: tuple[RuleRelation, ...] = (),
    ) -> LegalRuleConflictReport:
        normalized_issue = self._norm(legal_issue)
        relevant = tuple(rule for rule in rules if self._norm(rule.legal_issue) == normalized_issue)
        by_id = {rule.rule_id: rule for rule in relevant}

        relation_index: dict[frozenset[str], RuleRelation] = {}
        for relation in relations:
            if not relation.verified:
                continue
            if relation.left_rule_id not in by_id or relation.right_rule_id not in by_id:
                continue
            key = frozenset((relation.left_rule_id, relation.right_rule_id))
            relation_index[key] = relation

        edges: list[RuleConflictEdge] = []
        unresolved: list[tuple[str, str]] = []
        for left, right in combinations(relevant, 2):
            if left.semantic_key == right.semantic_key:
                edges.append(
                    RuleConflictEdge(
                        left=left,
                        right=right,
                        relation=RuleRelationType.SAME_RULE,
                        explanation="Нормализованные правила имеют одинаковый semantic_key.",
                        verified=True,
                    )
                )
                continue

            relation = relation_index.get(frozenset((left.rule_id, right.rule_id)))
            if relation is None:
                unresolved.append((left.rule_id, right.rule_id))
                continue

            edges.append(
                RuleConflictEdge(
                    left=left,
                    right=right,
                    relation=relation.relation,
                    explanation=relation.explanation,
                    verified=True,
                )
            )

        review = bool(unresolved) or any(
            edge.relation in {
                RuleRelationType.CONFLICT,
                RuleRelationType.SUPERSEDED,
                RuleRelationType.EXCEPTION,
            }
            for edge in edges
        )
        return LegalRuleConflictReport(
            legal_issue=legal_issue,
            rules=relevant,
            edges=tuple(edges),
            unresolved_pairs=tuple(unresolved),
            requires_human_review=review,
        )

    @staticmethod
    def release_ready(report: LegalRuleConflictReport) -> bool:
        if report.unresolved_pairs:
            return False
        return not any(
            edge.relation in {RuleRelationType.CONFLICT, RuleRelationType.SUPERSEDED}
            for edge in report.edges
        )

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join(value.casefold().replace("ё", "е").split())
