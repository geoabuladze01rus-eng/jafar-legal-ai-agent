from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from itertools import pairwise


@dataclass(frozen=True, slots=True)
class LegalChunk:
    """A deterministic, citeable fragment of one normalized document page."""

    content: str
    source_page: int
    section: str | None = None
    source_start: int = 0
    source_end: int = 0

    @property
    def stable_id(self) -> str:
        payload = f"v1:{self.source_page}:{self.source_start}:{self.source_end}:{self.content}".encode()
        return sha256(payload).hexdigest()


_NAMED_HEADING_RE = re.compile(
    r"^(?:раздел|глава|параграф|§|статья|часть|пункт|подпункт|chapter|section|article|part)\s+"
    r"(?:[IVXLCDM]+|\d+(?:\.\d+)*)(?:\s*[.:-]\s*|\s+).+",
    re.IGNORECASE,
)
_ALL_CAPS_RE = re.compile(r"^[А-ЯЁA-Z][А-ЯЁA-Z\s\-–—]{3,}:?$")
_DECISION_HEADING_RE = re.compile(
    r"^(?:ПОСТАНОВИЛ|ОПРЕДЕЛИЛ|ПРИГОВОРИЛ|УСТАНОВИЛ|ПРОШУ|ХОДАТАЙСТВО|ВОЗРАЖЕНИЯ)\s*:?$"
)
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[!?;])\s+|(?<=\.)\s+(?=[А-ЯЁA-Z])")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$")


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines()).strip()


def _canonical_heading(line: str) -> str:
    stripped = line.strip()
    compact = re.sub(r"\s+", "", stripped.rstrip(":"))
    if compact in {"УСТАНОВИЛ", "ПОСТАНОВИЛ", "ОПРЕДЕЛИЛ", "ПРИГОВОРИЛ"}:
        return compact
    return stripped.lstrip("# ").rstrip(":").strip()


def _is_section_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 160:
        return False
    return bool(
        stripped.startswith("#")
        or _ALL_CAPS_RE.fullmatch(stripped)
        or _DECISION_HEADING_RE.fullmatch(_canonical_heading(stripped))
        or _NAMED_HEADING_RE.fullmatch(stripped)
    )


def _is_table(lines: list[str]) -> bool:
    return len(lines) >= 2 and "|" in lines[0] and bool(_TABLE_SEPARATOR_RE.fullmatch(lines[1].strip()))


def _trim_span(value: str, start: int, end: int) -> tuple[int, int]:
    while start < end and value[start].isspace():
        start += 1
    while end > start and value[end - 1].isspace():
        end -= 1
    return start, end


def _safe_hard_split_spans(value: str, start: int, end: int, max_chars: int) -> list[tuple[int, int]]:
    """Split only on whitespace, retaining source offsets for every emitted span."""
    parts: list[tuple[int, int]] = []
    while end - start > max_chars:
        split_at = value.rfind(" ", start + 1, start + max_chars + 1)
        if split_at <= start:
            split_at = value.find(" ", start + max_chars, end)
        if split_at <= start:
            return [*parts, (start, end)]
        parts.append(_trim_span(value, start, split_at))
        start, end = _trim_span(value, split_at, end)
    if start < end:
        parts.append((start, end))
    return parts


def _line_spans(value: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in re.finditer(r"[^\n]+", value)]


def _split_oversized_spans(
    block: str, max_chars: int, *, table: bool = False
) -> list[tuple[str, int, int]]:
    if len(block) <= max_chars:
        return [(block, 0, len(block))]
    if table:
        lines = block.splitlines()
        spans = _line_spans(block)
        header = lines[:2] if _is_table(lines) else []
        first_row = len(header)
        parts: list[tuple[str, int, int]] = []
        header_text = block[spans[0][0] : spans[first_row - 1][1]] if header else ""
        current_start = spans[first_row][0] if first_row < len(spans) else 0
        current_end = current_start
        for row_start, row_end in spans[first_row:]:
            candidate_end = row_end
            content_size = len(header_text) + (1 if header_text else 0) + candidate_end - current_start
            if content_size > max_chars and current_end > current_start:
                content = "\n".join(part for part in (header_text, block[current_start:current_end]) if part)
                parts.append((content, current_start, current_end))
                current_start = row_start
            current_end = candidate_end
        if current_end > current_start:
            content = "\n".join(part for part in (header_text, block[current_start:current_end]) if part)
            parts.append((content, current_start, current_end))
        return parts

    boundaries = [0, *[match.end() for match in _SENTENCE_BOUNDARY_RE.finditer(block)], len(block)]
    sentences = [_trim_span(block, start, end) for start, end in pairwise(boundaries)]
    parts: list[tuple[int, int]] = []
    current_start: int | None = None
    current_end: int | None = None
    for start, end in sentences:
        if start >= end:
            continue
        if current_start is None or end - current_start <= max_chars:
            current_start = start if current_start is None else current_start
            current_end = end
        else:
            if current_end is not None:
                parts.append((current_start, current_end))
            if end - start <= max_chars:
                current_start, current_end = start, end
            else:
                parts.extend(_safe_hard_split_spans(block, start, end, max_chars))
                current_start = current_end = None
    if current_start is not None and current_end is not None:
        parts.append((current_start, current_end))
    return [(block[start:end], start, end) for start, end in parts]


def _paragraph_blocks(normalized: str) -> list[tuple[int, int, list[str]]]:
    blocks: list[tuple[int, int, list[str]]] = []
    start = 0
    for match in re.finditer(r"\n\s*\n", normalized):
        value = normalized[start:match.start()].strip()
        if value:
            offset = normalized.find(value, start, match.start())
            blocks.append((offset, offset + len(value), value.splitlines()))
        start = match.end()
    value = normalized[start:].strip()
    if value:
        offset = normalized.find(value, start)
        blocks.append((offset, offset + len(value), value.splitlines()))
    return blocks


def semantic_legal_chunks(
    text: str,
    *,
    source_page: int,
    target_chars: int = 2600,
    max_chars: int = 3400,
) -> list[LegalChunk]:
    """Create deterministic, page-scoped chunks without crossing legal section boundaries."""
    if source_page < 1:
        raise ValueError("source_page must be positive")
    if not 0 < target_chars <= max_chars:
        raise ValueError("target_chars must be positive and no greater than max_chars")
    normalized = _normalize(text)
    if not normalized:
        return []

    blocks: list[tuple[str | None, str, int, int, bool]] = []
    section: str | None = None
    for start, end, lines in _paragraph_blocks(normalized):
        value = normalized[start:end]
        if _is_section_heading(value):
            section = _canonical_heading(value)
            blocks.append((section, value, start, end, False))
            continue
        blocks.append((section, value, start, end, _is_table(lines)))

    chunks: list[LegalChunk] = []
    current: list[tuple[str, int, int]] = []
    current_section: str | None = None

    def flush() -> None:
        nonlocal current, current_section
        if current:
            chunks.append(
                LegalChunk(
                    content="\n\n".join(part[0] for part in current),
                    source_page=source_page,
                    section=current_section,
                    source_start=current[0][1],
                    source_end=current[-1][2],
                )
            )
        current = []
        current_section = None

    for block_section, block, start, end, table in blocks:
        pieces = _split_oversized_spans(block, max_chars, table=table)
        for piece, piece_start, piece_end in pieces:
            piece_start += start
            piece_end += start
            section_changed = current and block_section != current_section
            candidate_length = len("\n\n".join([*(item[0] for item in current), piece]))
            if current and (section_changed or candidate_length > max_chars):
                flush()
                candidate_length = len(piece)
            if not current:
                current_section = block_section
            current.append((piece, piece_start, piece_end))
            if candidate_length >= target_chars and not table:
                flush()
    flush()
    return chunks
