#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

printf '\n[JAFAR] Python compile check\n'
"$PYTHON_BIN" -m compileall -q src

printf '\n[JAFAR] Ruff\n'
"$PYTHON_BIN" -m ruff check src tests

printf '\n[JAFAR] Pavlik acceptance contract\n'
"$PYTHON_BIN" -m pytest -q tests/test_pavlik_acceptance_contract.py

printf '\n[JAFAR] Full Python regression suite\n'
"$PYTHON_BIN" -m pytest -q

printf '\n[JAFAR] Verification completed successfully.\n'
