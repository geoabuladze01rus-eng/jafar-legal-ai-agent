#!/usr/bin/env python3
"""One-shot synthetic Qwen smoke; disabled by default."""
import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from jafar.domains import DocumentTask, MatterType
from jafar.model_provider import QwenProvider


def credential():
    value = os.getenv("QWEN_API_KEY")
    if value: return value
    if platform.system() == "Darwin":
        try:
            return subprocess.run(["security", "find-generic-password", "-a", os.getenv("USER", ""), "-s", "JAFAR.Qwen.API", "-w"], check=True, capture_output=True, text=True).stdout.strip()
        except (subprocess.CalledProcessError, OSError): return None
    return None

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-live-network", action="store_true"); args = parser.parse_args()
    if not args.allow_live_network: print("LIVE_AI_NETWORK=DISABLED\nSMOKE=NOT_RUN"); return 0
    key, base, model = credential(), os.getenv("QWEN_BASE_URL"), os.getenv("QWEN_MODEL")
    if not key: print("LIVE_AI_NETWORK=BLOCKED\nSMOKE=BLOCKED_CREDENTIAL_NOT_CONFIGURED"); return 2
    if not base: print("SMOKE=BLOCKED_BASE_URL_NOT_CONFIGURED"); return 2
    if not model: print("SMOKE=BLOCKED_MODEL_NOT_CONFIGURED"); return 2
    result, category, status = QwenProvider(key, model, base, True).analyze_with_diagnostics("Полностью синтетический договор. Требуется проверка адвокатом.", DocumentTask.LEGAL_ANALYSIS, MatterType.GENERAL)
    print(f"SMOKE={'PASS' if result else 'FAIL'}\nPROVIDER=qwen\nMODEL={model}\nERROR_CATEGORY={category or 'UNKNOWN'}\nEXTERNAL_REQUESTS=1\nRETRIES=0\nFALLBACK=0\nOPENAI_CALLS=0\nGEMINI_CALLS=0\nDEEPSEEK_CALLS=0\nREQUIRES_LAWYER_REVIEW=true\nSOURCE_FACT_PROMOTION=NO" + (f"\nHTTP_STATUS={status}" if status else "")); return 0 if result else 1
if __name__ == "__main__": raise SystemExit(main())
