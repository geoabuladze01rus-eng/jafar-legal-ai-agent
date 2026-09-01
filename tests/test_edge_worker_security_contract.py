from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKERS = (
    ROOT / "supabase/functions/document-ocr-worker-v4/index.ts",
    ROOT / "supabase/functions/document-pipeline-worker-v3/index.ts",
)


def test_internal_workers_never_accept_public_or_platform_api_keys():
    for path in WORKERS:
        source = path.read_text(encoding="utf-8")
        assert "SUPABASE_PUBLISHABLE_KEYS" not in source
        assert "SUPABASE_SECRET_KEYS" not in source
        assert 'Deno.env.get("JAFAR_WORKER_SECRET")' in source
        assert "worker.length >= 32" in source
        assert "safeEqual(key, apiKey)" in source
        assert "safeEqual(key, bearer)" in source


def test_workers_with_disabled_platform_jwt_have_a_dedicated_secret_boundary():
    config = (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
    schedule = (
        ROOT / "supabase/migrations/20260824111500_schedule_document_worker_edge_functions.sql"
    ).read_text(encoding="utf-8")

    assert config.count("verify_jwt = false") == len(WORKERS)
    assert schedule.count("jafar_worker_secret") == len(WORKERS)
    assert "SUPABASE_SERVICE_ROLE_KEY" not in schedule


def test_workers_require_explicit_confidential_cloud_opt_in_before_claiming_jobs():
    for path in WORKERS:
        source = path.read_text(encoding="utf-8")
        gate = 'Deno.env.get("CONFIDENTIAL_CLOUD_FALLBACK")'
        rejection = 'json({ error: "confidential_cloud_processing_disabled" }, 503)'
        assert gate in source
        assert rejection in source
        assert source.index(rejection) < source.index('db.rpc("claim_document_')


def test_workers_do_not_persist_or_return_raw_provider_error_bodies():
    for path in WORKERS:
        source = path.read_text(encoding="utf-8")
        assert "function safeErrorCode(error: unknown)" in source
        assert "await response.text()" not in source
