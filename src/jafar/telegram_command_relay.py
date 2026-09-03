from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
BRIDGE_HOME = Path.home() / ".jafar-command-bridge"

PRIVATE_KEY_PATH = (
    BRIDGE_HOME / "private.pem"
)

STATE_PATH = (
    BRIDGE_HOME / "processed.json"
)

REMOTE = "origin"
QUEUE_BRANCH = "jafar-command-queue"

QUEUE_PREFIX = "queue/"
STATUS_PREFIX = "status/"


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO,
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


def decrypt_envelope(
    raw: str,
) -> dict[str, Any]:
    envelope = json.loads(raw)

    if envelope.get("v") != 1:
        raise ValueError(
            "unsupported relay envelope"
        )

    private_key = _load_private_key()

    wrapped = base64.b64decode(
        envelope["wrapped_key"]
    )

    aes_key = private_key.decrypt(
        wrapped,
        padding.OAEP(
            mgf=padding.MGF1(
                algorithm=hashes.SHA256()
            ),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    nonce = base64.b64decode(
        envelope["nonce"]
    )

    ciphertext = base64.b64decode(
        envelope["ciphertext"]
    )

    plaintext = AESGCM(
        aes_key
    ).decrypt(
        nonce,
        ciphertext,
        None,
    )

    return json.loads(
        plaintext.decode()
    )


def _load_processed() -> set[str]:
    if not STATE_PATH.exists():
        return set()

    data = json.loads(
        STATE_PATH.read_text()
    )

    return set(
        data.get("processed", [])
    )


def _save_processed(
    processed: set[str],
) -> None:
    BRIDGE_HOME.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATE_PATH.write_text(
        json.dumps(
            {
                "processed": sorted(
                    processed
                )
            },
            indent=2,
        )
        + "\n"
    )

    os.chmod(
        STATE_PATH,
        0o600,
    )


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
        if line.strip().endswith(
            ".jafarcmd"
        )
    ]


def _read_remote_file(
    path: str,
) -> str:
    return _git(
        "show",
        f"{REMOTE}/{QUEUE_BRANCH}:{path}",
    )


def _validate_command(
    command: dict[str, Any],
) -> None:
    if command.get("version") != 1:
        raise ValueError(
            "unsupported command version"
        )

    command_id = command.get(
        "command_id"
    )

    if (
        not isinstance(command_id, str)
        or len(command_id) < 16
    ):
        raise ValueError(
            "invalid command_id"
        )

    allowed = {
        "dry_run_probe",
    }

    if command.get("action") not in allowed:
        raise ValueError(
            "relay action is not enabled"
        )


def _execute(
    command: dict[str, Any],
) -> None:
    action = command["action"]

    if action == "dry_run_probe":
        digest = hashlib.sha256(
            json.dumps(
                command,
                sort_keys=True,
            ).encode()
        ).hexdigest()

        logger.info(
            "accepted encrypted relay "
            "dry-run command_id=%s "
            "digest=%s",
            command["command_id"],
            digest[:16],
        )

        return

    raise ValueError(
        "unsupported relay action"
    )


def run_once() -> int:
    if not PRIVATE_KEY_PATH.exists():
        raise RuntimeError(
            "relay private key missing"
        )

    _git(
        "fetch",
        "--quiet",
        REMOTE,
        QUEUE_BRANCH,
    )

    processed = _load_processed()

    count = 0

    for path in _list_queue_files():

        name = Path(path).stem

        if name in processed:
            continue

        raw = _read_remote_file(
            path
        )

        command = decrypt_envelope(
            raw
        )

        _validate_command(
            command
        )

        if (
            command["command_id"]
            != name
        ):
            raise ValueError(
                "filename / command_id mismatch"
            )

        _execute(
            command
        )

        processed.add(
            name
        )

        _save_processed(
            processed
        )

        count += 1

    return count


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(message)s"
        ),
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
