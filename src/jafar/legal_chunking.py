from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class LegalChunk:
    content: str
    source_page: int
    section: str | None = None


_SECTION_RE = re.compile(
    r"^(?:#{1,6}\s+.+|[А-ЯЁA-Z][А-ЯЁA-Z\s\-–—]{3,}:?|(?:ПОСТАНОВИЛ|ОПРЕДЕЛИЛ|ПРИГОВОРИЛ|УСТАНОВИЛ|ПРОШУ|ХОДАТАЙСТВО|ВОЗРАЖЕНИЯ)\s*:?)$"
)
_SENTENCE_END_RE = re.compile(r"(?<=[.!?;:])\s+(?=[А-ЯЁA-Z0-9])")


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines()).strip()


def _is_section_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 160:
        return False
    return bool(_SECTION_RE.match(stripped))


def _split_oversized(block: str, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]
    sentences = _SENTENCE_END_RE.split(block)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            parts.append(current)
            current = ""
        if len(sentence) <= max_chars:
            current = sentence
            continue
        for start in range(0, len(sentence), max_chars):
            parts.append(sentence[start : start + max_chars].strip())
    if current:
        parts.append(current)
    return [part for part in parts if part]


def semantic_legal_chunks(
    text: str,
    *,
    source_page: int,
    target_chars: int = 2600,
    max_chars: int = 3400,
) -> list[LegalChunk]:
    """Split legal text on headings/paragraphs, then sentences, before hard cuts."""
    normalized = _normalize(text)
    if not normalized:
        return []

    blocks: list[tuple[str | None, str]] = []
    section: str | None = None
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            value = "\n".join(paragraph).strip()
            if value:
                blocks.append((section, value))
            paragraph.clear()

    for line in normalized.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if _is_section_heading(stripped):
            flush_paragraph()
            section = stripped.lstrip("# ").rstrip(":").strip()
            blocks.append((section, stripped))
            continue
        paragraph.append(stripped)
    flush_paragraph()

    chunks: list[LegalChunk] = []
    current_parts: list[str] = []
    current_section: str | None = None

    def flush_chunk() -> None:
        nonlocal current_parts, current_section
        content = "\n\n".join(current_parts).strip()
        if content:
            chunks.append(LegalChunk(content=content, source_page=source_page, section=current_section))
        current_parts = []
        current_section = None

    for block_section, block in blocks:
        for part in _split_oversized(block, max_chars):
            candidate = "\n\n".join([*current_parts, part]).strip()
            section_changed = current_section is not None and block_section not in {None, current_section}
            if current_parts and (len(candidate) > max_chars or (section_changed and len(candidate) >= target_chars)):
                flush_chunk()
            if not current_parts:
                current_section = block_section
            elif current_section is None and block_section is not None:
                current_section = block_section
            current_parts.append(part)
            if len("\n\n".join(current_parts)) >= target_chars and part.endswith((".", ";", ":")):
                flush_chunk()

    flush_chunk()
    return chunks
