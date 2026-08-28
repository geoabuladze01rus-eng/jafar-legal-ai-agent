#!/usr/bin/env python3
"""Opt-in smoke gate; never performs a request by default."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jafar.ai_network_policy import AINetworkPolicy, DataClassification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-live-network", action="store_true")
    args = parser.parse_args()
    if not args.allow_live_network:
        print("LIVE_AI_NETWORK=DISABLED\nSMOKE=NOT_RUN")
        return 0
    try:
        AINetworkPolicy(allow_live_network=True).authorize(provider_enabled=True, credential=None, data=DataClassification.SYNTHETIC)
    except PermissionError:
        print("LIVE_AI_NETWORK=BLOCKED\nSMOKE=NOT_RUN")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
