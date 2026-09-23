from __future__ import annotations

from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260909070000_add_telegram_visual_assets.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_visual_asset_migration_is_fail_closed_and_service_role_only() -> None:
    sql = _sql()

    assert "create table if not exists public.telegram_visual_assets" in sql
    assert "enable row level security" in sql
    assert "revoke all on table public.telegram_visual_assets from public" in sql
    assert "revoke all on table public.telegram_visual_assets from anon" in sql
    assert "revoke all on table public.telegram_visual_assets from authenticated" in sql
    assert "grant select, insert, update, delete on table public.telegram_visual_assets to service_role" in sql

    assert "security definer" in sql
    assert "resolve_telegram_visual_asset" in sql
    assert "v.category = p_category" in sql
    assert "v.approved is true" in sql
    assert "v.active is true" in sql
    assert "coalesce(v.data_base64, '') <> ''" in sql
    assert "v.sha256 ~ '^[0-9a-f]{64}$'" in sql

    assert "revoke all on function public.resolve_telegram_visual_asset(text, text) from public" in sql
    assert "revoke all on function public.resolve_telegram_visual_asset(text, text) from anon" in sql
    assert (
        "revoke all on function public.resolve_telegram_visual_asset(text, text) from authenticated"
        in sql
    )
    assert "grant execute on function public.resolve_telegram_visual_asset(text, text) to service_role" in sql


def test_visual_asset_migration_does_not_seed_or_activate_content() -> None:
    sql = _sql()

    assert "insert into public.telegram_visual_assets" not in sql
    assert "approved boolean not null default false" in sql
    assert "active boolean not null default false" in sql


def test_trigger_function_is_not_executable_by_public_api_roles() -> None:
    sql = _sql()

    signature = "public.touch_telegram_visual_assets_updated_at()"
    assert f"revoke all on function {signature} from public" in sql
    assert f"revoke all on function {signature} from anon" in sql
    assert f"revoke all on function {signature} from authenticated" in sql
