from __future__ import annotations

from dataclasses import dataclass

from .publication_runtime import DispatchablePublication


@dataclass(frozen=True)
class DryRunResult:
    publication_id: int
    chat_id: str
    media_type: str | None
    would_send: bool = True


def inspect_publication(item: DispatchablePublication) -> DryRunResult:
    return DryRunResult(
        publication_id=item.publication_id,
        chat_id=item.chat_id,
        media_type=item.media_type,
    )
