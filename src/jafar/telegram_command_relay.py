from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx2
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
BRIDGE_HOME = Path.home() / ".jafar-command-bridge"

PRIVATE_KEY_PATH = BRIDGE_HOME / "private.pem"
STATE_PATH = BRIDGE_HOME / "processed.json"
INFLIGHT_PATH = BRIDGE_HOME / "inflight.json"
OUTBOX_PATH = BRIDGE_HOME / "status-outbox.json"
STATUS_WORKTREE = BRIDGE_HOME / "status-worktree"

REMOTE = "origin"
QUEUE_BRANCH = "jafar-command-queue"
STATUS_BRANCH = "jafar-command-status"

QUEUE_PREFIX = "queue/"
STATUS_PREFIX = "status/"

ALLOWED_ACTIONS = {
    "dry_run_probe",
    "create_post_draft",
    "get_approval",
    "list_recent_approvals",
    "list_scheduled_posts",
    "owner_approve_and_schedule",
}

FORBIDDEN_ACTIONS = {
    "publish",
    "send",
    "schedule",
    "approve_publication",
    "execute_approved",
    "telegram_approve_publication",
    "telegram_execute_approved",
}


def _git(*args: str, cwd: Path = REPO) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout


def _load_private_key():
    return serialization.load_pem_private_key(
        PRIVATE_KEY_PATH.read_bytes(),
        password=None,
    )


def decrypt_envelope(raw: str) -> dict[str, Any]:
    envelope = json.loads(raw)

    if envelope.get("v") != 1:
        raise ValueError("unsupported relay envelope")

    private_key = _load_private_key()

    wrapped = base64.b64decode(envelope["wrapped_key"])
    aes_key = private_key.decrypt(
        wrapped,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    nonce = base64.b64decode(envelope["nonce"])
    ciphertext = base64.b64decode(envelope["ciphertext"])

    plaintext = AESGCM(aes_key).decrypt(
        nonce,
        ciphertext,
        None,
    )

    decoded = json.loads(plaintext.decode())
    if not isinstance(decoded, dict):
        raise ValueError("relay payload must be an object")
    return decoded


def _load_string_set(path: Path, key: str) -> set[str]:
    if not path.exists():
        return set()

    data = json.loads(path.read_text())
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"invalid relay state: {key}")
    return {str(item) for item in value}


def _save_string_set(path: Path, key: str, values: set[str]) -> None:
    BRIDGE_HOME.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {key: sorted(values)},
            indent=2,
        )
        + "\n"
    )
    os.chmod(path, 0o600)


def _load_processed() -> set[str]:
    return _load_string_set(STATE_PATH, "processed")


def _save_processed(processed: set[str]) -> None:
    _save_string_set(STATE_PATH, "processed", processed)


def _load_inflight() -> set[str]:
    return _load_string_set(INFLIGHT_PATH, "inflight")


def _save_inflight(inflight: set[str]) -> None:
    _save_string_set(INFLIGHT_PATH, "inflight", inflight)


def _load_outbox() -> dict[str, dict[str, Any]]:
    if not OUTBOX_PATH.exists():
        return {}

    data = json.loads(OUTBOX_PATH.read_text())
    items = data.get("items", {})
    if not isinstance(items, dict):
        raise ValueError("invalid status outbox")
    return {
        str(key): value
        for key, value in items.items()
        if isinstance(value, dict)
    }


def _save_outbox(items: dict[str, dict[str, Any]]) -> None:
    BRIDGE_HOME.mkdir(parents=True, exist_ok=True)
    OUTBOX_PATH.write_text(
        json.dumps(
            {"items": items},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    os.chmod(OUTBOX_PATH, 0o600)


def _queue_status(status: dict[str, Any]) -> None:
    command_id = str(status["command_id"])
    items = _load_outbox()
    items[command_id] = status
    _save_outbox(items)


def _ensure_status_worktree() -> None:
    if not STATUS_WORKTREE.exists():
        raise RuntimeError("relay status worktree missing")


def _write_status_remote(status: dict[str, Any]) -> None:
    _ensure_status_worktree()

    command_id = str(status["command_id"])
    target = STATUS_WORKTREE / STATUS_PREFIX / f"{command_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)

    _git("fetch", "--quiet", REMOTE, STATUS_BRANCH, cwd=STATUS_WORKTREE)
    _git("reset", "--hard", f"{REMOTE}/{STATUS_BRANCH}", cwd=STATUS_WORKTREE)

    target.write_text(
        json.dumps(
            status,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    _git("add", str(target.relative_to(STATUS_WORKTREE)), cwd=STATUS_WORKTREE)

    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=STATUS_WORKTREE,
        check=False,
    )
    if diff.returncode == 0:
        return
    if diff.returncode != 1:
        raise RuntimeError("unable to inspect relay status diff")

    _git(
        "commit",
        "-m",
        f"relay: status {command_id}",
        cwd=STATUS_WORKTREE,
    )
    _git(
        "push",
        "--quiet",
        REMOTE,
        f"HEAD:{STATUS_BRANCH}",
        cwd=STATUS_WORKTREE,
    )


def _flush_status_outbox() -> None:
    items = _load_outbox()
    if not items:
        return

    remaining = dict(items)

    for command_id, status in items.items():
        try:
            _write_status_remote(status)
        except Exception as exc:
            logger.error(
                "relay status push failed command_id=%s error=%s",
                command_id,
                type(exc).__name__,
            )
            continue

        remaining.pop(command_id, None)
        _save_outbox(remaining)


def _list_queue_files() -> list[str]:
    try:
        output = _git(
            "ls-tree",
            "-r",
            "--name-only",
            f"{REMOTE}/{QUEUE_BRANCH}",
            QUEUE_PREFIX,
        )
    except subprocess.CalledProcessError:
        return []

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip().endswith(".jafarcmd")
    ]


def _read_remote_file(path: str) -> str:
    return _git(
        "show",
        f"{REMOTE}/{QUEUE_BRANCH}:{path}",
    )


def _validate_command(command: dict[str, Any]) -> None:
    if command.get("version") != 1:
        raise ValueError("unsupported command version")

    command_id = command.get("command_id")
    if not isinstance(command_id, str) or len(command_id) < 16:
        raise ValueError("invalid command_id")

    action = command.get("action")
    if action in FORBIDDEN_ACTIONS:
        raise ValueError("relay action is forbidden")
    if action not in ALLOWED_ACTIONS:
        raise ValueError("relay action is not enabled")

    if action == "create_post_draft":
        allowed_keys = {
            "version",
            "command_id",
            "action",
            "chat_id",
            "text",
            "scheduled_for",
            "photo_url",
            "filename",
        }
        unknown = set(command) - allowed_keys
        if unknown:
            raise ValueError("unexpected create_post_draft fields")

        if not isinstance(command.get("chat_id"), (str, int)):
            raise ValueError("chat_id is required")

        text = command.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if len(text) > 50000:
            raise ValueError("text is too large")

        scheduled_for = command.get("scheduled_for")
        if scheduled_for is not None and not isinstance(scheduled_for, str):
            raise ValueError("scheduled_for must be a string")

        photo_url = command.get("photo_url")
        if photo_url is not None and not isinstance(photo_url, str):
            raise ValueError("photo_url must be a string")

        filename = command.get("filename")
        if filename is not None and not isinstance(filename, str):
            raise ValueError("filename must be a string")

    elif action == "owner_approve_and_schedule":
        allowed_keys = {
            "version",
            "command_id",
            "action",
            "approval_id",
            "expected_payload_hash",
            "expected_chat_id",
            "expected_scheduled_for",
            "owner_confirmation",
        }

        unknown = set(command) - allowed_keys
        if unknown:
            raise ValueError(
                "unexpected owner_approve_and_schedule fields"
            )

        approval_id = command.get("approval_id")
        if (
            not isinstance(approval_id, str)
            or not approval_id.strip()
        ):
            raise ValueError("approval_id is required")

        payload_hash = command.get(
            "expected_payload_hash"
        )
        if (
            not isinstance(payload_hash, str)
            or len(payload_hash) != 64
            or any(
                char not in "0123456789abcdef"
                for char in payload_hash
            )
        ):
            raise ValueError(
                "expected_payload_hash must be lowercase sha256"
            )

        if not isinstance(
            command.get("expected_chat_id"),
            (str, int),
        ):
            raise ValueError(
                "expected_chat_id is required"
            )

        scheduled_for = command.get(
            "expected_scheduled_for"
        )
        if (
            not isinstance(scheduled_for, str)
            or not scheduled_for.strip()
        ):
            raise ValueError(
                "expected_scheduled_for is required"
            )

        if command.get(
            "owner_confirmation"
        ) != "APPROVE":
            raise ValueError(
                "explicit owner confirmation is required"
            )

    elif action == "get_approval":
        allowed_keys = {
            "version",
            "command_id",
            "action",
            "approval_id",
        }
        if set(command) - allowed_keys:
            raise ValueError("unexpected get_approval fields")
        approval_id = command.get("approval_id")
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise ValueError("approval_id is required")

    elif action == "list_recent_approvals":
        allowed_keys = {
            "version",
            "command_id",
            "action",
            "limit",
        }
        if set(command) - allowed_keys:
            raise ValueError("unexpected list_recent_approvals fields")
        limit = command.get("limit", 20)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

    elif action in {"dry_run_probe", "list_scheduled_posts"}:
        allowed_keys = {
            "version",
            "command_id",
            "action",
        }
        if set(command) - allowed_keys:
            raise ValueError("unexpected relay fields")


def _read_env_file() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (REPO / ".env").read_text().splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


async def _call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    env = _read_env_file()
    token = env.get("JAFAR_MCP_AUTH_TOKEN", "")
    if not token:
        raise RuntimeError("MCP auth token missing")

    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    ) as client:
        async with streamable_http_client(
            "http://127.0.0.1:8000/mcp",
            http_client=client,
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    tool_name,
                    arguments,
                )

    if getattr(result, "is_error", False):
        raise RuntimeError("MCP tool returned an error")

    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured

    content = getattr(result, "content", None)
    if isinstance(content, list):
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed

    raise RuntimeError("MCP tool returned no structured result")


def _execute(command: dict[str, Any]) -> dict[str, Any]:
    action = str(command["action"])

    if action == "dry_run_probe":
        digest = hashlib.sha256(
            json.dumps(
                command,
                sort_keys=True,
            ).encode()
        ).hexdigest()

        logger.info(
            "accepted encrypted relay dry-run command_id=%s digest=%s",
            command["command_id"],
            digest[:16],
        )

        return {
            "ok": True,
            "action": action,
            "digest_prefix": digest[:16],
        }

    if action == "create_post_draft":
        arguments: dict[str, Any] = {
            "chat_id": command["chat_id"],
            "text": command["text"],
            "requested_by": "chatgpt-project-relay",
        }

        if command.get("scheduled_for") is not None:
            arguments["scheduled_for"] = command["scheduled_for"]

        if command.get("photo_url") is not None:
            arguments["photo_url"] = command["photo_url"]

        if command.get("filename") is not None:
            arguments["filename"] = command["filename"]

        result = asyncio.run(
            _call_mcp_tool(
                "telegram_create_post_draft",
                arguments,
            )
        )
        return {
            "ok": True,
            "action": action,
            "approval": result,
        }

    if action == "owner_approve_and_schedule":
        approval_id = str(
            command["approval_id"]
        ).strip()

        expected_hash = str(
            command["expected_payload_hash"]
        )

        expected_chat = str(
            command["expected_chat_id"]
        )

        expected_schedule = str(
            command["expected_scheduled_for"]
        )

        current = asyncio.run(
            _call_mcp_tool(
                "telegram_get_approval",
                {
                    "approval_id":
                        approval_id,
                },
            )
        )

        if current.get("state") != "proposed":
            raise PermissionError(
                "approval is not in proposed state"
            )

        if str(
            current.get("chat_id")
        ) != expected_chat:
            raise PermissionError(
                "approval chat binding changed"
            )

        if current.get(
            "payload_hash"
        ) != expected_hash:
            raise PermissionError(
                "approval payload hash changed"
            )

        actual_schedule = current.get(
            "scheduled_for"
        )

        if actual_schedule != expected_schedule:
            raise PermissionError(
                "approval schedule binding changed"
            )

        if not actual_schedule:
            raise PermissionError(
                "immediate publication is forbidden "
                "through owner_approve_and_schedule"
            )

        try:
            scheduled_dt = datetime.fromisoformat(
                str(actual_schedule)
            )
        except ValueError as exc:
            raise ValueError(
                "invalid scheduled_for timestamp"
            ) from exc

        if scheduled_dt.tzinfo is None:
            raise ValueError(
                "scheduled_for must include timezone"
            )

        minimum_time = (
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        )

        if (
            scheduled_dt.astimezone(
                timezone.utc
            )
            <= minimum_time
        ):
            raise PermissionError(
                "relay scheduling requires "
                "at least 5 minutes lead time"
            )

        env = _read_env_file()

        owner = env.get(
            "TELEGRAM_OWNER_APPROVER_ID",
            "",
        ).strip()

        if not owner:
            raise RuntimeError(
                "owner approver is not configured"
            )

        approved = asyncio.run(
            _call_mcp_tool(
                "telegram_approve_publication",
                {
                    "approval_id":
                        approval_id,
                    "approver":
                        owner,
                    "confirmation":
                        command[
                            "owner_confirmation"
                        ],
                },
            )
        )

        if approved.get(
            "state"
        ) != "approved":
            raise RuntimeError(
                "approval did not enter approved state"
            )

        execution = asyncio.run(
            _call_mcp_tool(
                "telegram_execute_approved",
                {
                    "approval_id":
                        approval_id,
                },
            )
        )

        scheduled = execution.get(
            "scheduled"
        )

        if not isinstance(
            scheduled,
            dict,
        ):
            raise RuntimeError(
                "owner relay may only schedule "
                "future publications"
            )

        return {
            "ok": True,
            "action": action,
            "approval": approved,
            "execution": execution,
        }

    if action == "get_approval":
        result = asyncio.run(
            _call_mcp_tool(
                "telegram_get_approval",
                {"approval_id": command["approval_id"]},
            )
        )
        return {
            "ok": True,
            "action": action,
            "approval": result,
        }

    if action == "list_recent_approvals":
        result = asyncio.run(
            _call_mcp_tool(
                "telegram_list_recent_approvals",
                {"limit": command.get("limit", 20)},
            )
        )
        return {
            "ok": True,
            "action": action,
            "approvals": result,
        }

    if action == "list_scheduled_posts":
        result = asyncio.run(
            _call_mcp_tool(
                "telegram_list_scheduled_posts",
                {},
            )
        )
        return {
            "ok": True,
            "action": action,
            "scheduled": result,
        }

    raise ValueError("unsupported relay action")


def _status_record(
    *,
    command: dict[str, Any],
    state: str,
    result: dict[str, Any] | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "version": 1,
        "command_id": str(command["command_id"]),
        "action": str(command["action"]),
        "state": state,
        "timestamp": int(time.time()),
    }
    if result is not None:
        record["result"] = result
    if error_type is not None:
        record["error_type"] = error_type
    return record


def run_once() -> int:
    if not PRIVATE_KEY_PATH.exists():
        raise RuntimeError("relay private key missing")

    _flush_status_outbox()

    _git(
        "fetch",
        "--quiet",
        REMOTE,
        QUEUE_BRANCH,
    )

    processed = _load_processed()
    inflight = _load_inflight()

    count = 0

    for path in _list_queue_files():
        name = Path(path).stem

        if name in processed:
            continue

        raw = _read_remote_file(path)
        command = decrypt_envelope(raw)
        _validate_command(command)

        if command["command_id"] != name:
            raise ValueError("filename / command_id mismatch")

        if name in inflight:
            status = _status_record(
                command=command,
                state="execution_uncertain",
                error_type="PreviousExecutionInterrupted",
            )
            processed.add(name)
            inflight.discard(name)
            _save_processed(processed)
            _save_inflight(inflight)
            _queue_status(status)
            count += 1
            continue

        inflight.add(name)
        _save_inflight(inflight)

        try:
            result = _execute(command)
            status = _status_record(
                command=command,
                state="completed",
                result=result,
            )
        except Exception as exc:
            status = _status_record(
                command=command,
                state="failed",
                error_type=type(exc).__name__,
            )

        processed.add(name)
        inflight.discard(name)
        _save_processed(processed)
        _save_inflight(inflight)
        _queue_status(status)

        count += 1

    _flush_status_outbox()
    return count


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    while True:
        try:
            run_once()
        except Exception as exc:
            logger.error(
                "relay cycle failed: %s",
                type(exc).__name__,
            )

        time.sleep(30)


if __name__ == "__main__":
    main()
