from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

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

    plaintext = json.dumps(
        payload
    ).encode()

    aes_key = AESGCM.generate_key(
        bit_length=256
    )

    nonce = os.urandom(12)

    ciphertext = AESGCM(
        aes_key
    ).encrypt(
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

    assert (
        relay.decrypt_envelope(
            envelope
        )
        == payload
    )


def test_reject_unknown_action():
    command = {
        "version": 1,
        "command_id":
            "1234567890abcdef",
        "action":
            "publish_immediately",
    }

    try:
        relay._validate_command(
            command
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "unsafe action accepted"
        )
