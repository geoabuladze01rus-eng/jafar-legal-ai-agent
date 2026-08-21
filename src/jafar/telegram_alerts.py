from __future__ import annotations

from .comment_router import CommentRoute


def owner_alert(text: str, route: CommentRoute) -> str:
    return (
        "🚨 ТРЕБУЕТСЯ ВНИМАНИЕ\n\n"
        f"Маршрут: {route.action}\n"
        f"Причина: {route.reason}\n\n"
        f"Комментарий:\n{text.strip()}"
    )
