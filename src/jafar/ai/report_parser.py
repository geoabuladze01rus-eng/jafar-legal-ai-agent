import json
from typing import Any

from jafar.ai.report import LegalReport

_REQUIRED_KEYS = (
    "summary",
    "facts",
    "risks",
    "deadlines",
    "missing_information",
    "recommendations",
)


def parse_legal_report(payload: str) -> LegalReport:
    try:
        data: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response is not valid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("AI response must be a JSON object")

    missing = [key for key in _REQUIRED_KEYS if key not in data]
    if missing:
        raise ValueError(f"AI response missing required fields: {', '.join(missing)}")

    if not isinstance(data["summary"], str):
        raise ValueError("summary must be a string")

    for key in _REQUIRED_KEYS[1:]:
        if not isinstance(data[key], list) or not all(isinstance(item, str) for item in data[key]):
            raise ValueError(f"{key} must be an array of strings")

    return LegalReport(
        summary=data["summary"],
        facts=data["facts"],
        risks=data["risks"],
        deadlines=data["deadlines"],
        missing_information=data["missing_information"],
        recommendations=data["recommendations"],
    )
