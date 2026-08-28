from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol

from .domains import MatterType
from .legal_models import Deadline, Matter, MatterEvent
from .matter_repository import MatterRepository


class SupabaseClient(Protocol):
    """Small protocol so the repository stays independent of a specific SDK."""

    def table(self, name: str) -> Any: ...

    def rpc(self, function: str, params: dict[str, Any]) -> Any: ...


class SupabaseMatterRepository(MatterRepository):
    """Supabase adapter for durable matter state.

    Matter rows and deadline rows are hydrated together. This is important for the connected
    dashboard: a persistent repository must expose the same deadline state as ``MatterStore``
    instead of silently returning matters with empty deadlines.
    """

    def __init__(self, client: SupabaseClient, owner_user_id: str) -> None:
        if not owner_user_id.strip():
            raise ValueError("owner_user_id_required")
        self.client = client
        self.owner_user_id = owner_user_id.strip()

    def create(self, matter: Matter) -> Matter:
        payload = self._matter_payload(matter)
        payload["owner_user_id"] = self.owner_user_id
        self.client.table("matters").insert(payload).execute()
        if matter.deadlines:
            self._insert_deadlines(matter.id, matter.deadlines)
        return matter

    def get(self, matter_id: str) -> Matter | None:
        response = (
            self.client.table("matters")
            .select("*")
            .eq("id", matter_id)
            .eq("owner_user_id", self.owner_user_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            return None
        deadlines = self._deadlines_for_matter(matter_id)
        return self._matter(response.data, deadlines=deadlines)

    def list_matters(self) -> list[Matter]:
        response = (
            self.client.table("matters")
            .select("*")
            .eq("owner_user_id", self.owner_user_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return []

        matter_ids = {str(row["id"]) for row in rows}
        deadline_response = (
            self.client.table("deadlines")
            .select("*")
            .eq("owner_user_id", self.owner_user_id)
            .execute()
        )
        grouped: dict[str, list[Deadline]] = {matter_id: [] for matter_id in matter_ids}
        for row in deadline_response.data or []:
            matter_id = str(row.get("matter_id", ""))
            if matter_id in grouped:
                grouped[matter_id].append(self._deadline(row))

        return [
            self._matter(row, deadlines=grouped.get(str(row["id"]), []))
            for row in rows
        ]

    def add_deadlines(self, matter_id: str, deadlines: list[Deadline]) -> Matter | None:
        if not deadlines:
            return self.get(matter_id)
        matter = self.get(matter_id)
        if matter is None:
            return None

        existing = {self._deadline_key(item) for item in matter.deadlines}
        new_items = [item for item in deadlines if self._deadline_key(item) not in existing]
        if new_items:
            self._insert_deadlines(matter_id, new_items)
        return self.get(matter_id)

    def record_document_event(
        self,
        matter_id: str,
        title: str,
        event_date: datetime,
        description: str | None = None,
        source_document: str | None = None,
        document_fingerprint: str | None = None,
        deadlines: list[Deadline] | None = None,
    ) -> MatterEvent | None:
        params = {
            "p_matter_id": matter_id,
            "p_title": title,
            "p_event_date": event_date.isoformat(),
            "p_description": description,
            "p_source_document": source_document,
            "p_document_fingerprint": document_fingerprint,
            "p_deadlines": [self._deadline_payload(item) for item in deadlines or []],
        }
        response = self.client.rpc("record_document_event", params).execute()
        row = response.data
        if isinstance(row, list):
            row = row[0] if row else None
        return self._event(row) if row else None

    def add_event(
        self,
        matter_id: str,
        title: str,
        event_date: datetime,
        description: str | None = None,
        source_document: str | None = None,
        document_fingerprint: str | None = None,
    ) -> MatterEvent | None:
        return self.record_document_event(
            matter_id,
            title,
            event_date,
            description,
            source_document,
            document_fingerprint,
            [],
        )

    def event_by_fingerprint(
        self,
        matter_id: str,
        document_fingerprint: str,
    ) -> MatterEvent | None:
        response = (
            self.client.table("matter_events")
            .select("*")
            .eq("matter_id", matter_id)
            .eq("owner_user_id", self.owner_user_id)
            .eq("document_fingerprint", document_fingerprint)
            .maybe_single()
            .execute()
        )
        return self._event(response.data) if response.data else None

    def events(self, matter_id: str) -> list[MatterEvent]:
        response = (
            self.client.table("matter_events")
            .select("*")
            .eq("matter_id", matter_id)
            .eq("owner_user_id", self.owner_user_id)
            .order("event_date")
            .execute()
        )
        return [self._event(row) for row in response.data or []]

    def _deadlines_for_matter(self, matter_id: str) -> list[Deadline]:
        response = (
            self.client.table("deadlines")
            .select("*")
            .eq("matter_id", matter_id)
            .eq("owner_user_id", self.owner_user_id)
            .execute()
        )
        return [self._deadline(row) for row in response.data or []]

    def _insert_deadlines(self, matter_id: str, deadlines: list[Deadline]) -> None:
        rows = [
            {
                "matter_id": matter_id,
                "owner_user_id": self.owner_user_id,
                **self._deadline_payload(item),
            }
            for item in deadlines
        ]
        if rows:
            self.client.table("deadlines").insert(rows).execute()

    @staticmethod
    def _matter_payload(matter: Matter) -> dict[str, Any]:
        return {
            "id": matter.id,
            "title": matter.title,
            "matter_type": matter.matter_type.value,
            "client_name": matter.client_name,
            "opposing_party": matter.opposing_party,
            "court_or_authority": matter.court_or_authority,
            "case_number": matter.case_number,
            "status": matter.status,
            "created_at": matter.created_at.isoformat(),
            "updated_at": matter.updated_at.isoformat(),
        }

    @classmethod
    def _matter(
        cls,
        row: dict[str, Any],
        *,
        deadlines: list[Deadline] | None = None,
    ) -> Matter:
        return Matter(
            id=str(row["id"]),
            title=row["title"],
            matter_type=MatterType(row["matter_type"]),
            client_name=row.get("client_name"),
            opposing_party=row.get("opposing_party"),
            court_or_authority=row.get("court_or_authority"),
            case_number=row.get("case_number"),
            status=row.get("status", "active"),
            deadlines=list(deadlines or []),
            created_at=cls._datetime(row["created_at"]),
            updated_at=cls._datetime(row["updated_at"]),
        )

    @staticmethod
    def _deadline(row: dict[str, Any]) -> Deadline:
        raw_due_date = row.get("due_date")
        due_date: date | None
        if raw_due_date is None or raw_due_date == "":
            due_date = None
        elif isinstance(raw_due_date, datetime):
            due_date = raw_due_date.date()
        elif isinstance(raw_due_date, date):
            due_date = raw_due_date
        else:
            value = str(raw_due_date)
            try:
                due_date = date.fromisoformat(value[:10])
            except ValueError:
                due_date = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return Deadline(
            title=str(row["title"]),
            due_date=due_date,
            source_text=row.get("source_text"),
            confidence=float(row.get("confidence") or 0.0),
        )

    @staticmethod
    def _deadline_payload(item: Deadline) -> dict[str, Any]:
        return {
            "title": item.title,
            "due_date": item.due_date.isoformat() if item.due_date else None,
            "source_text": item.source_text,
            "confidence": item.confidence,
        }

    @staticmethod
    def _deadline_key(item: Deadline) -> tuple[str, date | None, str | None]:
        return (item.title, item.due_date, item.source_text)

    @staticmethod
    def _datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    @classmethod
    def _event(cls, row: dict[str, Any]) -> MatterEvent:
        return MatterEvent(
            id=str(row["id"]),
            matter_id=str(row["matter_id"]),
            title=row["title"],
            event_date=cls._datetime(row["event_date"]),
            description=row.get("description"),
            source_document=row.get("source_document"),
            document_fingerprint=row.get("document_fingerprint"),
            created_at=cls._datetime(row["created_at"]),
        )
