from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OCR_WORKER = (ROOT / "supabase/functions/document-ocr-worker-v4/index.ts").read_text()
PIPELINE_WORKER = (ROOT / "supabase/functions/document-pipeline-worker-v3/index.ts").read_text()
SHARED = (ROOT / "supabase/functions/_shared/document-worker.ts").read_text()
PIPELINE_MIGRATION = (
    ROOT / "supabase/migrations/20260825010000_harden_document_pipeline_end_to_end.sql"
).read_text()
AUTH_MIGRATION = (
    ROOT / "supabase/migrations/20260825011000_separate_document_worker_auth.sql"
).read_text()
OCR_COMPACT = " ".join(OCR_WORKER.split())
PIPELINE_COMPACT = " ".join(PIPELINE_WORKER.split())


def test_ocr_success_uses_atomic_idempotent_pipeline_handoff() -> None:
    assert 'await db.rpc( "complete_ocr_and_enqueue_pipeline"' in OCR_COMPACT
    assert 'p_worker_id: workerId' in OCR_WORKER
    assert '.from("document_ocr_jobs").update' not in OCR_WORKER
    assert 'processing_status: "completed"' not in OCR_WORKER
    assert "on conflict (document_id, stage) do update" in PIPELINE_MIGRATION
    assert "v_job.status = 'completed'" in PIPELINE_MIGRATION
    assert "unique(document_id, stage) prevents duplicates" in PIPELINE_MIGRATION


def test_low_confidence_or_manual_review_cannot_enqueue_pipeline() -> None:
    assert "const manualReview = lowConfidencePages > 0 || invalidPages > 0" in OCR_WORKER
    assert "v_manual_review := coalesce(p_manual_review, false)" in PIPELINE_MIGRATION
    assert "or v_bad_pages > 0" in PIPELINE_MIGRATION
    assert "if v_manual_review then" in PIPELINE_MIGRATION
    assert "processing_status = 'manual_review'" in PIPELINE_MIGRATION
    assert "document_pages_not_ready" in PIPELINE_MIGRATION


def test_document_completed_is_reserved_for_full_pipeline_completion() -> None:
    for status in ("ocr_processing", "ocr_completed", "pipeline_processing", "manual_review"):
        assert f"'{status}'::text" in PIPELINE_MIGRATION
    assert "v_job.stage = 'analyze'" in PIPELINE_MIGRATION
    assert "set processing_status = 'completed'" in PIPELINE_MIGRATION
    assert "status <> 'completed'" in PIPELINE_MIGRATION


def test_claims_are_ordered_fenced_and_skip_locked() -> None:
    assert PIPELINE_MIGRATION.count("for update of j skip locked") == 2
    assert PIPELINE_MIGRATION.count("attempts = attempts + 1") == 2
    assert "locked_by = p_worker_id" in PIPELINE_MIGRATION
    assert "stale_ocr_worker_lease" in PIPELINE_MIGRATION
    assert "stale_pipeline_worker_lease" in PIPELINE_MIGRATION
    assert "p.stage = 'chunk'" in PIPELINE_MIGRATION
    assert "p.stage = 'embed'" in PIPELINE_MIGRATION
    assert "c.embedding is null" in PIPELINE_MIGRATION


def test_ocr_retries_backoff_and_recover_abandoned_claims() -> None:
    assert 'db.rpc("fail_document_ocr_job"' in OCR_WORKER
    assert "2 ** Math.max(0, attempts - 1)" in OCR_WORKER
    assert "lease_expires_at < now()" in PIPELINE_MIGRATION
    assert "ocr_worker_lease_expired" in PIPELINE_MIGRATION
    assert "ocr_retry_limit_exhausted" in PIPELINE_MIGRATION
    assert "j.attempts >= d.max_retry_attempts" in PIPELINE_MIGRATION


def test_embedding_stage_requeues_until_every_chunk_is_embedded() -> None:
    assert '"JAFAR_EMBEDDING_BATCH_SIZE", 100, 1, 100' in PIPELINE_COMPACT
    assert ".limit(EMBEDDING_BATCH_SIZE)" in PIPELINE_WORKER
    assert 'select("id", { count: "exact", head: true })' in PIPELINE_WORKER
    assert '.is("embedding", null)' in PIPELINE_WORKER
    assert 'await finish("queued")' in PIPELINE_WORKER
    assert "remaining_chunks: remaining" in PIPELINE_WORKER


def test_analysis_provenance_is_validated_and_previous_rows_are_preserved() -> None:
    for field in (
        "matter_id: doc.matter_id",
        "document_id: doc.id",
        "citations: validation.citations",
        "source_chunks: chunks.map",
        "page: chunk.source_page",
        "chunk_index: chunk.chunk_index",
        "confidence: clampConfidence",
        "requires_lawyer_review: true",
    ):
        assert field in PIPELINE_WORKER
    assert "significant_findings_without_citations" in SHARED
    assert 'status: validation.valid ? "completed" : "manual_review"' in PIPELINE_WORKER
    assert '.from("ai_analyses").insert' in PIPELINE_WORKER
    assert '.from("ai_analyses").delete' not in PIPELINE_WORKER


def test_worker_auth_separates_gateway_and_application_secrets() -> None:
    assert 'req.headers.get("x-jafar-worker-secret")' in SHARED
    assert 'req.headers.get("apikey")' not in SHARED
    assert "'apikey', (select decrypted_secret" in AUTH_MIGRATION
    assert "name = 'supabase_publishable_key'" in AUTH_MIGRATION
    assert "'x-jafar-worker-secret', (select decrypted_secret" in AUTH_MIGRATION
    assert "name = 'jafar_worker_secret'" in AUTH_MIGRATION


def test_models_come_from_validated_environment_configuration() -> None:
    assert "gpt-5.6-luna" not in OCR_WORKER + PIPELINE_WORKER
    assert 'configuredModel("JAFAR_OCR_MODEL", "gpt-5.6")' in OCR_WORKER
    assert 'configuredModel("JAFAR_ANALYSIS_MODEL", "gpt-5.6")' in PIPELINE_WORKER
    assert '"JAFAR_EMBEDDING_MODEL", "text-embedding-3-small"' in PIPELINE_COMPACT
