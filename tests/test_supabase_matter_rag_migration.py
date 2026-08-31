from pathlib import Path


MIGRATIONS = Path(__file__).parents[1] / "supabase" / "migrations"
REPAIR = MIGRATIONS / "20260831165010_repair_matter_pgvector_provenance.sql"


def migration_sql() -> str:
    return REPAIR.read_text(encoding="utf-8").casefold()


def test_provenance_repair_runs_after_chunk_traceability_migration():
    traceability = MIGRATIONS / "20260831150000_add_document_chunk_source_traceability.sql"

    assert traceability.exists()
    assert REPAIR.name > traceability.name


def test_rpc_returns_canonical_provenance_with_deterministic_ordering():
    sql = migration_sql()

    for field in (
        "stable_chunk_id text",
        "owner_user_id text",
        "source_section text",
        "source_start integer",
        "source_end integer",
        "similarity double precision",
    ):
        assert field in sql
    assert "set hnsw.iterative_scan = strict_order" in sql
    assert "coalesce(c.stable_chunk_id, c.id::text)" in sql
    assert "limit least(greatest(coalesce(p_match_count, 8), 0), 200)" in sql


def test_rpc_remains_security_invoker_and_service_role_only():
    sql = migration_sql()

    assert "security invoker" in sql
    assert "security definer" not in sql
    assert ") from public;" in sql
    assert ") from anon;" in sql
    assert ") from authenticated;" in sql
    assert ") to service_role;" in sql
    assert "m.owner_user_id::text = p_owner_user_id" in sql
    assert "d.matter_id::text = p_matter_id" in sql
