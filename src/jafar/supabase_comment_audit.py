from __future__ import annotations

from typing import Any

import httpx

from .comment_pipeline import CommentPipelineResult


class SupabaseCommentAuditSink:
    def __init__(self, url: str, service_key: str, *, timeout: float = 15.0) -> None:
        self.base_url = url.rstrip("/")
        self.service_key = service_key
        self.timeout = timeout

    async def write(self, result: CommentPipelineResult) -> None:
        record = result.audit
        payload: dict[str, Any] = {
            "update_id": record.update_id,
            "chat_id": record.chat_id,
            "message_id": record.message_id,
            "user_id": record.user_id,
            "username": record.username,
            "intent": record.intent,
            "decision_mode": record.decision_mode,
            "draft": record.draft,
            "status": record.status,
            "created_at": record.created_at,
        }
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/rest/v1/telegram_comment_audit",
                headers=headers,
                json=payload,
            )
        response.raise_for_status()
