from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.staging_smoke


def test_staging_configuration_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "ENVIRONMENT": "staging",
        "JAFAR_SUPABASE_URL": "https://staging.example.supabase.co",
        "JAFAR_SUPABASE_SERVICE_ROLE_KEY": "test-only-placeholder",
        "JAFAR_SUPABASE_OWNER_USER_ID": "staging-owner",
        "AI_COST_CONTROL_ENABLED": "true",
        "AI_PRICING_VERSION": "staging-reviewed",
        "STORAGE_BACKEND": "supabase",
        "AI_QUEUE_BACKEND": "supabase",
    }
    environment = os.environ.copy()
    environment.update(values)
    result = subprocess.run(
        [sys.executable, "scripts/verify_staging.py"],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_non_staging_environment_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    environment = os.environ.copy()
    environment["ENVIRONMENT"] = "production"
    result = subprocess.run(
        [sys.executable, "scripts/verify_staging.py"],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "FAIL environment" in result.stdout
