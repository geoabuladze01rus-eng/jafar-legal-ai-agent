from enum import StrEnum


class MatterType(StrEnum):
    CRIMINAL = "criminal"
    ARBITRATION = "arbitration"
    CIVIL = "civil"
    ADMINISTRATIVE = "administrative"
    GENERAL = "general"


class DocumentTask(StrEnum):
    SUMMARIZE = "summarize"
    LEGAL_ANALYSIS = "legal_analysis"
    RISK_REVIEW = "risk_review"
    DRAFT_RESPONSE = "draft_response"
    EXTRACT_DEADLINES = "extract_deadlines"
