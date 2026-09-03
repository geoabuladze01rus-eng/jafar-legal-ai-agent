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



def test_accept_owner_approve_and_schedule():
    command = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "owner_approve_and_schedule",
        "approval_id": "approval-123",
        "expected_payload_hash": "a" * 64,
        "expected_chat_id": "-1001234567890",
        "expected_scheduled_for":
            "2099-09-10T06:00:00+00:00",
        "owner_confirmation": "APPROVE",
    }

    relay._validate_command(command)


def test_owner_approve_requires_explicit_confirmation():
    command = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "owner_approve_and_schedule",
        "approval_id": "approval-123",
        "expected_payload_hash": "a" * 64,
        "expected_chat_id": "-1001234567890",
        "expected_scheduled_for":
            "2099-09-10T06:00:00+00:00",
        "owner_confirmation": "YES",
    }

    try:
        relay._validate_command(command)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "non-APPROVE confirmation accepted"
        )


def test_owner_approve_rejects_invalid_payload_hash():
    command = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "owner_approve_and_schedule",
        "approval_id": "approval-123",
        "expected_payload_hash": "wrong",
        "expected_chat_id": "-1001234567890",
        "expected_scheduled_for":
            "2099-09-10T06:00:00+00:00",
        "owner_confirmation": "APPROVE",
    }

    try:
        relay._validate_command(command)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "invalid payload hash accepted"
        )


def test_owner_approve_and_schedule_is_hash_bound(
    monkeypatch,
):
    calls = []

    async def fake_call(
        tool_name,
        arguments,
    ):
        calls.append(
            (tool_name, arguments)
        )

        if tool_name == "telegram_get_approval":
            return {
                "approval_id":
                    "approval-123",
                "state":
                    "proposed",
                "chat_id":
                    "-1001234567890",
                "payload_hash":
                    "a" * 64,
                "scheduled_for":
                    "2099-09-10T06:00:00+00:00",
            }

        if tool_name == "telegram_approve_publication":
            return {
                "approval_id":
                    "approval-123",
                "state":
                    "approved",
                "chat_id":
                    "-1001234567890",
                "payload_hash":
                    "a" * 64,
                "scheduled_for":
                    "2099-09-10T06:00:00+00:00",
            }

        if tool_name == "telegram_execute_approved":
            return {
                "ok": True,
                "approval_id":
                    "approval-123",
                "scheduled": {
                    "id":
                        "schedule-123",
                    "status":
                        "pending",
                },
            }

        raise AssertionError(
            f"unexpected MCP tool: {tool_name}"
        )

    monkeypatch.setattr(
        relay,
        "_call_mcp_tool",
        fake_call,
    )

    monkeypatch.setattr(
        relay,
        "_read_env_file",
        lambda: {
            "TELEGRAM_OWNER_APPROVER_ID":
                "artur-owner",
        },
    )

    result = relay._execute(
        {
            "version": 1,
            "command_id":
                "1234567890abcdef",
            "action":
                "owner_approve_and_schedule",
            "approval_id":
                "approval-123",
            "expected_payload_hash":
                "a" * 64,
            "expected_chat_id":
                "-1001234567890",
            "expected_scheduled_for":
                "2099-09-10T06:00:00+00:00",
            "owner_confirmation":
                "APPROVE",
        }
    )

    assert calls == [
        (
            "telegram_get_approval",
            {
                "approval_id":
                    "approval-123",
            },
        ),
        (
            "telegram_approve_publication",
            {
                "approval_id":
                    "approval-123",
                "approver":
                    "artur-owner",
                "confirmation":
                    "APPROVE",
            },
        ),
        (
            "telegram_execute_approved",
            {
                "approval_id":
                    "approval-123",
            },
        ),
    ]

    assert result["ok"] is True
    assert (
        result["execution"]
        ["scheduled"]
        ["id"]
        == "schedule-123"
    )


def test_owner_approve_rejects_hash_mismatch(
    monkeypatch,
):
    calls = []

    async def fake_call(
        tool_name,
        arguments,
    ):
        calls.append(
            (tool_name, arguments)
        )

        return {
            "approval_id":
                "approval-123",
            "state":
                "proposed",
            "chat_id":
                "-1001234567890",
            "payload_hash":
                "b" * 64,
            "scheduled_for":
                "2099-09-10T06:00:00+00:00",
        }

    monkeypatch.setattr(
        relay,
        "_call_mcp_tool",
        fake_call,
    )

    try:
        relay._execute(
            {
                "version": 1,
                "command_id":
                    "1234567890abcdef",
                "action":
                    "owner_approve_and_schedule",
                "approval_id":
                    "approval-123",
                "expected_payload_hash":
                    "a" * 64,
                "expected_chat_id":
                    "-1001234567890",
                "expected_scheduled_for":
                    "2099-09-10T06:00:00+00:00",
                "owner_confirmation":
                    "APPROVE",
            }
        )
    except PermissionError:
        pass
    else:
        raise AssertionError(
            "payload hash mismatch accepted"
        )

    assert [
        name
        for name, _ in calls
    ] == [
        "telegram_get_approval"
    ]


def test_owner_approve_rejects_immediate_publication(
    monkeypatch,
):
    calls = []

    async def fake_call(
        tool_name,
        arguments,
    ):
        calls.append(
            (tool_name, arguments)
        )

        return {
            "approval_id":
                "approval-123",
            "state":
                "proposed",
            "chat_id":
                "-1001234567890",
            "payload_hash":
                "a" * 64,
            "scheduled_for":
                None,
        }

    monkeypatch.setattr(
        relay,
        "_call_mcp_tool",
        fake_call,
    )

    try:
        relay._execute(
            {
                "version": 1,
                "command_id":
                    "1234567890abcdef",
                "action":
                    "owner_approve_and_schedule",
                "approval_id":
                    "approval-123",
                "expected_payload_hash":
                    "a" * 64,
                "expected_chat_id":
                    "-1001234567890",
                "expected_scheduled_for":
                    "2099-09-10T06:00:00+00:00",
                "owner_confirmation":
                    "APPROVE",
            }
        )
    except PermissionError:
        pass
    else:
        raise AssertionError(
            "immediate publication path accepted"
        )

    assert [
        name
        for name, _ in calls
    ] == [
        "telegram_get_approval"
    ]



def test_accept_private_media_post_draft():
    command = {
        "version": 1,
        "command_id":
            "1234567890abcdef",
        "action":
            "create_post_draft",
        "chat_id":
            "-1001234567890",
        "text":
            "draft with private image",
        "scheduled_for":
            "2099-09-10T06:00:00+00:00",
        "media_path":
            "media/test.png",
        "media_sha256":
            "a" * 64,
        "filename":
            "test.png",
    }

    relay._validate_command(
        command
    )


def test_private_media_rejects_path_traversal():

    command = {
        "version": 1,
        "command_id":
            "1234567890abcdef",
        "action":
            "create_post_draft",
        "chat_id":
            "-1001234567890",
        "text":
            "draft",
        "media_path":
            "media/../secret.png",
        "media_sha256":
            "a" * 64,
    }

    try:

        relay._validate_command(
            command
        )

    except ValueError:
        pass

    else:

        raise AssertionError(
            "path traversal accepted"
        )


def test_private_media_requires_sha256():

    command = {
        "version": 1,
        "command_id":
            "1234567890abcdef",
        "action":
            "create_post_draft",
        "chat_id":
            "-1001234567890",
        "text":
            "draft",
        "media_path":
            "media/test.png",
    }

    try:

        relay._validate_command(
            command
        )

    except ValueError:
        pass

    else:

        raise AssertionError(
            "media without hash accepted"
        )


def test_private_media_rejects_direct_base64():

    command = {
        "version": 1,
        "command_id":
            "1234567890abcdef",
        "action":
            "create_post_draft",
        "chat_id":
            "-1001234567890",
        "text":
            "draft",
        "photo_base64":
            "unsafe-direct-payload",
    }

    try:

        relay._validate_command(
            command
        )

    except ValueError:
        pass

    else:

        raise AssertionError(
            "direct photo_base64 relay accepted"
        )


def test_private_media_rejects_hash_mismatch(
    monkeypatch,
):

    monkeypatch.setattr(
        relay,
        "_git",
        lambda *args, **kwargs: "",
    )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + b"test-image-data"
    )

    monkeypatch.setattr(
        relay,
        "_git_bytes",
        lambda *args, **kwargs: png,
    )

    try:

        relay._load_private_media(
            "media/test.png",
            "0" * 64,
        )

    except PermissionError:
        pass

    else:

        raise AssertionError(
            "media hash mismatch accepted"
        )


def test_private_media_rejects_fake_image(
    monkeypatch,
):

    monkeypatch.setattr(
        relay,
        "_git",
        lambda *args, **kwargs: "",
    )

    content = (
        b"this is not an image"
    )

    monkeypatch.setattr(
        relay,
        "_git_bytes",
        lambda *args, **kwargs:
            content,
    )

    import hashlib

    digest = hashlib.sha256(
        content
    ).hexdigest()

    try:

        relay._load_private_media(
            "media/fake.png",
            digest,
        )

    except ValueError:
        pass

    else:

        raise AssertionError(
            "fake image accepted"
        )


def test_private_media_draft_passes_bytes_to_mcp(
    monkeypatch,
):

    import base64
    import hashlib

    png = (
        b"\x89PNG\r\n\x1a\n"
        + b"private-test-image"
    )

    digest = hashlib.sha256(
        png
    ).hexdigest()

    calls = []

    monkeypatch.setattr(
        relay,
        "_git",
        lambda *args, **kwargs: "",
    )

    monkeypatch.setattr(
        relay,
        "_git_bytes",
        lambda *args, **kwargs:
            png,
    )

    async def fake_call(
        tool_name,
        arguments,
    ):

        calls.append(
            (
                tool_name,
                arguments,
            )
        )

        return {
            "approval_id":
                "approval-photo-123",
            "state":
                "proposed",
            "message_id":
                None,
        }

    monkeypatch.setattr(
        relay,
        "_call_mcp_tool",
        fake_call,
    )

    result = relay._execute(
        {
            "version": 1,
            "command_id":
                "1234567890abcdef",
            "action":
                "create_post_draft",
            "chat_id":
                "-1001234567890",
            "text":
                "draft with image",
            "scheduled_for":
                "2099-09-10T06:00:00+00:00",
            "media_path":
                "media/test.png",
            "media_sha256":
                digest,
        }
    )

    assert len(calls) == 1

    tool_name, arguments = (
        calls[0]
    )

    assert (
        tool_name
        == "telegram_create_post_draft"
    )

    assert (
        arguments["filename"]
        == "test.png"
    )

    assert (
        arguments.get(
            "photo_url"
        )
        is None
    )

    decoded = base64.b64decode(
        arguments[
            "photo_base64"
        ]
    )

    assert decoded == png

    assert (
        result["approval"]["state"]
        == "proposed"
    )


def test_video_command_requires_safe_private_mp4_reference():
    command = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "create_post_draft",
        "chat_id": "-1001234567890",
        "text": "encrypted video draft",
        "video_path": "media/smoke.mp4",
        "video_sha256": "a" * 64,
        "video_filename": "smoke.mp4",
    }
    relay._validate_command(command)

    for field, value in (("video_path", "media/../secret.mp4"), ("video_path", "media/test.png")):
        invalid = dict(command)
        invalid[field] = value
        try:
            relay._validate_command(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe video reference accepted")

    invalid = dict(command)
    invalid["media_path"] = "media/photo.png"
    invalid["media_sha256"] = "b" * 64
    try:
        relay._validate_command(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("photo and video were accepted together")


def test_encrypted_private_mp4_relay_creates_proposed_video_draft(monkeypatch, tmp_path):
    mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"
    digest = __import__("hashlib").sha256(mp4).hexdigest()
    calls = []
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "private.pem"
    private_path.write_bytes(
        key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    monkeypatch.setattr(relay, "PRIVATE_KEY_PATH", private_path)
    monkeypatch.setattr(relay, "BRIDGE_HOME", tmp_path)
    monkeypatch.setattr(relay, "STATE_PATH", tmp_path / "processed.json")
    monkeypatch.setattr(relay, "INFLIGHT_PATH", tmp_path / "inflight.json")
    monkeypatch.setattr(relay, "OUTBOX_PATH", tmp_path / "outbox.json")

    monkeypatch.setattr(relay, "_git", lambda *args, **kwargs: "")
    monkeypatch.setattr(relay, "_git_bytes", lambda *args, **kwargs: mp4)

    async def fake_call(tool_name, arguments):
        calls.append((tool_name, arguments))
        return {
            "approval_id": "approval-video-123",
            "state": "proposed",
            "has_video": True,
            "has_photo": False,
            "approved_by": None,
            "message_id": None,
            "schedule_id": None,
        }

    monkeypatch.setattr(relay, "_call_mcp_tool", fake_call)
    command = {
        "version": 1,
        "command_id": "1234567890abcdef",
        "action": "create_post_draft",
        "chat_id": "-1001234567890",
        "text": "synthetic encrypted MP4",
        "video_path": "media/smoke.mp4",
        "video_sha256": digest,
        "video_filename": "smoke.mp4",
    }
    aes_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ciphertext = AESGCM(aes_key).encrypt(nonce, json.dumps(command).encode(), None)
    wrapped = key.public_key().encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None
        ),
    )
    envelope = json.dumps(
        {
            "v": 1,
            "wrapped_key": base64.b64encode(wrapped).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }
    )
    status_records = []
    monkeypatch.setattr(relay, "_flush_status_outbox", lambda: None)
    monkeypatch.setattr(relay, "_list_queue_files", lambda: ["queue/1234567890abcdef.jafarcmd"])
    monkeypatch.setattr(relay, "_read_remote_file", lambda _path: envelope)
    monkeypatch.setattr(relay, "_queue_status", status_records.append)

    assert relay.run_once() == 1
    status = status_records[0]

    assert status["state"] == "completed"
    result = status["result"]
    assert result["approval"]["state"] == "proposed"
    assert result["approval"]["has_video"] is True
    assert result["approval"]["approved_by"] is None
    assert result["approval"]["message_id"] is None
    assert result["approval"]["schedule_id"] is None
    assert calls[0][0] == "telegram_create_post_draft"
    assert base64.b64decode(calls[0][1]["video_base64"]) == mp4
    assert calls[0][1]["filename"] == "smoke.mp4"
