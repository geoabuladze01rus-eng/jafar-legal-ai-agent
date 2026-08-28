from collections import Counter
from pathlib import Path


def test_supabase_migration_versions_are_unique() -> None:
    migrations = sorted(Path("supabase/migrations").glob("*.sql"))
    assert migrations, "expected Supabase migrations"

    versions = [path.name.split("_", 1)[0] for path in migrations]
    duplicates = sorted(version for version, count in Counter(versions).items() if count > 1)

    assert duplicates == [], f"duplicate Supabase migration versions: {duplicates}"
