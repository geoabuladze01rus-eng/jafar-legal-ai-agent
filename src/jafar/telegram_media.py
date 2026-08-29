"""Small, persistent editorial/media primitives for the Telegram channel.

This module deliberately does not send messages or instantiate an LLM.  It stores editorial
decisions and produces deterministic drafts; callers must pass generated content through the
existing APPROVE/live-send scheduler gates.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

CATEGORIES = (
    "real_legal_practice", "criminal_procedure", "investigative_mistakes",
    "supreme_court", "law_changes", "human_rights", "detention", "qa", "polls", "digest",
)
_REDACTIONS = (
    (r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[redacted email]"),
    (r"(?:\+7|8)[\s(\-]*\d{3}[\s)\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", "[redacted phone]"),
    (r"\b[А-ЯA-Z]\d{1,3}-\d{2,}/\d{4}\b", "[redacted case number]"),
    (r"\b(?:паспорт|снилс|инн)\s*[:№N]?\s*[\w-]+", "[redacted document]"),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def redact_case(text: str) -> tuple[str, list[str]]:
    findings: list[str] = []
    result = text
    for pattern, replacement in _REDACTIONS:
        result, count = re.subn(pattern, replacement, result, flags=re.IGNORECASE)
        if count:
            findings.append(replacement.strip("[]"))
    # Names and explicit confidentiality indicators are never retained verbatim.
    if re.search(r"(?:адвокатск\w* тайна|тайна следствия|конфиденциальн\w*)", result, re.IGNORECASE):
        findings.append("confidentiality_risk")
    return result.strip(), sorted(set(findings))


def generate_post(topic: str, category: str = "real_legal_practice", facts: str = "", *, short: bool = False) -> dict[str, Any]:
    if not topic.strip():
        raise ValueError("topic_required")
    if category not in CATEGORIES:
        raise ValueError("unknown_category")
    headline = topic.strip().rstrip(".!?")
    body = facts.strip() or "Короткий разбор темы с практическими выводами."
    if short:
        text = f"{headline}\n\n{body}\n\nЧто вы думаете?"
    else:
        text = (f"{headline}\n\nВводная: разберём вопрос простым языком.\n\nФакты:\n{body}\n\n"
                "Практический смысл: проверяйте документы и сроки, а спорные вопросы обсуждайте со специалистом.\n\n"
                "Какой опыт был у вас?\n\n#право #адвокат #следствие #суд #практика")
    return {"headline": headline, "body": text, "category": category, "mode": "APPROVE", "requires_approval": True}


class MediaStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.execute("CREATE TABLE IF NOT EXISTS telegram_content_plans (id TEXT PRIMARY KEY, week_start TEXT, items_json TEXT, created_at TEXT)")
            con.execute("CREATE TABLE IF NOT EXISTS telegram_news (id TEXT PRIMARY KEY, source_url TEXT, source_name TEXT, published_at TEXT, verified INTEGER, title TEXT, relevance REAL, created_at TEXT, dedupe_key TEXT UNIQUE)")
            con.execute("CREATE TABLE IF NOT EXISTS telegram_media_posts (id TEXT PRIMARY KEY, kind TEXT, payload_json TEXT, created_at TEXT)")
            columns = {row[1] for row in con.execute("PRAGMA table_info(telegram_news)")}
            if "dedupe_key" not in columns:
                con.execute("ALTER TABLE telegram_news ADD COLUMN dedupe_key TEXT")
                con.execute("CREATE UNIQUE INDEX IF NOT EXISTS telegram_news_dedupe ON telegram_news(dedupe_key)")

    def create_plan(self, week_start: str, topics: list[str], *, count: int = 7) -> dict[str, Any]:
        if not 7 <= count <= 10:
            raise ValueError("count_must_be_between_7_and_10")
        if not topics:
            raise ValueError("topics_required")
        items = [{"position": i + 1, "topic": topics[i % len(topics)], "category": CATEGORIES[i % len(CATEGORIES)], "state": "planned"} for i in range(count)]
        plan = {"id": str(uuid4()), "week_start": week_start, "items": items, "created_at": _now()}
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO telegram_content_plans VALUES (?,?,?,?)", (plan["id"], week_start, json.dumps(items, ensure_ascii=False), plan["created_at"]))
        return plan

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.path) as con:
            row = con.execute("SELECT id,week_start,items_json,created_at FROM telegram_content_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            raise KeyError(plan_id)
        return {"id": row[0], "week_start": row[1], "items": json.loads(row[2]), "created_at": row[3]}

    def update_plan(self, plan_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE telegram_content_plans SET items_json=? WHERE id=?", (json.dumps(items, ensure_ascii=False), plan_id))
        plan["items"] = items
        return plan

    def save(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        value = {"id": str(uuid4()), "kind": kind, **payload, "created_at": _now()}
        with sqlite3.connect(self.path) as con:
            con.execute("INSERT INTO telegram_media_posts VALUES (?,?,?,?)", (value["id"], kind, json.dumps(payload, ensure_ascii=False), value["created_at"]))
        return value

    def ingest_news(self, **payload: Any) -> dict[str, Any]:
        if not payload.get("source_url") or not payload.get("source_name"):
            raise ValueError("source_url_and_source_name_required")
        parsed = urlparse(str(payload["source_url"]))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url_must_be_http_or_https")
        title = str(payload.get("title", "")).strip()
        verified = bool(payload.get("verified", False))
        relevance = min(1.0, max(0.0, float(payload.get("relevance", 0.0))))
        dedupe_key = sha256(f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}|{title.casefold()}".encode()).hexdigest()
        item = {"id": str(uuid4()), "title": title, "source_url": payload["source_url"], "source_name": payload["source_name"], "published_at": payload.get("published_at"), "verified": verified, "relevance": relevance, "dedupe_key": dedupe_key}
        with sqlite3.connect(self.path) as con:
            existing = con.execute("SELECT id FROM telegram_news WHERE dedupe_key=?", (dedupe_key,)).fetchone()
            if existing:
                item["id"] = existing[0]
                item["duplicate"] = True
                return item
            con.execute("INSERT INTO telegram_news VALUES (?,?,?,?,?,?,?,?,?)", (item["id"], item["source_url"], item["source_name"], item["published_at"], int(verified), title, relevance, _now(), dedupe_key))
        return item

    def save_metrics(self, *, message_id: int, views: int | None = None, reactions: int | None = None, comments: int | None = None) -> dict[str, Any]:
        if all(value is None for value in (views, reactions, comments)) or any(value is not None and value < 0 for value in (views, reactions, comments)):
            raise ValueError("at_least_one_nonnegative_metric_required")
        return self.save("metrics", {"message_id": message_id, "views": views, "reactions": reactions, "comments": comments})
