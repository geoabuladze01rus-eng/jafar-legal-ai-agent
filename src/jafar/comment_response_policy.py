from __future__ import annotations

from dataclasses import dataclass

from .comment_classifier import CommentIntent


@dataclass(frozen=True)
class ResponseDecision:
    mode: str
    draft: str


def build_response(intent: CommentIntent, text: str) -> ResponseDecision:
    if intent is CommentIntent.PERSONAL_DATA:
        return ResponseDecision("moderate", "Пожалуйста, не публикуйте персональные данные в комментариях. Мы не будем их повторять или распространять.")
    if intent is CommentIntent.ESCALATE:
        return ResponseDecision("editor_review", "Тема требует внимательной проверки фактов и обстоятельств. Подготовим отдельный разбор.")
    if intent is CommentIntent.AGGRESSIVE:
        return ResponseDecision("auto_reply", "Понимаем эмоции. Давайте обсуждать факты и конкретные обстоятельства без перехода на личности.")
    if intent is CommentIntent.LEGAL_HELP:
        return ResponseDecision("editor_review", "В такой ситуации важны конкретные обстоятельства и документы. Мы не оказываем индивидуальную юридическую помощь в комментариях, но можем разобрать общий порядок действий.")
    if intent is CommentIntent.QUESTION:
        return ResponseDecision("auto_reply", "Спасибо за вопрос. Постараемся разобрать его по существу и опираться на подтверждённые источники.")
    return ResponseDecision("auto_reply", "Спасибо за мнение. Давайте обсудим вопрос по существу и с опорой на проверяемые факты.")
