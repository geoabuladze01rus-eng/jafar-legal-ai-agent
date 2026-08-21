from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class LegalRisk:
    title: str
    explanation: str
    level: RiskLevel
    confidence: float


@dataclass(frozen=True)
class LegalAnalysisResult:
    document_id: str
    facts: tuple[str, ...]
    legal_questions: tuple[str, ...]
    risks: tuple[LegalRisk, ...]
    consequences: tuple[str, ...]
    recommendations: tuple[str, ...]
    deadlines: tuple[str, ...]
    confidence: float
    requires_lawyer_review: bool = True
