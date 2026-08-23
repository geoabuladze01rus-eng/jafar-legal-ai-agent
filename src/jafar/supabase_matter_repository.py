from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from .legal_models import Deadline, Matter, MatterEvent
from .matter_repository import MatterRepository


class SupabaseClient(Protocol):
    """Small protocol so the repository stays independent of a specific SDK."""

    def table(self, name: str) -> Any: ...

    def rpc(self, function: str, params: dict[str, Any]) -> Any: ...


class SupabaseMatterRepository(MatterRepository):
    """Supabase adapter; authentication/RLS remain owned by the caller/client."""

    def __init__(self, client: SupabaseClient, owner_user_id: str) -> None:
        self.client = client
        self.owner_user_id = owner_user_id

    def create(self, matter: Matter) -> Matter:
        payload = self._matter_payload(matter)
        payload["owner_user_id"] = self.owner_user_id
        self.client.table("matters").insert(payload).execute()
        return matter

    def get(self, matter_id: str) -> Matter | None:
        response = (self.client.table("matters").select("*").eq("id", matter_id)
                    .eq("owner_user_id", self.owner_user_id).maybe_single().execute())
        return self._matter(response.data) if response.data else None

    def list_matters(self) -> list[Matter]:
        response = self.client.table("matters").select("*").eq("owner_user_id", self.owner_user_id).execute()
        return [self._matter(row) for row in (response.data or [])]

    def add_deadlines(self, matter_id: str, deadlines: list[Deadline]) -> Matter | None:
        if not deadlines:
            return self.get(matter_id)
        matter = self.get(matter_id)
        if matter is None:
            return None
        rows = [{"matter_id": matter_id, "owner_user_id": self.owner_user_id,
                 "title": item.title, "due_date": item.due_date.isoformat() if item.due_date else None,
                 "source_text": item.source_text} for item in deadlines]
        self.client.table("deadlines").insert(rows).execute()
        return self.get(matter_id)

    def record_document_event(self, matter_id: str, title: str, event_date: datetime,
                              description: str | None, source_document: str | None,
                              document_fingerprint: str | None, deadlines: list[Deadline]) -> MatterEvent | None:
        params = {
            "p_matter_id": matter_id, "p_title": title, "p_event_date": event_date.isoformat(),
            "p_description": description, "p_source_document": source_document,
            "p_document_fingerprint": document_fingerprint,
            "p_deadlines": [{"title": d.title, "due_date": d.due_date.isoformat() if d.due_date else None,
                             "source_text": d.source_text} for d in deadlines],
        }
        response = self.client.rpc("record_document_event", params).execute()
        row = response.data
        if isinstance(row, list):
            row = row[0] if row else None
        return self._event(row) if row else None

    def add_event(self, matter_id: str, title: str, event_date: datetime,
                  description: str | None = None, source_document: str | None = None,
                  document_fingerprint: str | None = None) -> MatterEvent | None:
        return self.record_document_event(matter_id, title, event_date, description,
                                          source_document, document_fingerprint, [])

    def event_by_fingerprint(self, matter_id: str, document_fingerprint: str) -> MatterEvent | None:
        response = (self.client.table("matter_events").select("*").eq("matter_id", matter_id)
                    .eq("owner_user_id", self.owner_user_id).eq("document_fingerprint", document_fingerprint)
                    .maybe_single().execute())
        return self._event(response.data) if response.data else None

    def events(self, matter_id: str) -> list[MatterEvent]:
        response = (self.client.table("matter_events").select("*").eq("matter_id", matter_id)
                    .eq("owner_user_id", self.owner_user_id).order("event_date").execute())
        return [self._event(row) for row in (response.data or [])]

    @staticmethod
    def _matter_payload(matter: Matter) -> dict[str, Any]:
        return {"id": matter.id, "title": matter.title, "matter_type": matter.matter_type.value,
                "client_name": matter.client_name, "opposing_party": matter.opposing_party,
                "court_or_authority": matter.court_or_authority, "case_number": matter.case_number,
                "created_at": matter.created_at.isoformat(), "updated_at": matter.updated_at.isoformat()}

    @staticmethod
    def _matter(row: dict[str, Any]) -> Matter:
        from .domains import MatterType
        return Matter(id=row["id"], title=row["title"], matter_type=MatterType(row["matter_type"]),
                      client_name=row.get("client_name"), opposing_party=row.get("opposing_party"),
                      court_or_authority=row.get("court_or_authority"), case_number=row.get("case_number"),
                      status=row.get("status", "active"), created_at=datetime.fromisoformat(row["created_at"]),
                      updated_at=datetime.fromisoformat(row["updated_at"]))

    @staticmethod
    def _event(row: dict[str, Any]) -> MatterEvent:
        return MatterEvent(id=row["id"], matter_id=row["matter_id"], title=row["title"],
                           event_date=datetime.fromisoformat(row["event_date"]), description=row.get("description"),
                           source_document=row.get("source_document"), document_fingerprint=row.get("document_fingerprint"),
                           created_at=datetime.fromisoformat(row["created_at"]))
