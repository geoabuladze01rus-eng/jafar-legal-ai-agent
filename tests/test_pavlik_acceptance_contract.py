import json
from pathlib import Path

from jafar.case_acceptance import (
    CaseObservation,
    VerificationStatus,
    evaluate_case_acceptance,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_pavlik_acceptance_preserves_ocr_identity_conflict_and_verified_provenance():
    ocr = _load("pavlik_case_ocr_fixture.json")
    order = _load("pavlik_extension_order_verified.json")

    observations = [
        CaseObservation(
            field=field,
            value=str(ocr["case"][field]),
            source_id=ocr["document"]["filename"],
            page=None,
            verification=VerificationStatus.OCR_UNVERIFIED,
        )
        for field in ("case_number", "suspect", "date_of_birth", "investigator")
    ]
    observations.extend(
        CaseObservation(
            field=item["field"],
            value=item["value"],
            source_id=order["document"]["filename"],
            page=item["page"],
            verification=VerificationStatus.VISUALLY_VERIFIED,
        )
        for item in order["observations"]
    )

    report = evaluate_case_acceptance(observations)

    assert report.authoritative["case_number"] == "12604008104000012"
    assert report.authoritative["suspect"] == "Павлик Вадим Алексеевич"
    assert report.authoritative["date_of_birth"] == "17.11.1984"
    assert report.authoritative["investigator"] == "Орлов А.С."
    assert report.authoritative["house_arrest_until"] == "03.09.2026"

    identity_conflict = next(item for item in report.conflicts if item.field == "suspect")
    assert set(identity_conflict.values) == {
        "Павлик Вадим Александрович",
        "Павлик Вадим Алексеевич",
    }
    assert any(":page:3" in ref for ref in identity_conflict.source_refs)
    assert report.requires_human_review is True


def test_ocr_only_case_fact_never_becomes_authoritative_without_corroboration():
    report = evaluate_case_acceptance(
        [
            CaseObservation(
                field="unverified_amount",
                value="165000",
                source_id="scan.pdf",
                page=8,
                verification=VerificationStatus.OCR_UNVERIFIED,
            )
        ]
    )

    assert "unverified_amount" not in report.authoritative
    assert report.unresolved_fields == ("unverified_amount",)
    assert report.requires_human_review is True
