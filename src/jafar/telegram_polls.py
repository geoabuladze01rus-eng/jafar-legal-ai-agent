from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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
    explanation: str | None = None,
    open_period: int | None = None,
    close_date: int | None = None,
) -> dict[str, Any]:
    question = question.strip()
    options = [option.strip() for option in options]
    if not 1 <= len(question) <= 300:
        raise ValueError("question must contain 1 to 300 characters")
    if not 2 <= len(options) <= 10 or any(not 1 <= len(option) <= 100 for option in options):
        raise ValueError("options must contain 2 to 10 non-empty values of at most 100 characters")
    if poll_type not in {"regular", "quiz"}:
        raise ValueError("poll_type must be regular or quiz")
    if poll_type == "regular" and (correct_option_id is not None or explanation):
        raise ValueError("correct_option_id and explanation are only valid for quiz polls")
    if poll_type == "quiz":
        if correct_option_id is None or not 0 <= correct_option_id < len(options):
            raise ValueError("quiz polls require a valid correct_option_id")
        if allows_multiple_answers:
            raise ValueError("quiz polls cannot allow multiple answers")
        if explanation and len(explanation) > 200:
            raise ValueError("explanation must not exceed 200 characters")
    if open_period is not None and close_date is not None:
        raise ValueError("provide only one of open_period and close_date")
    if open_period is not None and not 5 <= open_period <= 600:
        raise ValueError("open_period must be between 5 and 600 seconds")
    if close_date is not None:
        seconds = close_date - int(datetime.now(UTC).timestamp())
        if not 5 <= seconds <= 600:
            raise ValueError("close_date must be 5 to 600 seconds in the future")
    return {
        "question": question,
        "options": options,
        "is_anonymous": is_anonymous,
        "allows_multiple_answers": allows_multiple_answers,
        "type": poll_type,
        "correct_option_id": correct_option_id,
        "explanation": explanation,
        "open_period": open_period,
        "close_date": close_date,
    }


class TelegramPollStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_polls (
                poll_id TEXT PRIMARY KEY, chat_id TEXT, message_id INTEGER, question TEXT NOT NULL,
                options_json TEXT NOT NULL, poll_json TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_poll_answers (
                poll_id TEXT NOT NULL, user_id TEXT NOT NULL, option_ids_json TEXT NOT NULL,
                updated_at TEXT NOT NULL, PRIMARY KEY(poll_id, user_id)
            )""")

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def record_sent(self, *, poll: dict[str, Any], chat_id: str, message_id: int | None) -> None:
        poll_id = str(poll["id"])
        with self._connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO telegram_polls VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    poll_id,
                    chat_id,
                    message_id,
                    poll.get("question", ""),
                    json.dumps(poll.get("options", [])),
                    json.dumps(poll),
                    _now(),
                ),
            )

    def ingest_update(self, update: dict[str, Any]) -> bool:
        poll = update.get("poll")
        if isinstance(poll, dict) and poll.get("id"):
            self._upsert_poll(poll)
            return True
        answer = update.get("poll_answer")
        if (
            isinstance(answer, dict)
            and answer.get("poll_id")
            and answer.get("user", {}).get("id") is not None
        ):
            with self._connect() as con:
                con.execute(
                    "INSERT OR REPLACE INTO telegram_poll_answers VALUES (?, ?, ?, ?)",
                    (
                        str(answer["poll_id"]),
                        str(answer["user"]["id"]),
                        json.dumps(answer.get("option_ids", [])),
                        _now(),
                    ),
                )
            return True
        return False

    def _upsert_poll(self, poll: dict[str, Any]) -> None:
        poll_id = str(poll["id"])
        with self._connect() as con:
            old = con.execute(
                "SELECT chat_id, message_id FROM telegram_polls WHERE poll_id=?", (poll_id,)
            ).fetchone()
            con.execute(
                "INSERT OR REPLACE INTO telegram_polls VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    poll_id,
                    old["chat_id"] if old else None,
                    old["message_id"] if old else None,
                    poll.get("question", ""),
                    json.dumps(poll.get("options", [])),
                    json.dumps(poll),
                    _now(),
                ),
            )

    def results(self, poll_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM telegram_polls WHERE poll_id=?", (poll_id,)).fetchone()
            answers = con.execute(
                "SELECT user_id, option_ids_json FROM telegram_poll_answers WHERE poll_id=?",
                (poll_id,),
            ).fetchall()
        if row is None:
            raise KeyError(poll_id)
        poll = json.loads(row["poll_json"])
        return {
            "poll_id": poll_id,
            "chat_id": row["chat_id"],
            "message_id": row["message_id"],
            "poll": poll,
            "answers": [
                {"user_id": answer["user_id"], "option_ids": json.loads(answer["option_ids_json"])}
                for answer in answers
            ],
            "answer_count": len(answers),
        }
