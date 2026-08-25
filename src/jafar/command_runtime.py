from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .command_bus import JafarCommandBus
from .lawyer_context import LawyerContext
from .matters import MatterStore
from .tool_router import JafarToolRouter


@dataclass(frozen=True, slots=True)
class CommandRuntimeResult:
    intent: str
    message: str
    request_id: str
    approval_required: bool
    data: dict | None = None


class JafarCommandRuntime:
    """Single command facade shared by HTTP, voice and future chat clients."""

    def __init__(
        self,
        matter_store: MatterStore,
        context: LawyerContext | None = None,
    ) -> None:
        self.matter_store = matter_store
        self.context = context or LawyerContext()
        self.bus = JafarCommandBus()
        self.router = JafarToolRouter(self.bus)
        self._register_commands()

    def _register_commands(self) -> None:
        self.bus.register("health", lambda _: {"message": "Джафар на связи."})
        self.bus.register("list_matters", self._list_matters)
        self.bus.register("attention_summary", self._attention_summary)
        self.bus.register("matter_update", self._matter_update)
        self.bus.register("latest_legal_email", self._latest_legal_email)
        self.bus.register("prepare_reply", self._prepare_reply)

        self.router.register(
            "health",
            "health",
            "Проверка связи с Джафаром",
            requires_approval=False,
        )
        self.router.register(
            "list_matters",
            "list_matters",
            "Показать открытые дела",
            requires_approval=False,
        )
        self.router.register(
            "attention_summary",
            "attention_summary",
            "Показать, что требует внимания",
            requires_approval=False,
        )
        self.router.register(
            "matter_update",
            "matter_update",
            "Показать последние изменения по делу",
            requires_approval=False,
        )
        self.router.register(
            "latest_legal_email",
            "latest_legal_email",
            "Разобрать последнее юридическое письмо",
            requires_approval=False,
        )
        self.router.register(
            "prepare_reply",
            "prepare_reply",
            "Показать подготовленный проект ответа для проверки",
            requires_approval=False,
        )

    def execute(
        self,
        intent: str,
        *,
        args: dict | None = None,
        request_id: str | None = None,
        approved: bool = False,
    ) -> CommandRuntimeResult:
        request_id = request_id or str(uuid4())
        result = self.router.route(intent, args or {}, request_id, approved=approved)
        if result.status == "approval_required":
            return CommandRuntimeResult(
                intent=intent,
                message=result.message,
                request_id=request_id,
                approval_required=True,
            )
        if result.status != "completed":
            return CommandRuntimeResult(
                intent=intent,
                message=result.message,
                request_id=request_id,
                approval_required=False,
                data=result.data,
            )

        data = result.data or {}
        return CommandRuntimeResult(
            intent=intent,
            message=str(data.get("message", result.message)),
            request_id=request_id,
            approval_required=False,
            data=data,
        )

    def _list_matters(self, _: dict) -> dict:
        matters = self.matter_store.list_matters()
        if not matters:
            return {
                "message": "Сейчас открытых дел в хранилище нет.",
                "count": 0,
                "matters": [],
            }
        return {
            "message": f"У вас {len(matters)} дел.",
            "count": len(matters),
            "matters": [
                {"id": matter.id, "title": matter.title}
                for matter in matters
            ],
        }

    def _attention_summary(self, _: dict) -> dict:
        matters = [matter for matter in self.matter_store.list_matters() if matter.status == "active"]
        deadlines = []
        for matter in matters:
            for deadline in matter.deadlines:
                deadlines.append(
                    {
                        "matter_id": matter.id,
                        "matter_title": matter.title,
                        "title": deadline.title,
                        "due_date": deadline.due_date.isoformat() if deadline.due_date else None,
                        "confidence": deadline.confidence,
                    }
                )
        deadlines.sort(key=lambda item: (item["due_date"] is None, item["due_date"] or "9999-12-31"))
        latest_email = self.context.latest_legal_email
        attention_count = len(deadlines) + (1 if latest_email is not None else 0)
        if attention_count == 0:
            message = "Сейчас в загруженном контексте нет новых сроков или юридических писем, требующих внимания."
        else:
            message = (
                f"Требуют внимания: {len(deadlines)} сроков"
                + (" и последнее юридическое письмо." if latest_email is not None else ".")
            )
        return {
            "message": message,
            "attention_count": attention_count,
            "deadlines": deadlines,
            "latest_legal_email": self._email_snapshot_data(latest_email),
        }

    def _matter_update(self, args: dict) -> dict:
        query = str(args.get("query") or "").strip().lower()
        matters = self.matter_store.list_matters()
        if query:
            matches = [
                matter
                for matter in matters
                if any(
                    query in str(value or "").lower()
                    for value in (matter.id, matter.title, matter.client_name, matter.case_number)
                )
            ]
        else:
            matches = sorted(matters, key=lambda matter: matter.updated_at, reverse=True)[:1]

        if not matches:
            return {
                "message": "Не нашёл дело по указанному запросу.",
                "matter": None,
            }

        matter = sorted(matches, key=lambda item: item.updated_at, reverse=True)[0]
        events = sorted(self.matter_store.events(matter.id), key=lambda item: item.event_date, reverse=True)
        latest_event = events[0] if events else None
        deadlines = sorted(
            matter.deadlines,
            key=lambda item: (item.due_date is None, item.due_date.isoformat() if item.due_date else "9999-12-31"),
        )
        message = f"По делу «{matter.title}»"
        if latest_event is not None:
            message += f" последнее событие: {latest_event.title}."
        else:
            message += " новых зафиксированных событий пока нет."
        return {
            "message": message,
            "matter": {
                "id": matter.id,
                "title": matter.title,
                "case_number": matter.case_number,
                "status": matter.status,
            },
            "latest_event": (
                {
                    "title": latest_event.title,
                    "event_date": latest_event.event_date.isoformat(),
                    "description": latest_event.description,
                    "source_document": latest_event.source_document,
                }
                if latest_event is not None
                else None
            ),
            "deadlines": [
                {
                    "title": deadline.title,
                    "due_date": deadline.due_date.isoformat() if deadline.due_date else None,
                    "confidence": deadline.confidence,
                }
                for deadline in deadlines
            ],
        }

    def _latest_legal_email(self, _: dict) -> dict:
        snapshot = self.context.latest_legal_email
        if snapshot is None:
            return {
                "message": "В текущем контексте ещё нет обработанного юридического письма.",
                "email": None,
            }
        return {
            "message": f"Последнее юридическое письмо: «{snapshot.subject}» от {snapshot.sender}.",
            "email": self._email_snapshot_data(snapshot),
        }

    def _prepare_reply(self, _: dict) -> dict:
        snapshot = self.context.latest_legal_email
        if snapshot is None or snapshot.draft_body is None:
            return {
                "message": "Нет подготовленного проекта ответа. Сначала нужно обработать юридическое письмо.",
                "draft": None,
            }
        return {
            "message": "Проект ответа подготовлен и требует проверки адвокатом перед отправкой.",
            "draft": {
                "to": snapshot.draft_to,
                "subject": snapshot.draft_subject,
                "body": snapshot.draft_body,
                "requires_review": True,
                "send_performed": False,
            },
        }

    @staticmethod
    def _email_snapshot_data(snapshot) -> dict | None:
        if snapshot is None:
            return None
        return {
            "message_id": snapshot.message_id,
            "sender": snapshot.sender,
            "subject": snapshot.subject,
            "legal_relevance": snapshot.legal_relevance,
            "matter_ids": list(snapshot.matter_ids),
            "document_count": snapshot.document_count,
            "issue_count": snapshot.issue_count,
            "requires_review": snapshot.requires_review,
        }
