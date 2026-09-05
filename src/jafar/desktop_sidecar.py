"""Entrypoint for the signed macOS JAFAR backend sidecar.

The parent Swift process provides an ephemeral IPC token and a loopback port.  This
entrypoint rejects anything else before importing the application, keeping desktop
startup independent of a repository, shell profile, system Python, and .env file.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time

from .desktop_runtime import LOOPBACK_HOST, RUNTIME_MODE, desktop_paths


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="JafarBackend", add_help=True)
    parser.add_argument("--host", default=LOOPBACK_HOST)
    parser.add_argument("--port", required=True, type=int)
    return parser


def _validate(args: argparse.Namespace) -> None:
    if args.host != LOOPBACK_HOST:
        raise ValueError("desktop sidecar must bind to loopback")
    if not 1 <= args.port <= 65535:
        raise ValueError("desktop sidecar port is invalid")
    token = os.getenv("JAFAR_DESKTOP_IPC_TOKEN", "")
    if len(token) < 32:
        raise ValueError("desktop IPC authentication is not configured")
    parent_pid = os.getenv("JAFAR_DESKTOP_PARENT_PID", "").strip()
    if parent_pid and (not parent_pid.isdecimal() or int(parent_pid) < 1):
        raise ValueError("desktop parent process is invalid")


def _stop_if_parent_exits(parent_pid: int) -> None:
    """Stop only this sidecar if its specific Swift parent disappears.

    This is deliberately PID-based rather than name-based, so it cannot terminate an
    unrelated local process.  It also covers crash/force-quit paths where Swift does
    not receive an application termination callback.
    """

    while True:
        time.sleep(1)
        if os.getppid() != parent_pid:
            os.kill(os.getpid(), signal.SIGTERM)
            return


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _validate(args)
    except ValueError as exc:
        print(f"JAFAR desktop backend configuration error: {exc}", file=sys.stderr)
        return 2

    os.environ["JAFAR_RUNTIME_MODE"] = RUNTIME_MODE
    os.environ["ENVIRONMENT"] = "desktop"
    os.environ["JAFAR_PRODUCTION_SEND"] = "false"
    os.environ["JAFAR_TELEGRAM_POLLING_ENABLED"] = "false"
    os.environ["JAFAR_CONFIDENTIAL_CLOUD_FALLBACK"] = "false"
    # Derive process-local storage keys and remove the Keychain master material
    # before importing the ASGI application or starting any background thread.
    from .desktop_key_material import bootstrap_desktop_key_material

    try:
        bootstrap_desktop_key_material()
    except RuntimeError:
        print("JAFAR desktop backend storage bootstrap failed", file=sys.stderr)
        return 2
    paths = desktop_paths().create()
    os.environ["JAFAR_DESKTOP_STATE_DIR"] = str(paths.application_support)
    os.environ["JAFAR_DESKTOP_LOG_DIR"] = str(paths.logs)
    os.environ["JAFAR_DESKTOP_CACHE_DIR"] = str(paths.cache)
    parent_pid = os.getenv("JAFAR_DESKTOP_PARENT_PID", "").strip()
    if parent_pid:
        threading.Thread(
            target=_stop_if_parent_exits,
            args=(int(parent_pid),),
            daemon=True,
            name="jafar-desktop-parent-monitor",
        ).start()

    import uvicorn

    uvicorn.run("jafar.main:app", host=LOOPBACK_HOST, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the frozen binary
    raise SystemExit(main())
