"""Read-only owner readiness report for the JAFAR Telegram command bridge."""

from __future__ import annotations

import os
import socket
import subprocess
import asyncio
from urllib.request import urlopen

from jafar.config import settings
from jafar.telegram_command_relay import PRIVATE_KEY_PATH
from jafar.telegram_mcp import _allowed_chat_ids, mcp
from jafar.telegram_security import validate_telegram_settings


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _mcp_reachable() -> bool:
    try:
        port = int(os.environ.get("JAFAR_MCP_PORT", "8000"))
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except (OSError, ValueError):
        return False


def _ngrok_healthy() -> bool:
    try:
        with urlopen("http://127.0.0.1:4040/api/tunnels", timeout=0.5) as response:  # noqa: S310
            return response.status == 200
    except OSError:
        return False


def _relay_healthy() -> bool:
    if not PRIVATE_KEY_PATH.is_file():
        return False
    try:
        for ref in (
            "origin/jafar-command-queue",
            "origin/jafar-command-status",
            "origin/jafar-media",
        ):
            subprocess.run(
                ["git", "rev-parse", "--verify", ref],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except subprocess.CalledProcessError:
        return False
    return True


def main() -> None:
    try:
        validate_telegram_settings(settings)
        settings_valid = True
    except RuntimeError:
        settings_valid = False

    tools = asyncio.run(mcp.list_tools())
    mcp_reachable = _mcp_reachable()
    relay_healthy = _relay_healthy()
    ngrok_healthy = _ngrok_healthy()
    live_send = bool(settings.telegram_production_send and not settings.telegram_dry_run)
    ready = bool(
        settings_valid
        and mcp_reachable
        and relay_healthy
        and ngrok_healthy
        and _allowed_chat_ids()
        and settings.telegram_owner_approver_id
        and settings.jafar_mcp_auth_token
        and not live_send
    )

    values = {
        "branch": _git("branch", "--show-current"),
        "head_sha": _git("rev-parse", "HEAD"),
        "mcp_reachable": mcp_reachable,
        "mcp_tools_count": len(tools),
        "scheduler_enabled": settings.telegram_scheduler_enabled,
        "command_relay_health": relay_healthy,
        "ngrok_health": ngrok_healthy,
        "allowed_chat_count": len(_allowed_chat_ids()),
        "owner_approval_configured": bool(settings.telegram_owner_approver_id),
        "remote_auth_configured": bool(settings.jafar_mcp_auth_token),
        "text_supported": True,
        "photo_supported": True,
        "video_supported": True,
        "private_media_relay_supported": True,
        "status_return_supported": True,
        "dry_run": settings.telegram_dry_run,
        "production_send": settings.telegram_production_send,
    }
    for key, value in values.items():
        print(f"{key.upper()}={str(value).lower() if isinstance(value, bool) else value}")
    print(f"READY_FOR_OWNER_LIVE_SMOKE={str(ready).lower()}")
    print(f"LIVE_SEND_ENABLED={str(live_send).lower()}")


if __name__ == "__main__":
    main()
