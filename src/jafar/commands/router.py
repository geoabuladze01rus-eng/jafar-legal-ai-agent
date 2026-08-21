import re

from jafar.commands.models import CommandKind, CommandRequest, CommandResult


_PATTERNS: list[tuple[CommandKind, str]] = [
    (CommandKind.SEARCH_MATTER, r"\b(найди|поищи|поиск)\b"),
    (CommandKind.ANALYZE_DOCUMENT, r"\b(проанализируй|анализ|разбери)\b"),
    (CommandKind.LIST_DEADLINES, r"\b(срок|сроки|дедлайн|дедлайны)\b"),
    (CommandKind.REVIEW_EMAIL, r"\b(почт|письм|email|mail)\w*\b"),
    (CommandKind.CREATE_DRAFT, r"\b(черновик|подготовь ответ|ответ)\b"),
]


def route_command(request: CommandRequest) -> CommandResult:
    text = request.text.strip()
    if not text:
        return CommandResult(command=CommandKind.SEARCH_MATTER, status="rejected", message="Пустая команда")

    for kind, pattern in _PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return CommandResult(
                command=kind,
                status="accepted",
                message=f"Команда распознана: {kind.value}",
                requires_approval=kind == CommandKind.CREATE_DRAFT,
            )

    return CommandResult(
        command=CommandKind.SEARCH_MATTER,
        status="needs_clarification",
        message="Не удалось однозначно определить команду.",
    )
