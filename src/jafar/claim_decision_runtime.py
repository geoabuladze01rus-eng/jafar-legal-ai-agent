"""Desktop-only encrypted reviewer decision register bootstrap."""

from __future__ import annotations

from .desktop_key_material import desktop_corpus_key
from .desktop_runtime import desktop_paths, is_desktop_runtime
from .encrypted_claim_decisions import (
    EncryptedClaimDecisionLedger,
    derive_decision_ledger_key,
)


def build_claim_decision_ledger_from_env() -> EncryptedClaimDecisionLedger | None:
    if not is_desktop_runtime():
        return None
    paths = desktop_paths().create()
    return EncryptedClaimDecisionLedger(
        paths.application_support / "claim-review-decisions.sqlite3",
        derive_decision_ledger_key(desktop_corpus_key()),
    )
