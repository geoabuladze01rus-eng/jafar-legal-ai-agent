from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_POLL_CLOSE_SECONDS = 2_628_000
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def validate_poll(
    *,
    question: str,
    options: list[str],
    is_anonymous: bool = True,
    allows_multiple_answers: bool = False,
    poll_type: str = "regular",
    correct_option_id: int | None = None,
    correct_option_ids: list[int] | None = None,
    explanation: str | None = None,
    open_period: int | None = None,
    close_date: int | None = None,
) -> dict[str, Any]:
    question = question.strip()
    options = [option.strip() for option in options]
    if not 1 <= len(question) <= 300:
        raise ValueError("question must contain 1 to 300 characters")
    if not 1 <= len(options) <= 12 or any(not 1 <= len(option) <= 100 for option in options):
        raise ValueError("options must contain 1 to 12 non-empty values of at most 100 characters")
    if poll_type not in {"regular", "quiz"}:
        raise ValueError("poll_type must be regular or quiz")
    if correct_option_id is not None and correct_option_ids is not None:
        raise ValueError("provide only one of correct_option_id and correct_option_ids")

    normalized_correct: list[int] | None
    if correct_option_ids is not None:
        if any(isinstance(value, bool) or not isinstance(value, int) for value in correct_option_ids):
            raise ValueError("correct_option_ids must contain integer option indexes")
        normalized_correct = sorted(set(correct_option_ids))
    elif correct_option_id is not None:
        if isinstance(correct_option_id, bool):
            raise ValueError("correct_option_id must be an integer option index")
        normalized_correct = [correct_option_id]
    else:
        normalized_correct = None

    if poll_type == "regular":
        if normalized_correct or explanation:
            raise ValueError("correct options and explanation are only valid for quiz polls")
        normalized_correct = None
    else:
        if not normalized_correct:
            raise ValueError("quiz polls require at least one correct option")
        if any(value < 0 or value >= len(options) for value in normalized_correct):
            raise ValueError("quiz polls require valid correct option indexes")
        if len(normalized_correct) > 1 and not allows_multiple_answers:
            raise ValueError("multiple correct quiz answers require allows_multiple_answers=true")
        if explanation is not None:
            explanation = explanation.strip()
            if len(explanation) > 200 or explanation.count("\n") > 2:
                raise ValueError("explanation must not exceed 200 characters or 2 line feeds")

    if open_period is not None and close_date is not None:
        raise ValueError("provide only one of open_period and close_date")
    if open_period is not None and not 5 <= open_period <= MAX_POLL_CLOSE_SECONDS:
        raise ValueError(f"open_period must be between 5 and {MAX_POLL_CLOSE_SECONDS} seconds")
    if close_date is not None:
        seconds = close_date - int(datetime.now(UTC).timestamp())
        if not 5 <= seconds <= MAX_POLL_CLOSE_SECONDS:
            raise ValueError(f"close_date must be 5 to {MAX_POLL_CLOSE_SECONDS} seconds in the future")
    return {
        "question": question,
        "options": options,
        "is_anonymous": bool(is_anonymous),
        "allows_multiple_answers": bool(allows_multiple_answers),
        "type": poll_type,
        "correct_option_ids": normalized_correct,
        "explanation": explanation,
        "open_period": open_period,
        "close_date": close_date,
    }


class TelegramPollStore:
    def __init__(self, path: str | Path, *, identity_secret: str | None = None) -> None:
        db_path = Path(path).expanduser()
        if db_path.is_symlink():
            raise RuntimeError("telegram_poll_db_must_not_be_symlink")
        self.path = str(db_path)
        self._identity_secret = (identity_secret or "").encode("utf-8") or None
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_polls (
                poll_id TEXT PRIMARY KEY, chat_id TEXT, message_id INTEGER, question TEXT NOT NULL,
                options_json TEXT NOT NULL, poll_json TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_poll_answers (
                poll_id TEXT NOT NULL, user_id TEXT NOT NULL, option_ids_json TEXT NOT NULL,
                updated_at TEXT NOT NULL, PRIMARY KEY(poll_id, user_id)
            )""")
            if self._identity_secret is not None:
                self._migrate_legacy_raw_voter_ids(con)
        self._harden_permissions()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=5.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _harden_permissions(self) -> None:
        if os.name != "posix":
            return
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{self.path}{suffix}")
            if candidate.is_symlink():
                raise RuntimeError("telegram_poll_sidecar_must_not_be_symlink")
            if candidate.exists():
                candidate.chmod(0o600)

    def _pseudonymize(self, raw_identity: str) -> str | None:
        if self._identity_secret is None:
            return None
        return hmac.new(self._identity_secret, raw_identity.encode("utf-8"), hashlib.sha256).hexdigest()

    def _migrate_legacy_raw_voter_ids(self, con: sqlite3.Connection) -> None:
        rows = con.execute(
            "SELECT poll_id, user_id, option_ids_json, updated_at FROM telegram_poll_answers"
        ).fetchall()
        for row in rows:
            old_key = str(row["user_id"])
            if _HEX64.fullmatch(old_key):
                continue
            namespace = old_key if old_key.startswith(("user:", "chat:")) else f"user:{old_key}"
            new_key = self._pseudonymize(namespace)
            if new_key is None:
                continue
            con.execute(
                "INSERT OR REPLACE INTO telegram_poll_answers VALUES (?, ?, ?, ?)",
                (row["poll_id"], new_key, row["option_ids_json"], row["updated_at"]),
            )
            con.execute(
                "DELETE FROM telegram_poll_answers WHERE poll_id=? AND user_id=?",
                (row["poll_id"], old_key),
            )

    def _known_poll(self, poll_id: str) -> bool:
        with self._connect() as con:
            return con.execute("SELECT 1 FROM telegram_polls WHERE poll_id=?", (poll_id,)).fetchone() is not None

    def record_sent(self, *, poll: dict[str, Any], chat_id: str, message_id: int | None) -> None:
        poll_id = str(poll["id"]).strip()
        if not poll_id:
            raise ValueError("telegram_poll_id_required")
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO telegram_polls VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    poll_id,
                    chat_id,
                    message_id,
                    poll.get("question", ""),
                    json.dumps(poll.get("options", []), ensure_ascii=False),
                    json.dumps(poll, ensure_ascii=False),
                    _now(),
                ),
            )
        self._harden_permissions()

    def ingest_update(self, update: dict[str, Any]) -> bool:
        poll = update.get("poll")
        if isinstance(poll, dict) and poll.get("id"):
            poll_id = str(poll["id"]).strip()
            if not poll_id or not self._known_poll(poll_id):
                return False
            self._upsert_poll(poll)
            return True

        answer = update.get("poll_answer")
        if not isinstance(answer, dict) or not answer.get("poll_id"):
            return False
        poll_id = str(answer["poll_id"]).strip()
        if not poll_id or not self._known_poll(poll_id):
            return False

        voter_key = self._voter_key(answer)
        if voter_key is None:
            return True
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO telegram_poll_answers VALUES (?, ?, ?, ?)",
                (poll_id, voter_key, json.dumps(answer.get("option_ids", [])), _now()),
            )
        self._harden_permissions()
        return True

    def _voter_key(self, answer: dict[str, Any]) -> str | None:
        user = answer.get("user")
        if isinstance(user, dict) and user.get("id") is not None:
            return self._pseudonymize(f"user:{user['id']}")
        voter_chat = answer.get("voter_chat")
        if isinstance(voter_chat, dict) and voter_chat.get("id") is not None:
            return self._pseudonymize(f"chat:{voter_chat['id']}")
        return None

    def _upsert_poll(self, poll: dict[str, Any]) -> None:
        poll_id = str(poll["id"])
        with self._connect() as con:
            old = con.execute("SELECT chat_id, message_id FROM telegram_polls WHERE poll_id=?", (poll_id,)).fetchone()
            if old is None:
                raise RuntimeError("telegram_poll_update_for_unknown_poll")
            con.execute(
                "INSERT OR REPLACE INTO telegram_polls VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    poll_id,
                    old["chat_id"],
                    old["message_id"],
                    poll.get("question", ""),
                    json.dumps(poll.get("options", []), ensure_ascii=False),
                    json.dumps(poll, ensure_ascii=False),
                    _now(),
                ),
            )
        self._harden_permissions()

    def results(self, poll_id: str) -> dict[str, Any]:
        key = poll_id.strip()
        if not key:
            raise ValueError("poll_id must not be empty")
        with self._connect() as con:
            row = con.execute("SELECT * FROM telegram_polls WHERE poll_id=?", (key,)).fetchone()
            answers = con.execute(
                "SELECT user_id, option_ids_json FROM telegram_poll_answers WHERE poll_id=?", (key,)
            ).fetchall()
        if row is None:
            raise KeyError(key)
        poll = json.loads(row["poll_json"])
        if not isinstance(poll, dict):
            raise RuntimeError("telegram_poll_payload_invalid")
        normalized_answers: list[dict[str, Any]] = []
        for answer in answers:
            option_ids = json.loads(answer["option_ids_json"])
            if not isinstance(option_ids, list) or any(isinstance(value, bool) or not isinstance(value, int) for value in option_ids):
                raise RuntimeError("telegram_poll_answer_payload_invalid")
            voter_key = str(answer["user_id"])
            if not _HEX64.fullmatch(voter_key):
                raise RuntimeError("telegram_poll_voter_key_not_pseudonymous")
            normalized_answers.append({"voter_key": voter_key, "option_ids": option_ids})
        return {
            "poll_id": key,
            "chat_id": row["chat_id"],
            "message_id": row["message_id"],
            "poll": poll,
            "answers": normalized_answers,
            "answer_count": len(normalized_answers),
        }
