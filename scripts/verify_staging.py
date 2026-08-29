"""Read-only staging configuration and Supabase surface verification.

Run with ``ENVIRONMENT=staging``.  Network checks are opt-in via
``STAGING_VERIFY_LIVE=true`` and use only GET requests (OpenAPI and storage metadata).
The script never prints credential values and never calls an RPC that could mutate data.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXPECTED_TABLES = {
    "matters",
    "matter_events",
    "action_approvals",
    "ai_usage_costs",
    "ai_cost_reservations",
    "ai_jobs",
    "ai_rate_limit_buckets",
    "action_reconciliation_audit",
}
EXPECTED_RPC_PREFIXES = {
    "create_matter_for_owner",
    "claim_ai_jobs",
    "mark_ai_job_dispatched",
    "finish_ai_job",
    "reclaim_stale_undispatched_ai_jobs",
    "reserve_ai_cost_for_owner",
    "close_ai_cost_reservation_for_owner",
    "consume_ai_rate_limit",
    "reconcile_action_for_owner",
    "record_document_event_for_owner",
}


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _check_config() -> list[Check]:
    environment = os.getenv("ENVIRONMENT", "").strip().casefold()
    checks = [
        Check("environment", environment == "staging", "must be exactly staging"),
        Check("supabase URL", bool(os.getenv("JAFAR_SUPABASE_URL", "").strip()), "present"),
        Check(
            "service-role credential",
            bool(os.getenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "").strip()),
            "present only in server environment",
        ),
        Check(
            "single owner",
            bool(os.getenv("JAFAR_SUPABASE_OWNER_USER_ID", "").strip()),
            "server-controlled owner ID is present",
        ),
        Check("pricing enabled", os.getenv("AI_COST_CONTROL_ENABLED", "").casefold() == "true", "must be true"),
        Check("pricing version", bool(os.getenv("AI_PRICING_VERSION", "").strip()), "present"),
        Check("private storage", os.getenv("STORAGE_BACKEND", "").casefold() == "supabase", "must be supabase"),
        Check("durable AI queue", os.getenv("AI_QUEUE_BACKEND", "").casefold() == "supabase", "must be supabase"),
    ]
    return checks


def _get_json(url: str, headers: dict[str, str]) -> object:
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def _live_checks() -> list[Check]:
    base = os.getenv("JAFAR_SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    checks: list[Check] = []
    try:
        schema = _get_json(f"{base}/rest/v1/", headers)
        definitions = schema.get("definitions", {}) if isinstance(schema, dict) else {}
        names = set(definitions)
        missing_tables = sorted(EXPECTED_TABLES - names)
        missing_rpcs = sorted(
            prefix for prefix in EXPECTED_RPC_PREFIXES if not any(name.startswith(prefix) for name in names)
        )
        checks.append(Check("critical tables", not missing_tables, "ok" if not missing_tables else f"missing: {', '.join(missing_tables)}"))
        checks.append(Check("RPC surface", not missing_rpcs, "ok" if not missing_rpcs else f"missing: {', '.join(missing_rpcs)}"))
        buckets = _get_json(f"{base}/storage/v1/bucket", headers)
        bucket_names = {item.get("name") for item in buckets if isinstance(item, dict)} if isinstance(buckets, list) else set()
        bucket = os.getenv("DOCUMENT_STORAGE_BUCKET", "jafar-legal-documents").strip()
        checks.append(Check("private document bucket", bucket in bucket_names, "present" if bucket in bucket_names else "missing"))
        checks.append(Check("RLS confirmation", os.getenv("STAGING_VERIFY_RLS_CONFIRMED", "").casefold() == "true", "operator must confirm via SQL metadata query"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        checks.append(Check("Supabase metadata", False, f"unavailable ({type(exc).__name__})"))
    return checks


def main() -> int:
    checks = _check_config()
    if os.getenv("STAGING_VERIFY_LIVE", "").casefold() == "true":
        checks.extend(_live_checks())
    else:
        checks.append(Check("live metadata", True, "not run; set STAGING_VERIFY_LIVE=true for read-only checks"))
    failed = [check for check in checks if not check.ok]
    for check in checks:
        print(f"{'PASS' if check.ok else 'FAIL'} {check.name}: {check.detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
