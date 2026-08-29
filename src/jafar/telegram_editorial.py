from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

EditorialMode = Literal["DRAFT", "APPROVE", "AUTO"]
Severity = Literal["low", "medium", "high"]
DEFAULT_RUBRICS = (
    "следственная практика",
    "ошибки обвинения/следствия",
    "работа адвоката",
    "разбор судебной практики",
    "истории из практики",
    "профессиональный взгляд/наблюдение",
    "интерактивный опрос",
    "недельный дайджест",
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def safety_check(text: str) -> dict[str, Any]:
    checks = (
        ("high", "email", r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "email address"),
        (
            "high",
            "phone",
            r"(?:\+7|8)[\s(\-]*\d{3}[\s)\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}",
            "phone number",
        ),
        ("high", "case_number", r"\b[А-ЯA-Z]\d{1,3}-\d{2,}/\d{4}\b", "case/document number"),
        ("high", "address", r"\b(?:ул\.|улица|проспект|д\.)\s*[^,.\n]{3,}", "address"),
        (
            "high",
            "investigation_secrecy",
            r"\b(?:тайна следствия|неразглашени[ея]|досудебн\w* материал)",
            "pretrial/investigation secrecy risk",
        ),
        (
            "high",
            "privilege",
            r"\b(?:адвокатск\w* тайна|конфиденциальн\w* клиент|доверител[ья])",
            "privileged/confidential information",
        ),
        (
            "high",
            "identifying_person",
            r"\b(?:паспорт|снилс|инн|персональн\w* данн\w*)",
            "personal data indicator",
        ),
        (
            "medium",
            "accusation",
            r"\b(?:взяточник|преступник|вор|мошенник)\b",
            "unverified accusation may be stated as fact",
        ),
    )
    findings = [
        {"severity": severity, "kind": kind, "reason": reason}
        for severity, kind, pattern, reason in checks
        if re.search(pattern, text, re.IGNORECASE)
    ]
    severity: Severity = (
        "high"
        if any(x["severity"] == "high" for x in findings)
        else "medium"
        if findings
        else "low"
    )
    return {
        "severity": severity,
        "findings": findings,
        "disclaimer": "This is a publication safety gate, not definitive legal clearance.",
    }


def redact_transcript(text: str) -> str:
    redacted = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[redacted email]", text)
    redacted = re.sub(
        r"(?:\+7|8)[\s(\-]*\d{3}[\s)\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", "[redacted phone]", redacted
    )
    redacted = re.sub(r"\b[А-ЯA-Z]\d{1,3}-\d{2,}/\d{4}\b", "[redacted case number]", redacted)
    return re.sub(r"\b(?:ээ+|ну|как бы|в общем)\b\s*", "", redacted, flags=re.IGNORECASE).strip()


@dataclass(frozen=True)
class EditorialItem:
    id: str
    week_start: str
    position: int
    rubric: str
    topic: str
    scheduled_for: str | None
    series_id: str | None
    state: str


class EditorialStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_editorial_items (
                id TEXT PRIMARY KEY, week_start TEXT NOT NULL, position INTEGER NOT NULL, rubric TEXT NOT NULL, topic TEXT NOT NULL, scheduled_for TEXT, series_id TEXT, state TEXT NOT NULL, created_at TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_editorial_drafts (
                id TEXT PRIMARY KEY, item_id TEXT, headline TEXT NOT NULL, body TEXT NOT NULL, image_url TEXT, photo_base64 TEXT, image_prompt TEXT, safety_json TEXT NOT NULL, mode TEXT NOT NULL, state TEXT NOT NULL, evergreen INTEGER NOT NULL DEFAULT 0, scheduled_id TEXT, message_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def create_plan(
        self,
        *,
        week_start: date,
        topics: list[str],
        rubrics: list[str],
        windows: list[str],
        series_length: int | None = None,
    ) -> list[EditorialItem]:
        if not topics:
            topics = ["профессиональное наблюдение"]
        if not windows:
            windows = ["09:00"]
        created: list[EditorialItem] = []
        prior: str | None = self.list_items()[-1].rubric if self.list_items() else None
        series_id = str(uuid4()) if series_length and series_length > 1 else None
        count = series_length or max(len(topics), 7)
        for position in range(count):
            candidates = [r for r in rubrics if r != prior] or rubrics
            rubric = candidates[position % len(candidates)]
            prior = rubric
            window = windows[position % len(windows)]
            try:
                publish_time = time.fromisoformat(window)
            except ValueError as exc:
                raise ValueError("publishing_windows must contain HH:MM values") from exc
            when = datetime.combine(
                week_start + timedelta(days=position % 7), publish_time, tzinfo=UTC
            )
            item = EditorialItem(
                str(uuid4()),
                week_start.isoformat(),
                position + 1,
                rubric,
                topics[position % len(topics)],
                when.isoformat(),
                series_id,
                "planned",
            )
            with self._connect() as con:
                con.execute(
                    "INSERT INTO telegram_editorial_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (*item.__dict__.values(), utc_now().isoformat()),
                )
            created.append(item)
        return created

    def list_items(self, week_start: str | None = None) -> list[EditorialItem]:
        sql, args = "SELECT * FROM telegram_editorial_items", ()
        if week_start:
            sql += " WHERE week_start=?"
            args = (week_start,)
        sql += " ORDER BY week_start, position"
        with self._connect() as con:
            rows = con.execute(sql, args).fetchall()
        return [
            EditorialItem(
                *(
                    row[key]
                    for key in (
                        "id",
                        "week_start",
                        "position",
                        "rubric",
                        "topic",
                        "scheduled_for",
                        "series_id",
                        "state",
                    )
                )
            )
            for row in rows
        ]

    def get_item(self, item_id: str) -> EditorialItem:
        return next(item for item in self.list_items() if item.id == item_id)

    def update_item(
        self,
        item_id: str,
        *,
        topic: str | None = None,
        scheduled_for: str | None = None,
        state: str | None = None,
    ) -> EditorialItem:
        sets, values = [], []
        for key, value in (("topic", topic), ("scheduled_for", scheduled_for), ("state", state)):
            if value is not None:
                sets.append(f"{key}=?")
                values.append(value)
        if not sets:
            return self.get_item(item_id)
        with self._connect() as con:
            con.execute(
                f"UPDATE telegram_editorial_items SET {', '.join(sets)} WHERE id=?",
                (*values, item_id),
            )
        return self.get_item(item_id)

    def create_draft(
        self,
        *,
        item_id: str | None,
        headline: str,
        body: str,
        mode: EditorialMode,
        image_url: str | None = None,
        photo_base64: str | None = None,
        image_prompt: str | None = None,
    ) -> dict[str, Any]:
        safety, now, draft_id = safety_check(body), utc_now().isoformat(), str(uuid4())
        state = (
            "draft"
            if mode == "DRAFT"
            else "approval_required"
            if mode == "APPROVE" or safety["severity"] == "high"
            else "approved"
        )
        with self._connect() as con:
            con.execute(
                "INSERT INTO telegram_editorial_drafts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, ?, ?)",
                (
                    draft_id,
                    item_id,
                    headline,
                    body,
                    image_url,
                    photo_base64,
                    image_prompt,
                    json.dumps(safety),
                    mode,
                    state,
                    now,
                    now,
                ),
            )
        return self.get_draft(draft_id)

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM telegram_editorial_drafts WHERE id=?", (draft_id,)
            ).fetchone()
        if row is None:
            raise KeyError(draft_id)
        result = dict(row)
        result["safety"] = json.loads(result.pop("safety_json"))
        result["evergreen"] = bool(result["evergreen"])
        return result

    def set_draft_state(self, draft_id: str, state: str) -> dict[str, Any]:
        with self._connect() as con:
            con.execute(
                "UPDATE telegram_editorial_drafts SET state=?, updated_at=? WHERE id=?",
                (state, utc_now().isoformat(), draft_id),
            )
        return self.get_draft(draft_id)

    def link_schedule(self, draft_id: str, schedule_id: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE telegram_editorial_drafts SET scheduled_id=?, state='scheduled', updated_at=? WHERE id=?",
                (schedule_id, utc_now().isoformat(), draft_id),
            )

    def link_delivery(self, draft_id: str, message_id: int | None) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE telegram_editorial_drafts SET message_id=?, state='published', updated_at=? WHERE id=?",
                (message_id, utc_now().isoformat(), draft_id),
            )

    def mark_evergreen(self, draft_id: str) -> dict[str, Any]:
        with self._connect() as con:
            con.execute("UPDATE telegram_editorial_drafts SET evergreen=1 WHERE id=?", (draft_id,))
        return self.get_draft(draft_id)

    def evergreen(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, headline, body, message_id, updated_at FROM telegram_editorial_drafts WHERE evergreen=1 ORDER BY updated_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def performance(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT d.*, i.rubric, i.topic FROM telegram_editorial_drafts d LEFT JOIN telegram_editorial_items i ON i.id=d.item_id WHERE d.message_id IS NOT NULL"
            ).fetchall()
        return [
            {
                "draft_id": row["id"],
                "message_id": row["message_id"],
                "rubric": row["rubric"],
                "topic": row["topic"],
                "published_at": row["updated_at"],
                "views": None,
                "reactions": None,
                "note": "Telegram views/reactions are unavailable until received from a supported runtime update.",
            }
            for row in rows
        ]
