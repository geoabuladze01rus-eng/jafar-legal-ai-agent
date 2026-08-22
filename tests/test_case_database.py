from jafar.case_database import CaseDatabase, CaseRecord


def test_case_database_supports_all_legal_case_types_and_document_links():
    db = CaseDatabase()
    for case_type in ("criminal", "civil", "arbitration"):
        db.upsert(CaseRecord(f"{case_type}-1", case_type, f"Test {case_type}"))

    db.attach_document("criminal-1", "doc-1")
    snapshot = db.snapshot("criminal-1")
    assert snapshot["case_type"] == "criminal"
    assert snapshot["document_ids"] == ["doc-1"]


def test_case_database_rejects_unknown_case_type():
    db = CaseDatabase()
    try:
        db.upsert(CaseRecord("x", "tax", "Invalid"))
    except ValueError:
        return
    raise AssertionError("unsupported case type was accepted")
