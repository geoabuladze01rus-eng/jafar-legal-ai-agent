from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CaseAction:
    title: str
    reason: str
    priority: str
    basis: tuple[str, ...] = ()
    due_at: str | None = None
    requires_approval: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class CaseActionPlanner:
    """Converts findings into proposed lawyer actions; never makes autonomous legal decisions."""

    def plan(self, *, findings: list[dict[str, Any]], deadlines: list[dict[str, Any]] | None = None, contradictions: list[dict[str, Any]] | None = None, gaps: list[dict[str, Any]] | None = None) -> list[CaseAction]:
        actions: list[CaseAction] = []
        for finding in findings:
            if finding.get("requires_human_review"):
                actions.append(CaseAction("Проверить юридический вывод", str(finding.get("statement", "")), "high", tuple(finding.get("basis", []))))
        for item in contradictions or []:
            actions.append(CaseAction("Проверить противоречие", f"{item.get('left', '')} / {item.get('right', '')}", "high" if item.get("severity") == "high" else "medium", tuple(item.get("evidence_ids", []))))
        for gap in gaps or []:
            actions.append(CaseAction("Запросить недостающие материалы", str(gap.get("description", "Недостаточно доказательств")), str(gap.get("severity", "medium")), tuple(gap.get("expected_evidence", []))))
        for deadline in deadlines or []:
            actions.append(CaseAction("Контролировать процессуальный срок", str(deadline.get("title", "")), "critical", due_at=deadline.get("due_at") or deadline.get("at")))
        return actions

    @staticmethod
    def serialize(actions: list[CaseAction]) -> list[dict[str, Any]]:
        return [{"title": a.title, "reason": a.reason, "priority": a.priority, "basis": list(a.basis), "due_at": a.due_at, "requires_approval": a.requires_approval, "metadata": a.metadata} for a in actions]
