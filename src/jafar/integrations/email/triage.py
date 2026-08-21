import re

from jafar.integrations.email.models import EmailTriageResult, LegalEmail

_LEGAL_TERMS = re.compile(
    r"\b(договор|суд|иск|претенз|адвокат|следств|уголовн|арбитраж|"
    r"гражданск|постановлен|определен|протокол|допрос|жалоб|срок|"
    r"доверенност|экспертиз|уведомлен|требован)\w*\b",
    re.IGNORECASE,
)


def triage_email(email: LegalEmail) -> EmailTriageResult:
    text = f"{email.subject}\n{email.body_preview}"
    matches = _LEGAL_TERMS.findall(text)
    score = min(1.0, len(set(word.lower() for word in matches)) / 5)
    return EmailTriageResult(
        is_legal_relevant=score >= 0.2 or email.has_attachments,
        confidence=score if score >= 0.2 else (0.25 if email.has_attachments else 0.0),
        reasons=(
            [f"Обнаружены юридические маркеры: {', '.join(sorted(set(matches)))}"]
            if matches
            else (["Письмо содержит вложения"] if email.has_attachments else [])
        ),
    )
