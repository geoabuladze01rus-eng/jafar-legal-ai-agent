from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from jafar import telegram_command_relay as relay


def test_decrypt_envelope(monkeypatch, tmp_path):
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    private_path = tmp_path / "private.pem"

    private_path.write_bytes(
        key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption(),
        )
    )

    monkeypatch.setattr(
        relay,
        "PRIVATE_KEY_PATH",
        private_path,
    )

    payload = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "dry_run_probe",
    }

    plaintext = json.dumps(payload).encode()

    aes_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)

    ciphertext = AESGCM(aes_key).encrypt(
        nonce,
        plaintext,
        None,
    )

    wrapped = key.public_key().encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(
                hashes.SHA256()
            ),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    envelope = json.dumps(
        {
            "v": 1,
            "wrapped_key":
                base64.b64encode(
                    wrapped
                ).decode(),
            "nonce":
                base64.b64encode(
                    nonce
                ).decode(),
            "ciphertext":
                base64.b64encode(
                    ciphertext
                ).decode(),
        }
    )

    assert relay.decrypt_envelope(envelope) == payload


def test_reject_unknown_action():
    command = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "publish_immediately",
    }

    try:
        relay._validate_command(command)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "unsafe action accepted"
        )


def test_reject_approval_and_execution_actions():
    for action in (
        "publish",
        "send",
        "schedule",
        "approve_publication",
        "execute_approved",
        "telegram_approve_publication",
        "telegram_execute_approved",
    ):
        command = {
            "version": 1,
            "command_id": "1234567890abcdef",
            "action": action,
        }

        try:
            relay._validate_command(command)
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"unsafe action accepted: {action}"
            )


def test_accept_create_post_draft():
    command = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "create_post_draft",
        "chat_id": "-1001234567890",
        "text": "draft only",
        "scheduled_for": "2026-09-04T09:00:00+03:00",
    }

    relay._validate_command(command)


def test_create_post_draft_rejects_extra_fields():
    command = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "create_post_draft",
        "chat_id": "-1001234567890",
        "text": "draft only",
        "confirmation": "APPROVE",
    }

    try:
        relay._validate_command(command)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "unexpected approval field accepted"
        )


def test_execute_create_post_draft_calls_only_draft_tool(monkeypatch):
    calls = []

    async def fake_call(tool_name, arguments):
        calls.append((tool_name, arguments))
        return {
            "approval_id": "approval-123",
            "state": "proposed",
            "message_id": None,
        }

    monkeypatch.setattr(
        relay,
        "_call_mcp_tool",
        fake_call,
    )

    result = relay._execute(
        {
            "version": 1,
            "command_id": "1234567890abcdef",
            "action": "create_post_draft",
            "chat_id": "-1001234567890",
            "text": "draft only",
            "scheduled_for": "2026-09-04T09:00:00+03:00",
        }
    )

    assert calls == [
        (
            "telegram_create_post_draft",
            {
                "chat_id": "-1001234567890",
                "text": "draft only",
                "requested_by": "chatgpt-project-relay",
                "scheduled_for": "2026-09-04T09:00:00+03:00",
            },
        )
    ]

    assert result["approval"]["state"] == "proposed"


def test_inflight_command_becomes_uncertain_without_reexecution(
    monkeypatch,
    tmp_path,
):
    state = tmp_path / "processed.json"
    inflight = tmp_path / "inflight.json"
    outbox = tmp_path / "outbox.json"

    monkeypatch.setattr(relay, "STATE_PATH", state)
    monkeypatch.setattr(relay, "INFLIGHT_PATH", inflight)
    monkeypatch.setattr(relay, "OUTBOX_PATH", outbox)
    monkeypatch.setattr(
        relay,
        "PRIVATE_KEY_PATH",
        tmp_path / "private.pem",
    )
    relay.PRIVATE_KEY_PATH.write_text("placeholder")

    command_id = "1234567890abcdef"
    relay._save_inflight({command_id})

    command = {
        "version": 1,
        "command_id": command_id,
        "action": "dry_run_probe",
    }

    monkeypatch.setattr(
        relay,
        "_flush_status_outbox",
        lambda: None,
    )
    monkeypatch.setattr(
        relay,
        "_git",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        relay,
        "_list_queue_files",
        lambda: [f"queue/{command_id}.jafarcmd"],
    )
    monkeypatch.setattr(
        relay,
        "_read_remote_file",
        lambda path: "{}",
    )
    monkeypatch.setattr(
        relay,
        "decrypt_envelope",
        lambda raw: command,
    )

    executed = []

    monkeypatch.setattr(
        relay,
        "_execute",
        lambda cmd: executed.append(cmd),
    )

    count = relay.run_once()

    assert count == 1
    assert executed == []
    assert command_id in relay._load_processed()
    assert command_id not in relay._load_inflight()

    status = relay._load_outbox()[command_id]
    assert status["state"] == "execution_uncertain"
