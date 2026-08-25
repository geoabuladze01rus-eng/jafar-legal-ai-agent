from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .document_intake import DocumentExtractor, ExtractedDocument, ExtractedPage
from .document_intelligence import DocumentIntelligence
from .domains import DocumentTask, MatterType
from .evidence_timeline import EvidenceItem, EvidenceTimeline
from .legal_analysis import LegalAnalyzer
from .legal_reasoning import LegalReasoningEngine

DEFAULT_EXPECTED_CASE = "12604008104000012"
PERSON_TOKEN = re.compile(r"\b([А-ЯЁ][а-яё]{3,})\s+([А-ЯЁ])\.([А-ЯЁ])\.")
RUSSIAN_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


class PrivateDocumentGateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MotionContract:
    main_case: str
    case_numbers: tuple[str, ...]
    motion_date: str
    detention_at: str
    initial_home_arrest_at: str
    initial_home_arrest_until: str
    charge_at: str
    additional_merge_at: str
    investigation_extension_at: str
    investigation_term_until: str
    requested_home_arrest_until: str
    historical_admission_mentions: int
    anomaly_codes: tuple[str, ...]


def _page(pages: tuple[ExtractedPage, ...], number: int) -> str:
    for page in pages:
        if page.page_number == number:
            return page.text
    raise PrivateDocumentGateError(f"Expected PDF page {number} was not extracted")


def _match(pattern: str, text: str, label: str, flags: int = 0) -> re.Match[str]:
    result = re.search(pattern, text, flags)
    if result is None:
        raise PrivateDocumentGateError(f"Required source fact not found: {label}")
    return result


def _iso_date(value: str) -> str:
    return datetime.strptime(value, "%d.%m.%Y").date().isoformat()


def _natural_date(text: str) -> str:
    match = _match(
        r"\b(\d{1,2})\s+"
        r"(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
        r"\s+(\d{4})\s+года\b",
        text,
        "document date",
        re.IGNORECASE,
    )
    day = int(match.group(1))
    month = RUSSIAN_MONTHS[match.group(2).lower()]
    year = int(match.group(3))
    return datetime(year, month, day, tzinfo=UTC).date().isoformat()


def _surname_key(surname: str) -> str:
    lower = surname.lower()
    replacements = (
        ("овой", "ов"),
        ("евой", "ев"),
        ("иной", "ин"),
        ("ова", "ов"),
        ("ева", "ев"),
        ("ина", "ин"),
    )
    for ending, replacement in replacements:
        if lower.endswith(ending) and len(lower) > len(ending) + 2:
            return f"{lower[:-len(ending)]}{replacement}"
    return lower


def _has_initials_conflict(text: str) -> bool:
    by_surname: dict[str, set[str]] = defaultdict(set)
    for surname, first, second in PERSON_TOKEN.findall(text):
        by_surname[_surname_key(surname)].add(f"{first}.{second}.")
    return any(len(initials) > 1 for initials in by_surname.values())


def _has_duplicate_participant(page_two: str) -> bool:
    section = _match(
        r"организованной\s+преступной\s+деятельности(?P<body>.*?)в\s+период\s+времени",
        page_two,
        "alleged participant list",
        re.IGNORECASE | re.DOTALL,
    ).group("body")
    identities = [
        (_surname_key(surname), f"{first}.{second}.")
        for surname, first, second in PERSON_TOKEN.findall(section)
    ]
    return any(count > 1 for count in Counter(identities).values())


def _source_anomalies(pages: tuple[ExtractedPage, ...]) -> tuple[str, ...]:
    whole_text = "\n".join(page.text for page in pages)
    page_two = _page(pages, 2)
    page_three = _page(pages, 3)
    anomalies: list[str] = []

    if _has_initials_conflict(whole_text):
        anomalies.append("participant_initials_conflict")
    if _has_duplicate_participant(page_two):
        anomalies.append("duplicate_participant_in_source")
    if re.search(
        r"сотрудниками\s+ПУ\s+ФСБ\s+России\s+по\s+[А-ЯЁа-яё-]+скому\.",
        page_three,
        re.IGNORECASE,
    ):
        anomalies.append("truncated_source_sentence")
    return tuple(anomalies)


def extract_motion_contract(
    pages: tuple[ExtractedPage, ...],
    *,
    expected_case: str = DEFAULT_EXPECTED_CASE,
) -> MotionContract:
    if len(pages) != 4:
        raise PrivateDocumentGateError(
            f"Expected 4 PDF pages for this acceptance document, got {len(pages)}"
        )

    page_one = _page(pages, 1)
    page_two = _page(pages, 2)
    page_three = _page(pages, 3)
    page_four = _page(pages, 4)
    whole_text = "\n".join(page.text for page in pages)

    _match(
        r"ходатайства\s+о\s+продлении\s+меры\s+пресечения\s+в\s+виде\s+домашнего\s+ареста",
        page_one,
        "investigator motion heading",
        re.IGNORECASE,
    )
    main_case = _match(
        r"рассмотрев\s+материалы\s+уголовного\s+дела\s*№\s*(\d{17})",
        page_one,
        "main criminal case number",
        re.IGNORECASE,
    ).group(1)
    if main_case != expected_case:
        raise PrivateDocumentGateError(
            f"Unexpected main case number: expected {expected_case}, got {main_case}"
        )

    investigation_term = _match(
        r"Срок\s+предварительного\s+следствия.*?последний\s+раз\s+продлен\s+"
        r"(\d{2}\.\d{2}\.\d{4}).*?то\s+есть\s+до\s+(\d{2}\.\d{2}\.\d{4})",
        page_two,
        "investigation extension and end date",
        re.IGNORECASE | re.DOTALL,
    )
    detention = _match(
        r"(\d{2}\.\d{2}\.\d{4})\s+в\s+16\s+часов\s+20\s+минут.*?задержан",
        page_two,
        "detention timestamp",
        re.IGNORECASE | re.DOTALL,
    )
    initial_home_arrest = _match(
        r"(\d{2}\.\d{2}\.\d{4}).{0,220}?избрана\s+мера\s+пресечения\s+в\s+виде\s+"
        r"домашнего\s+ареста.*?то\s+есть\s+до\s+(\d{2}\.\d{2}\.\d{4})",
        page_three,
        "initial home arrest and end date",
        re.IGNORECASE | re.DOTALL,
    )
    charge = _match(
        r"(\d{2}\.\d{2}\.\d{4}).{0,100}?предъявлено\s+обвинение",
        page_three,
        "charge date",
        re.IGNORECASE | re.DOTALL,
    )
    additional_merge = _match(
        r"(\d{2}\.\d{2}\.\d{4})\s+уголовные\s+дела.*?соединены\s+в\s+одном\s+"
        r"производстве\s+с\s+присвоением\s+номера\s+уголовного\s+дела\s*№\s*(\d{17})",
        page_two,
        "additional case merge",
        re.IGNORECASE | re.DOTALL,
    )
    if additional_merge.group(2) != expected_case:
        raise PrivateDocumentGateError("Additional proceedings were not merged under the main case")

    request_in_reasoning = _match(
        r"необходимо\s+продлить\s+срок\s+содержания.*?то\s+есть\s+до\s+"
        r"(\d{2}\.\d{2}\.\d{4})",
        page_three,
        "investigator requested home-arrest end date",
        re.IGNORECASE | re.DOTALL,
    ).group(1)
    formal_request = _match(
        r"Ходатайствовать\s+перед.*?о\s+продлении.*?то\s+есть\s+до\s+"
        r"(\d{2}\.\d{2}\.\d{4})",
        page_four,
        "formal investigator request",
        re.IGNORECASE | re.DOTALL,
    ).group(1)
    if request_in_reasoning != formal_request:
        raise PrivateDocumentGateError(
            "Requested home-arrest end date differs between reasoning and operative request"
        )

    _match(
        r"организованной\s+преступной\s+деятельности",
        page_two,
        "investigation organized-crime allegation",
        re.IGNORECASE,
    )
    _match(
        r"более\s+32\s+транспортных\s+средств",
        page_two,
        "investigation vehicle-count allegation",
        re.IGNORECASE,
    )
    _match(
        r"47\s*556\s*224[,.]38",
        page_two,
        "investigation customs-payment allegation",
        re.IGNORECASE,
    )

    historical_admissions = len(
        re.findall(
            r"вину.{0,180}?признал\s+в\s+полном\s+объеме",
            whole_text,
            re.IGNORECASE | re.DOTALL,
        )
    )
    if historical_admissions < 2:
        raise PrivateDocumentGateError(
            "Expected historical admission statements on two procedural stages"
        )

    anomalies = _source_anomalies(pages)
    expected_anomalies = {
        "participant_initials_conflict",
        "duplicate_participant_in_source",
        "truncated_source_sentence",
    }
    if set(anomalies) != expected_anomalies:
        raise PrivateDocumentGateError(
            f"Source anomaly contract mismatch: detected {sorted(anomalies)}"
        )

    case_numbers = tuple(sorted(set(re.findall(r"\b\d{17}\b", whole_text))))
    return MotionContract(
        main_case=main_case,
        case_numbers=case_numbers,
        motion_date=_natural_date(page_one),
        detention_at=f"{_iso_date(detention.group(1))}T16:20:00+00:00",
        initial_home_arrest_at=_iso_date(initial_home_arrest.group(1)),
        initial_home_arrest_until=_iso_date(initial_home_arrest.group(2)),
        charge_at=_iso_date(charge.group(1)),
        additional_merge_at=_iso_date(additional_merge.group(1)),
        investigation_extension_at=_iso_date(investigation_term.group(1)),
        investigation_term_until=_iso_date(investigation_term.group(2)),
        requested_home_arrest_until=_iso_date(formal_request),
        historical_admission_mentions=historical_admissions,
        anomaly_codes=anomalies,
    )


def _at(value: str) -> datetime:
    if "T" in value:
        return datetime.fromisoformat(value)
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _build_reasoning(contract: MotionContract) -> dict[str, Any]:
    evidence = [
        {"evidence_id": "p1-motion", "page": 1, "source": "investigator_motion"},
        {"evidence_id": "p2-allegation", "page": 2, "source": "investigator_motion"},
        {"evidence_id": "p2-term", "page": 2, "source": "investigator_motion"},
        {"evidence_id": "p2-history", "page": 2, "source": "investigator_motion"},
        {"evidence_id": "p3-history", "page": 3, "source": "investigator_motion"},
        {"evidence_id": "p4-request", "page": 4, "source": "investigator_motion"},
    ]
    facts: list[dict[str, Any]] = [
        {
            "statement": "Документ является ходатайством следователя о продлении домашнего ареста",
            "evidence_ids": ["p1-motion"],
            "confidence": 0.99,
            "source_type": "document_fact",
        },
        {
            "statement": (
                "Срок предварительного следствия в документе указан до "
                f"{contract.investigation_term_until}"
            ),
            "evidence_ids": ["p2-term"],
            "confidence": 0.99,
            "source_type": "document_fact",
        },
        {
            "statement": (
                "Следователь просит продлить домашний арест до "
                f"{contract.requested_home_arrest_until}"
            ),
            "evidence_ids": ["p4-request"],
            "confidence": 0.99,
            "source_type": "investigation_request",
            "metadata": {"is_court_decision": False},
        },
        {
            "statement": "Следствие утверждает наличие организованной преступной деятельности",
            "evidence_ids": ["p2-allegation"],
            "confidence": 0.99,
            "source_type": "investigation_allegation",
        },
        {
            "statement": "Следствие утверждает объём транспортных средств и сумму неуплаты",
            "evidence_ids": ["p2-allegation"],
            "confidence": 0.99,
            "source_type": "investigation_allegation",
        },
        {
            "statement": "Документ фиксирует более раннее признание вины как историческую позицию",
            "evidence_ids": ["p2-history", "p3-history"],
            "confidence": 0.99,
            "source_type": "investigation_recorded_statement",
            "metadata": {"historical_position": True, "current_position": False},
        },
    ]
    for anomaly_code in contract.anomaly_codes:
        facts.append(
            {
                "statement": f"Источник содержит аномалию: {anomaly_code}",
                "confidence": 0.80,
                "source_type": "evidence_gap",
                "metadata": {"anomaly_code": anomaly_code},
            }
        )

    timeline = [
        {"event_at": contract.detention_at, "title": "Задержание"},
        {"event_at": contract.initial_home_arrest_at, "title": "Первоначальный домашний арест"},
        {"event_at": contract.charge_at, "title": "Предъявление обвинения"},
        {"event_at": contract.additional_merge_at, "title": "Соединение дополнительных производств"},
        {"event_at": contract.investigation_extension_at, "title": "Продление срока следствия"},
        {"event_at": contract.motion_date, "title": "Ходатайство следователя о продлении"},
    ]
    result = LegalReasoningEngine().analyze(
        facts=facts,
        evidence=evidence,
        timeline=timeline,
    )

    request = next(
        item
        for item in result["findings"]
        if item["metadata"].get("source_type") == "investigation_request"
    )
    allegations = [
        item
        for item in result["findings"]
        if item["metadata"].get("source_type") == "investigation_allegation"
    ]
    historical = next(
        item
        for item in result["findings"]
        if item["metadata"].get("source_type") == "investigation_recorded_statement"
    )
    if request["metadata"].get("is_court_decision") is not False:
        raise PrivateDocumentGateError("Investigator request was promoted to a court decision")
    if request["requires_human_review"] is not True:
        raise PrivateDocumentGateError("Investigator request bypassed human review")
    if not allegations or not all(item["requires_human_review"] for item in allegations):
        raise PrivateDocumentGateError("Investigation allegation bypassed human review")
    if historical["metadata"].get("current_position") is not False:
        raise PrivateDocumentGateError("Historical admission was promoted to current position")
    if len(result["evidence_gaps"]) != len(contract.anomaly_codes):
        raise PrivateDocumentGateError("Source anomalies were not surfaced as evidence gaps")
    return result


def _build_timeline(contract: MotionContract, document_id: str) -> dict[str, Any]:
    items = [
        EvidenceItem(
            evidence_id="timeline-detention",
            kind="document_fact",
            title="Задержание",
            source="investigator_motion:p2",
            occurred_at=_at(contract.detention_at),
            document_id=document_id,
            case_id=contract.main_case,
        ),
        EvidenceItem(
            evidence_id="timeline-home-arrest",
            kind="document_fact",
            title="Первоначальный домашний арест",
            source="investigator_motion:p3",
            occurred_at=_at(contract.initial_home_arrest_at),
            document_id=document_id,
            case_id=contract.main_case,
            metadata={"until": contract.initial_home_arrest_until},
        ),
        EvidenceItem(
            evidence_id="timeline-charge",
            kind="document_fact",
            title="Предъявление обвинения",
            source="investigator_motion:p3",
            occurred_at=_at(contract.charge_at),
            document_id=document_id,
            case_id=contract.main_case,
        ),
        EvidenceItem(
            evidence_id="timeline-merge",
            kind="document_fact",
            title="Соединение дополнительных производств",
            source="investigator_motion:p2",
            occurred_at=_at(contract.additional_merge_at),
            document_id=document_id,
            case_id=contract.main_case,
        ),
        EvidenceItem(
            evidence_id="timeline-investigation-extension",
            kind="document_fact",
            title="Продление срока следствия",
            source="investigator_motion:p2",
            occurred_at=_at(contract.investigation_extension_at),
            document_id=document_id,
            case_id=contract.main_case,
            metadata={"until": contract.investigation_term_until},
        ),
        EvidenceItem(
            evidence_id="timeline-motion",
            kind="investigation_request",
            title="Ходатайство следователя о продлении",
            source="investigator_motion:p1-p4",
            occurred_at=_at(contract.motion_date),
            document_id=document_id,
            case_id=contract.main_case,
            metadata={
                "requested_until": contract.requested_home_arrest_until,
                "is_court_decision": False,
            },
        ),
    ]
    return EvidenceTimeline().build(items)


def run_private_pdf_gate(
    pdf_path: Path,
    *,
    expected_case: str = DEFAULT_EXPECTED_CASE,
) -> dict[str, Any]:
    content = pdf_path.read_bytes()
    extractor = DocumentExtractor()
    extracted: ExtractedDocument = extractor.extract(
        pdf_path.name,
        content,
        "application/pdf",
    )
    pages = extractor.extract_pages(pdf_path.name, content, "application/pdf")
    contract = extract_motion_contract(pages, expected_case=expected_case)

    normalized = DocumentIntelligence().extract(
        document_id=extracted.fingerprint,
        text=extracted.text,
        metadata={"source": "private_local_pdf", "page_count": len(pages)},
    )
    generic_analysis = LegalAnalyzer().analyze(
        extracted.text,
        DocumentTask.LEGAL_ANALYSIS,
        MatterType.CRIMINAL,
    )
    reasoning = _build_reasoning(contract)
    timeline = _build_timeline(contract, extracted.fingerprint)

    return {
        "status": "PASS",
        "document": {
            "filename": pdf_path.name,
            "fingerprint": extracted.fingerprint,
            "content_hash": normalized.content_hash,
            "page_count": len(pages),
            "document_kind": "investigator_motion",
        },
        "contract": {
            "main_case": contract.main_case,
            "case_numbers": list(contract.case_numbers),
            "motion_date": contract.motion_date,
            "detention_at": contract.detention_at,
            "initial_home_arrest_at": contract.initial_home_arrest_at,
            "initial_home_arrest_until": contract.initial_home_arrest_until,
            "charge_at": contract.charge_at,
            "additional_merge_at": contract.additional_merge_at,
            "investigation_extension_at": contract.investigation_extension_at,
            "investigation_term_until": contract.investigation_term_until,
            "requested_home_arrest_until": contract.requested_home_arrest_until,
            "historical_admission_mentions": contract.historical_admission_mentions,
        },
        "timeline": timeline,
        "evidence_gaps": list(contract.anomaly_codes),
        "reasoning": {
            "human_review_required": reasoning["human_review_required"],
            "finding_count": len(reasoning["findings"]),
            "evidence_gap_count": len(reasoning["evidence_gaps"]),
            "evidence_coverage": reasoning["evidence_coverage"],
            "source_types": sorted(
                {
                    item["metadata"].get("source_type")
                    for item in reasoning["findings"]
                    if item["metadata"].get("source_type")
                }
            ),
        },
        "generic_legal_analysis": {
            "risk_signals": [issue.title for issue in generic_analysis.issues],
            "dates_requiring_review": len(generic_analysis.deadlines),
            "key_facts": generic_analysis.key_facts,
            "confidence": generic_analysis.confidence,
        },
        "privacy": {
            "pdf_committed": False,
            "external_ai_called": False,
            "production_written": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the local-only Pavlik private PDF E2E legal-safety gate."
    )
    parser.add_argument("pdf", type=Path, help="Path to the private investigator-motion PDF")
    parser.add_argument(
        "--expected-case",
        default=DEFAULT_EXPECTED_CASE,
        help="Expected main criminal case number",
    )
    args = parser.parse_args(argv)

    try:
        report = run_private_pdf_gate(args.pdf, expected_case=args.expected_case)
    except (OSError, PrivateDocumentGateError, ValueError) as exc:
        print(f"PAVLIK PRIVATE E2E: FAIL — {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
