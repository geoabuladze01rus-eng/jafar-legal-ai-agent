from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

VALID_ENTITY_QUERY_TYPES = {"name", "inn", "ogrn", "kpp"}
_KPP_RE = re.compile(r"^[0-9]{4}[0-9A-Z]{2}[0-9]{3}$")


def _weighted_control_digit(value: str, weights: tuple[int, ...]) -> int:
    return sum(int(digit) * weight for digit, weight in zip(value, weights, strict=True)) % 11 % 10


def valid_inn(value: str) -> bool:
    if not value.isdigit():
        return False
    if len(value) == 10:
        weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
        return _weighted_control_digit(value[:9], weights) == int(value[9])
    if len(value) == 12:
        first_weights = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        second_weights = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        first = _weighted_control_digit(value[:10], first_weights)
        second = _weighted_control_digit(value[:11], second_weights)
        return first == int(value[10]) and second == int(value[11])
    return False


def valid_ogrn(value: str) -> bool:
    if not value.isdigit():
        return False
    if len(value) == 13:
        return int(value[:12]) % 11 % 10 == int(value[12])
    if len(value) == 15:
        return int(value[:14]) % 13 % 10 == int(value[14])
    return False


def valid_kpp(value: str) -> bool:
    return bool(_KPP_RE.fullmatch(value.upper()))


@dataclass(frozen=True, slots=True, init=False)
class EntityQuery:
    """Canonical legal-entity query used by API, adapters and intelligence.

    Russian identifiers are validated before they can enter the source pipeline. INN and
    OGRN/OGRNIP include control-digit validation. KPP has no checksum, so its structural
    form is validated instead. Numeric auto-detected identifiers fail closed on a bad
    checksum rather than being silently reinterpreted as an organization name.
    """

    value: str
    query_type: str

    def __init__(
        self,
        value: str | None = None,
        query_type: str = "name",
        *,
        name: str | None = None,
        inn: str | None = None,
        ogrn: str | None = None,
        kpp: str | None = None,
    ) -> None:
        identifiers = {
            "name": name,
            "inn": inn,
            "ogrn": ogrn,
            "kpp": kpp,
        }
        supplied_identifiers = [
            (kind, raw)
            for kind, raw in identifiers.items()
            if raw is not None and str(raw).strip()
        ]
        if value is not None and supplied_identifiers:
            raise ValueError("entity_query_ambiguous_input")
        if len(supplied_identifiers) > 1:
            raise ValueError("entity_query_requires_single_identifier")

        if supplied_identifiers:
            normalized_type, raw_value = supplied_identifiers[0]
        else:
            normalized_type = query_type.strip().casefold()
            raw_value = value

        if normalized_type not in VALID_ENTITY_QUERY_TYPES:
            raise ValueError("unsupported_entity_query_type")
        normalized_value = str(raw_value or "").strip()
        if not normalized_value:
            raise ValueError("entity_query_value_required")
        if len(normalized_value) > 500:
            raise ValueError("entity_query_value_too_long")

        if normalized_type == "inn":
            if not valid_inn(normalized_value):
                raise ValueError("invalid_inn")
        elif normalized_type == "ogrn":
            if not valid_ogrn(normalized_value):
                raise ValueError("invalid_ogrn")
        elif normalized_type == "kpp":
            normalized_value = normalized_value.upper()
            if not valid_kpp(normalized_value):
                raise ValueError("invalid_kpp")

        object.__setattr__(self, "value", normalized_value)
        object.__setattr__(self, "query_type", normalized_type)

    @classmethod
    def infer(cls, value: str) -> EntityQuery:
        normalized = value.strip()
        if normalized.isdigit() and len(normalized) in {10, 12}:
            return cls(normalized, "inn")
        if normalized.isdigit() and len(normalized) in {13, 15}:
            return cls(normalized, "ogrn")
        if len(normalized) == 9 and valid_kpp(normalized):
            return cls(normalized, "kpp")
        return cls(normalized, "name")

    @property
    def name(self) -> str | None:
        return self.value if self.query_type == "name" else None

    @property
    def inn(self) -> str | None:
        return self.value if self.query_type == "inn" else None

    @property
    def ogrn(self) -> str | None:
        return self.value if self.query_type == "ogrn" else None

    @property
    def kpp(self) -> str | None:
        return self.value if self.query_type == "kpp" else None

    def normalized(self) -> EntityQuery:
        return self


@dataclass(frozen=True)
class SourceFinding:
    source_key: str
    status: str
    title: str
    details: dict[str, Any]
    source_url: str | None = None
    confidence: float = 0.0


class EntitySource(Protocol):
    source_key: str

    def lookup(self, query: EntityQuery) -> SourceFinding: ...


@dataclass(frozen=True)
class RiskFinding:
    code: str
    title: str
    severity: str
    rationale: str
    source_keys: tuple[str, ...]


@dataclass(frozen=True)
class InvestigationResult:
    query: EntityQuery
    profile: dict[str, Any]


class LegalEntityIntelligence:
    """Source-neutral public/free-source aggregator for Russian legal entities."""

    def __init__(self, sources: list[EntitySource] | None = None) -> None:
        self.sources = sources or []

    def investigate(self, query: EntityQuery) -> dict[str, Any]:
        q = query.normalized()
        findings = []
        for source in self.sources:
            try:
                findings.append(source.lookup(q))
            except Exception as exc:
                findings.append(
                    SourceFinding(
                        source.source_key,
                        "error",
                        source.source_key,
                        error_to_details(exc),
                    )
                )
        return self.build_profile(findings, trusted=True)

    def build_profile(
        self,
        findings: list[SourceFinding],
        *,
        trusted: bool = False,
    ) -> dict[str, Any]:
        """Aggregate findings while keeping source trust explicit.

        The safe default is untrusted. Only findings that explicitly crossed a server-owned,
        validated source pipeline may set ``trusted=True`` and produce a legal/entity risk score.
        Caller-supplied or future call-site findings therefore fail closed if the trust flag is
        accidentally omitted.
        """

        risks = self._score(findings) if trusted else []
        return {
            "sources_checked": len(findings),
            "sources_found": sum(f.status == "found" for f in findings),
            "sources_negative": sum(f.status == "negative" for f in findings),
            "sources_no_data": sum(f.status == "no_data" for f in findings),
            "sources_error": sum(f.status == "error" for f in findings),
            "source_trust": "server_verified" if trusted else "client_supplied_unverified",
            "risk_assessment_status": "scored" if trusted else "not_scored_unverified_input",
            "risk_score": self._score_value(risks) if trusted else None,
            "risk_level": self._risk_level(risks) if trusted else "unverified",
            "risks": [asdict(r) for r in risks],
            "findings": [asdict(f) for f in findings],
            "disclaimer": (
                "Отсутствие сведений в конкретном публичном источнике не доказывает "
                "отсутствие обстоятельства."
            ),
        }

    def _score(self, findings: list[SourceFinding]) -> list[RiskFinding]:
        risks: list[RiskFinding] = []
        by_source = {f.source_key: f for f in findings}
        fedresurs = by_source.get("fedresurs")
        if fedresurs and fedresurs.status == "found" and fedresurs.details.get("bankruptcy"):
            risks.append(
                RiskFinding(
                    "bankruptcy",
                    "Признаки банкротства",
                    "critical",
                    "Обнаружены сведения о банкротстве.",
                    ("fedresurs",),
                )
            )
        fssp = by_source.get("fssp")
        if fssp and fssp.status == "found":
            amount = fssp.details.get("debt_amount")
            if isinstance(amount, (int, float)) and amount > 0:
                risks.append(
                    RiskFinding(
                        "enforcement_debt",
                        "Исполнительные производства",
                        "high" if amount >= 1_000_000 else "medium",
                        f"Обнаружена задолженность: {amount}.",
                        ("fssp",),
                    )
                )
        kad = by_source.get("kad")
        if kad and kad.status == "found":
            count = kad.details.get("case_count")
            if isinstance(count, int) and count > 0:
                risks.append(
                    RiskFinding(
                        "arbitration_activity",
                        "Арбитражная активность",
                        "high" if count >= 20 else "medium",
                        f"Найдено дел: {count}.",
                        ("kad",),
                    )
                )
        finance = by_source.get("bo")
        if finance and finance.status == "found":
            loss = finance.details.get("net_loss")
            if isinstance(loss, (int, float)) and loss > 0:
                risks.append(
                    RiskFinding(
                        "financial_loss",
                        "Убыток по отчётности",
                        "medium",
                        f"Зафиксирован убыток: {loss}.",
                        ("bo",),
                    )
                )
        return risks

    @staticmethod
    def _score_value(risks: list[RiskFinding]) -> int:
        return min(
            100,
            sum(
                {"low": 10, "medium": 25, "high": 50, "critical": 80}[r.severity]
                for r in risks
            ),
        )

    @staticmethod
    def _risk_level(risks: list[RiskFinding]) -> str:
        if any(r.severity == "critical" for r in risks):
            return "critical"
        if any(r.severity == "high" for r in risks):
            return "high"
        if any(r.severity == "medium" for r in risks):
            return "medium"
        return "low" if risks else "unknown"

    def run(self, query: EntityQuery) -> InvestigationResult:
        normalized = query.normalized()
        return InvestigationResult(normalized, self.investigate(normalized))


def error_to_details(exc: Exception) -> dict[str, Any]:
    """Return a stable error class without exposing provider exception text or secrets."""

    return {"reason": "source_lookup_failed", "type": type(exc).__name__}
