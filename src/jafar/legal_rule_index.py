from __future__ import annotations

from dataclasses import dataclass

from .holding_rule_normalization import NormalizedLegalRule


@dataclass(frozen=True, slots=True)
class LegalRuleConcept:
    concept_id: str
    canonical_label: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IndexedLegalRule:
    rule: NormalizedLegalRule
    issue_concept_id: str
    rule_concept_id: str


@dataclass(frozen=True, slots=True)
class RuleMatch:
    left_rule_id: str
    right_rule_id: str
    same_issue: bool
    same_rule_concept: bool
    equivalent: bool
    requires_human_review: bool


class LegalRuleOntology:
    """Explicit ontology used to compare legal rules beyond literal wording.

    Aliases are curated inputs, not model guesses. Unknown labels remain unresolved until a
    lawyer or trusted normalization service maps them to a concept.
    """

    def __init__(self, concepts: tuple[LegalRuleConcept, ...]) -> None:
        self._concepts = {item.concept_id: item for item in concepts}
        self._by_label: dict[str, str] = {}
        for item in concepts:
            labels = (item.canonical_label, *item.aliases)
            for label in labels:
                key = self._normalize(label)
                existing = self._by_label.get(key)
                if existing is not None and existing != item.concept_id:
                    raise ValueError(f"Ambiguous ontology label: {label}")
                self._by_label[key] = item.concept_id

    def resolve(self, label: str) -> str | None:
        return self._by_label.get(self._normalize(label))

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().replace("ё", "е").split())


class LegalRuleIndex:
    def __init__(
        self,
        *,
        issue_ontology: LegalRuleOntology,
        rule_ontology: LegalRuleOntology,
    ) -> None:
        self.issue_ontology = issue_ontology
        self.rule_ontology = rule_ontology
        self._items: dict[str, IndexedLegalRule] = {}

    def add(self, rule: NormalizedLegalRule) -> IndexedLegalRule:
        issue_id = self.issue_ontology.resolve(rule.legal_issue)
        rule_id = self.rule_ontology.resolve(rule.rule)
        if issue_id is None or rule_id is None:
            raise ValueError("Rule cannot be indexed until issue and rule concepts are resolved")
        indexed = IndexedLegalRule(
            rule=rule,
            issue_concept_id=issue_id,
            rule_concept_id=rule_id,
        )
        self._items[rule.rule_id] = indexed
        return indexed

    def match(self, left_rule_id: str, right_rule_id: str) -> RuleMatch:
        left = self._items[left_rule_id]
        right = self._items[right_rule_id]
        same_issue = left.issue_concept_id == right.issue_concept_id
        same_rule = left.rule_concept_id == right.rule_concept_id
        equivalent = same_issue and same_rule
        return RuleMatch(
            left_rule_id=left_rule_id,
            right_rule_id=right_rule_id,
            same_issue=same_issue,
            same_rule_concept=same_rule,
            equivalent=equivalent,
            requires_human_review=not equivalent,
        )

    def by_issue(self, issue_concept_id: str) -> tuple[IndexedLegalRule, ...]:
        return tuple(
            item for item in self._items.values() if item.issue_concept_id == issue_concept_id
        )
