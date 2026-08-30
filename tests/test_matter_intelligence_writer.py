from jafar.matter_intelligence_store import MatterIntelligenceStore
from jafar.matter_intelligence_writer import MatterIntelligenceWriter


def test_writer_deduplicates_replays_and_sanitizes_secrets() -> None:
    store = MatterIntelligenceStore()
    writer = MatterIntelligenceWriter(store)
    first = writer.write(owner_id="o", matter_id="m", kind="evidence", payload={"summary": "x", "raw_prompt": "secret", "verification_state": "candidate/unverified"}, analysis_run_id="run-1")
    second = writer.write(owner_id="o", matter_id="m", kind="evidence", payload={"summary": "x", "raw_prompt": "other", "verification_state": "candidate/unverified"}, analysis_run_id="run-2")
    assert first.status == second.status == "persisted"
    assert len(store.list(owner_id="o", matter_id="m", kind="evidence")) == 1
    assert "raw_prompt" not in first.records[0].payload


def test_writer_changed_payload_appends_immutable_version() -> None:
    store = MatterIntelligenceStore()
    writer = MatterIntelligenceWriter(store)
    writer.write(owner_id="o", matter_id="m", kind="contradiction", payload={"statement_a": "a", "statement_b": "b"}, analysis_run_id="run")
    writer.write(owner_id="o", matter_id="m", kind="contradiction", payload={"statement_a": "a", "statement_b": "c"}, analysis_run_id="run")
    assert len(store.list(owner_id="o", matter_id="m", kind="contradiction")) == 2
