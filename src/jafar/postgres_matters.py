from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from .legal_models import Deadline, Matter, MatterEvent


class PostgresMatterStore:
    """Persistent MatterStore backed by the project's Supabase Postgres database."""

    def __init__(self, database_url: str, owner_user_id: str | None = None) -> None:
        self.database_url = database_url
        self.owner_user_id = owner_user_id

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5)

    def create(self, matter: Matter) -> Matter:
        metadata = {
            "opposing_party": matter.opposing_party,
            "court_or_authority": matter.court_or_authority,
        }
        with self._connect() as connection:
            client_id = None
            if matter.client_name:
                client = connection.execute(
                    "insert into public.clients (name) values (%s) returning id",
                    (matter.client_name,),
                ).fetchone()
                client_id = client["id"] if client else None

            connection.execute(
                """
                insert into public.matters
                    (id, client_id, title, matter_type, status, case_number,
                     owner_user_id, metadata, created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    matter.id,
                    client_id,
                    matter.title,
                    matter.matter_type.value,
                    matter.status,
                    matter.case_number,
                    self.owner_user_id,
                    json.dumps(metadata, ensure_ascii=False),
                    matter.created_at,
                    matter.updated_at,
                ),
            )
        return self.get(matter.id) or matter

    def get(self, matter_id: str) -> Matter | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select m.id, m.title, m.matter_type, m.status, m.case_number,
                       m.metadata, c.name as client_name, m.created_at, m.updated_at
                from public.matters m
                left join public.clients c on c.id = m.client_id
                where m.id = %s
                """,
                (matter_id,),
            ).fetchone()
            if row is None:
                return None

            deadline_rows = connection.execute(
                """
                select title, due_at, basis, confidence
                from public.deadlines
                where matter_id = %s
                order by due_at nulls last, created_at desc
                """,
                (matter_id,),
            ).fetchall()

        metadata = row.get("metadata") or {}
        deadlines = [
            Deadline(
                title=item["title"],
                due_date=item["due_at"].date() if item["due_at"] else None,
                source_text=item.get("basis"),
                confidence=float(item["confidence"] or 0.0),
            )
            for item in deadline_rows
        ]
        return Matter(
            id=str(row["id"]),
            title=row["title"],
            matter_type=row["matter_type"],
            client_name=row.get("client_name"),
            opposing_party=metadata.get("opposing_party"),
            court_or_authority=metadata.get("court_or_authority"),
            case_number=row.get("case_number"),
            status=row.get("status") or "active",
            deadlines=deadlines,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def add_deadlines(self, matter_id: str, deadlines: list[Deadline]) -> Matter | None:
        if self.get(matter_id) is None:
            return None
        with self._connect() as connection:
            for deadline in deadlines:
                connection.execute(
                    """
                    insert into public.deadlines
                        (matter_id, title, due_at, status, confidence, requires_approval, basis)
                    values (%s, %s, %s, 'open', %s, true, %s)
                    """,
                    (
                        matter_id,
                        deadline.title,
                        deadline.due_date,
                        deadline.confidence,
                        deadline.source_text,
                    ),
                )
            connection.execute(
                "update public.matters set updated_at = %s where id = %s",
                (datetime.now(timezone.utc), matter_id),
            )
        return self.get(matter_id)

    def add_event(
        self,
        matter_id: str,
        title: str,
        event_date: datetime,
        description: str | None = None,
        source_document: str | None = None,
    ) -> MatterEvent | None:
        if self.get(matter_id) is None:
            return None
        event_id = uuid4()
        with self._connect() as connection:
            connection.execute(
                """
                insert into public.matter_events
                    (id, matter_id, owner_user_id, title, event_date, description, source_document)
                values (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_id,
                    matter_id,
                    self.owner_user_id,
                    title,
                    event_date,
                    description,
                    source_document,
                ),
            )
        return MatterEvent(
            id=str(event_id),
            matter_id=matter_id,
            title=title,
            event_date=event_date,
            description=description,
            source_document=source_document,
            created_at=datetime.now(timezone.utc),
        )

    def events(self, matter_id: str) -> list[MatterEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select id, matter_id, title, event_date, description, source_document, created_at
                from public.matter_events
                where matter_id = %s
                order by event_date desc, created_at desc
                """,
                (matter_id,),
            ).fetchall()
        return [
            MatterEvent(
                id=str(row["id"]),
                matter_id=str(row["matter_id"]),
                title=row["title"],
                event_date=row["event_date"],
                description=row.get("description"),
                source_document=row.get("source_document"),
                created_at=row["created_at"],
            )
            for row in rows
        ]
