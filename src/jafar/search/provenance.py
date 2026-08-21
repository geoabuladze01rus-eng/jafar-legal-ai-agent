from dataclasses import dataclass


@dataclass(frozen=True)
class SourceReference:
    chunk_id: str
    source: str
    page: int | None = None
    quote: str | None = None


def make_reference(chunk_id: str, source: str, page: int | None = None, quote: str | None = None) -> SourceReference:
    return SourceReference(chunk_id=chunk_id, source=source, page=page, quote=quote)
