from dataclasses import replace
from datetime import date

from jafar.case_law_ingestion import CaseLawRecord, CaseLawRepository, IngestionStatus


def _record(fingerprint: str) -> CaseLawRecord:
    return CaseLawRecord(
        record_id="record-1",
        citation="Определение ВС РФ от 01.08.2026",
        court="Верховный Суд РФ",
        decided_on=date(2026, 8, 1),
        topic="допустимость доказательств",
        proposition="Проверка допустимости доказательства",
        source_url="https://example.test/sc-1",
        source_fingerprint=fingerprint,
        authority_id="sc-1",
    )


def test_update_removes_stale_dedupe_alias() -> None:
    repository = CaseLawRepository()
    original = _record("fingerprint-v1")
    updated = replace(original, source_fingerprint="fingerprint-v2")

    assert repository.upsert(original) == IngestionStatus.NEW
    old_key = original.dedupe_key
    assert repository.get_by_dedupe_key(old_key) == original

    assert repository.upsert(updated) == IngestionStatus.UPDATED
    assert repository.get_by_dedupe_key(old_key) is None
    assert repository.get_by_dedupe_key(updated.dedupe_key) == updated
    assert repository.records() == (updated,)
