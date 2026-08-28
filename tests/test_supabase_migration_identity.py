from collections import Counter
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION_NAME = re.compile(r"^(\d{14})_[a-z0-9_]+\.sql$")


def test_supabase_migrations_have_unique_timestamp_identities() -> None:
    files = sorted(MIGRATIONS.glob("*.sql"))
    parsed = []
    invalid = []

    for path in files:
        match = MIGRATION_NAME.fullmatch(path.name)
        if match is None:
            invalid.append(path.name)
            continue
        parsed.append((match.group(1), path.name))

    assert not invalid, f"Invalid Supabase migration filenames: {invalid}"

    counts = Counter(timestamp for timestamp, _ in parsed)
    duplicates = {
        timestamp: [name for candidate, name in parsed if candidate == timestamp]
        for timestamp, count in counts.items()
        if count > 1
    }
    assert not duplicates, f"Duplicate Supabase migration timestamps: {duplicates}"


def test_payload_binding_runs_after_atomic_matter_create() -> None:
    names = {path.name for path in MIGRATIONS.glob("*.sql")}

    assert "20260828165000_add_atomic_matter_create_rpc.sql" in names
    assert "20260828165500_bind_action_approval_payload.sql" in names
