#!/usr/bin/env python3
"""One-shot synthetic Gemini smoke; disabled unless explicitly opted in."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from jafar.domains import DocumentTask, MatterType
from jafar.model_provider import GeminiProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-live-network", action="store_true")
    args = parser.parse_args()
    if not args.allow_live_network:
        print("LIVE_AI_NETWORK=DISABLED\nSMOKE=NOT_RUN")
        return 0
    key, model = os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL")
    if not key:
        print("LIVE_AI_NETWORK=BLOCKED\nSMOKE=BLOCKED_CREDENTIAL_NOT_CONFIGURED")
        return 2
    if not model:
        print("SMOKE=BLOCKED_MODEL_NOT_CONFIGURED")
        return 2
    provider = GeminiProvider(api_key=key, model=model, enabled=True)
    result, category, status = provider.analyze_with_diagnostics(
        "Полностью синтетический договор. Укажи вопросы для проверки адвокатом.",
        DocumentTask.LEGAL_ANALYSIS, MatterType.GENERAL)
    print(f"SMOKE={'PASS' if result else 'FAIL'}\nPROVIDER=gemini\nMODEL={model}\nEXTERNAL_REQUESTS=1\nRETRIES=0\nFALLBACK=0\nOPENAI_CALLS=0\nDEEPSEEK_CALLS=0\nREQUIRES_LAWYER_REVIEW=true\nSOURCE_FACT_PROMOTION=NO\nERROR_CATEGORY={category or 'UNKNOWN'}" + (f"\nHTTP_STATUS={status}" if status else ""))
    return 0 if result else 1
if __name__ == "__main__": raise SystemExit(main())
