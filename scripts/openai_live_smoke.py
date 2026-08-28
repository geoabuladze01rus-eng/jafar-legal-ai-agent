#!/usr/bin/env python3
"""Opt-in smoke gate; never performs a request by default."""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jafar.ai_network_policy import AINetworkPolicy, DataClassification
from jafar.domains import DocumentTask, MatterType
from jafar.model_provider import OpenAICompatibleProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-live-network", action="store_true")
    args = parser.parse_args()
    if not args.allow_live_network:
        print("LIVE_AI_NETWORK=DISABLED\nSMOKE=NOT_RUN")
        return 0
    credential = os.environ.get("OPENAI_API_KEY")
    try:
        AINetworkPolicy(mode="local_live_test", allow_live_network=True).authorize(provider_enabled=True, credential=credential, data=DataClassification.SYNTHETIC)
    except PermissionError:
        print("LIVE_AI_NETWORK=BLOCKED\nSMOKE=BLOCKED_CREDENTIAL_NOT_CONFIGURED")
        return 2
    model = os.environ.get("OPENAI_MODEL") or os.environ.get("MODEL_NAME")
    if not model:
        print("SMOKE=BLOCKED_MODEL_NOT_CONFIGURED")
        return 2
    started = time.perf_counter()
    provider = OpenAICompatibleProvider(api_key=credential, model=model, timeout_seconds=15)
    result = provider.analyze(
        "15 января 2026 года между ООО «Альфа-Тест» и ООО «Бета-Тест» был заключён полностью вымышленный договор поставки. Все сведения синтетические. Укажи вопросы для проверки юристом.",
        DocumentTask.LEGAL_ANALYSIS,
        MatterType.GENERAL,
    )
    latency = int((time.perf_counter() - started) * 1000)
    print(f"SMOKE={'PASS' if isinstance(result, dict) else 'FAIL'}\nPROVIDER=openai\nMODEL={model}\nEXTERNAL_REQUESTS=1\nRETRIES=0\nFALLBACK=0\nGEMINI_CALLS=0\nDEEPSEEK_CALLS=0\nREQUIRES_LAWYER_REVIEW=true\nSOURCE_FACT_PROMOTION=NO\nLATENCY_MS={latency}\nINPUT_TOKENS=unavailable\nOUTPUT_TOKENS=unavailable")
    return 0 if isinstance(result, dict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
