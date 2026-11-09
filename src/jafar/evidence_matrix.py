"""Conservative cross-document evidence matrix for the encrypted desktop Matter corpus.

The engine extracts only explicitly labelled values from source text. It never
infers that similarly labelled values necessarily concern the same contract,
transaction or person. Divergences are *candidates for human review*, not
established contradictions. No AI or external services are called.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Protocol

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from pydantic import BaseModel, Field, field_validator

from .legal_draft_service import _disable_hyphenation, _nobreak_short_words
from .legal_models import Matter
from .matter_rag import MatterChunk
from .matter_repository import MatterRepository


MAX_DOCUMENTS = 12
MAX_CHUNKS_PER_DOCUMENT = 250
MAX_TEXT_CHARS_PER_DOCUMENT = 800_000
MAX_VALUES_PER_DOCUMENT = 100
MAX_LINE_CHARS = 800
MAX_QUOTE = 280


class EvidenceMatrixRequest(BaseModel):
    source_document_ids: list[str] = Field(min_length=2, max_length=MAX_DOCUMENTS)
    comparison_subject: str = Field(default="", max_length=250)

    @field_validator("source_document_ids")
    @classmethod
    def require_unique_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not item.strip() for item in values):
            raise ValueError("Source documents must be nonempty and unique")
        return values


class MatrixSource(BaseModel):
    document_id: str
    filename: str
    fingerprint: str
    chunk_count: int


class MatrixEvidence(BaseModel):
    key: str
    label: str
    value: str
    normalized: str
    document_id: str
    filename: str
    citation: str
    excerpt: str


class MatrixComparison(BaseModel):
    key: str
    label: str
    status: str
    interpretations: list[str]
    evidence: list[MatrixEvidence]


class EvidenceMatrixResponse(BaseModel):
    matter_id: str
    matter_title: str
    comparison_subject: str
    sources: list[MatrixSource]
    comparisons: list[MatrixComparison]
    other_values: list[MatrixEvidence]
    possible_difference_count: int
    warnings: list[str]


class EvidenceMatrixNotFound(ValueError):
    pass


class EvidenceMatrixTooLarge(ValueError):
    pass


class LocalCorpus(Protocol):
    def get_document(self, matter_id: str, document_id: str): ...
    def verify_document(self, matter_id: str, document_id: str) -> str: ...
    def chunks(self, matter_id: str) -> list[MatterChunk]: ...


@dataclass(frozen=True)
class _Rule:
    key: str
    label: str
    pattern: re.Pattern[str]
    value_kind: str


def _date_rule(key: str, label: str, label_expr: str) -> _Rule:
    return _Rule(
        key=key,
        label=label,
        pattern=re.compile(
            rf"^\s*(?:[-*•]\s*)?(?:{label_expr})\s*[:\-–—]\s*"
            r"(?P<value>\d{1,2}[./]\d{1,2}[./]\d{4})(?!\d)",
            re.IGNORECASE,
        ),
        value_kind="date",
    )


def _money_rule(key: str, label: str, label_expr: str) -> _Rule:
    return _Rule(
        key=key,
        label=label,
        pattern=re.compile(
            rf"^\s*(?:[-*•]\s*)?(?:{label_expr})\s*[:\-–—]\s*"
            r"(?P<value>\d[\d \u00a0\u202f]*(?:[,.]\d{1,2})?)\s*"
            r"(?:руб(?:лей|ля|ль|\.|)|₽)(?!\w)",
            re.IGNORECASE,
        ),
        value_kind="money",
    )


RULES = (
    _date_rule(
        "contract_date", "Дата заключения договора",
        r"дата(?:\s+заключения|\s+подписания)?\s+договора",
    ),
    _date_rule(
        "payment_date", "Дата платежа",
        r"дата(?:\s+осуществления)?\s+(?:платежа|оплаты)",
    ),
    _money_rule(
        "contract_amount", "Сумма договора",
        r"(?:сумма|стоимость)\s+договора",
    ),
    _money_rule(
        "debt_amount", "Сумма задолженности",
        r"(?:сумма|размер)\s+задолженности",
    ),
    _money_rule(
        "payment_amount", "Сумма платежа",
        r"сумма\s+(?:платежа|оплаты)",
    ),
)
LABELS = {rule.key: rule.label for rule in RULES}


def _normalized(value: str, value_kind: str) -> str | None:
    if value_kind == "date":
        try:
            return datetime.strptime(value.replace("/", "."), "%d.%m.%Y").date().isoformat()
        except ValueError:
            return None
    cleaned = value.replace("\u00a0", "").replace("\u202f", "").replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return f"{amount:.2f}"


def _excerpt(line: str) -> str:
    compact = " ".join(line.split())
    return compact if len(compact) <= MAX_QUOTE else compact[: MAX_QUOTE - 1].rstrip() + "…"


def _extract_from_chunk(chunk: MatterChunk, filename: str) -> list[MatrixEvidence]:
    found = []
    for line in chunk.content.splitlines():
        if len(line) > MAX_LINE_CHARS:
            continue
        for rule in RULES:
            match = rule.pattern.search(line)
            if match is None:
                continue
            raw = match.group("value")
            normalized = _normalized(raw, rule.value_kind)
            if normalized is None:
                continue
            found.append(
                MatrixEvidence(
                    key=rule.key,
                    label=rule.label,
                    value=raw.strip(),
                    normalized=normalized,
                    document_id=chunk.document_id,
                    filename=filename,
                    citation=chunk.citation,
                    excerpt=_excerpt(line),
                )
            )
            break
    return found


class EvidenceMatrixService:
    def __init__(self, matters: MatterRepository, corpus: LocalCorpus) -> None:
        self.matters = matters
        self.corpus = corpus

    def compare(self, matter_id: str, request: EvidenceMatrixRequest) -> EvidenceMatrixResponse:
        matter: Matter | None = self.matters.get(matter_id)
        if matter is None:
            raise EvidenceMatrixNotFound("Matter not found")

        sources: list[MatrixSource] = []
        selected = {}
        for document_id in request.source_document_ids:
            document = self.corpus.get_document(matter_id, document_id)
            if document is None or document.state != "READY":
                raise EvidenceMatrixNotFound("Selected document is not part of the Matter")
            self.corpus.verify_document(matter_id, document_id)
            selected[document_id] = document

        all_chunks = self.corpus.chunks(matter_id)
        by_document: dict[str, list[MatterChunk]] = defaultdict(list)
        for chunk in all_chunks:
            if chunk.document_id in selected and chunk.matter_id == matter_id:
                by_document[chunk.document_id].append(chunk)

        extracted: list[MatrixEvidence] = []
        for document_id in request.source_document_ids:
            document = selected[document_id]
            chunks = by_document[document_id]
            if len(chunks) > MAX_CHUNKS_PER_DOCUMENT:
                raise EvidenceMatrixTooLarge("Selected document has too many indexed chunks")
            if sum(len(chunk.content) for chunk in chunks) > MAX_TEXT_CHARS_PER_DOCUMENT:
                raise EvidenceMatrixTooLarge("Selected document exceeds comparison text limit")
            filename = Path(document.filename).name
            sources.append(
                MatrixSource(
                    document_id=document_id,
                    filename=filename,
                    fingerprint=document.fingerprint,
                    chunk_count=len(chunks),
                )
            )
            unique: set[tuple[str, str, str]] = set()
            count = 0
            for chunk in chunks:
                for item in _extract_from_chunk(chunk, filename):
                    key = (item.key, item.normalized, item.citation)
                    if key in unique:
                        continue
                    unique.add(key)
                    extracted.append(item)
                    count += 1
                    if count > MAX_VALUES_PER_DOCUMENT:
                        raise EvidenceMatrixTooLarge("Too many labelled values in selected document")

        grouped: dict[str, list[MatrixEvidence]] = defaultdict(list)
        for item in extracted:
            grouped[item.key].append(item)

        comparisons: list[MatrixComparison] = []
        other: list[MatrixEvidence] = []
        for rule in RULES:
            evidence = grouped.get(rule.key, [])
            per_document: dict[str, set[str]] = defaultdict(set)
            for item in evidence:
                per_document[item.document_id].add(item.normalized)
            if len(per_document) < 2:
                other.extend(evidence)
                continue
            distinct = {value for values in per_document.values() for value in values}
            ambiguous = any(len(values) > 1 for values in per_document.values())
            status = (
                "ambiguous_within_document"
                if ambiguous
                else "possible_difference" if len(distinct) > 1
                else "same_labelled_value"
            )
            notes = [
                "Поля имеют одинаковую подпись, но могут относиться к разным обязательствам "
                "или операциям; принадлежность одному событию требует проверки."
            ]
            if ambiguous:
                notes.append("В одном из документов приведено несколько разных значений одного поля.")
            elif status == "possible_difference":
                notes.append("Разные значения выявлены автоматически; противоречие не установлено.")
            else:
                notes.append("Найдено одинаковое подписанное значение; остальные сведения не сопоставлялись.")
            comparisons.append(
                MatrixComparison(
                    key=rule.key, label=rule.label, status=status,
                    interpretations=notes, evidence=evidence,
                )
            )

        warnings = [
            "Автоматически сравниваются только явно подписанные даты и суммы. "
            "Отсутствие расхождений не доказывает согласованность документов.",
            "Возможные расхождения не являются установленными противоречиями: "
            "проверяйте стороны, предмет, период и исходные документы.",
            "Технические ссылки на фрагменты не удостоверяют номера страниц или листов дела. "
            "Сканы и OCR требуют визуальной сверки с оригиналами.",
            "Справка предназначена для внутренней проверки, а не для автоматического направления в суд.",
        ]
        if not comparisons:
            warnings.insert(0, "В выбранных документах нет двух источников с сопоставимым явно подписанным полем.")
        return EvidenceMatrixResponse(
            matter_id=matter_id,
            matter_title=matter.title,
            comparison_subject=request.comparison_subject.strip(),
            sources=sources,
            comparisons=comparisons,
            other_values=other,
            possible_difference_count=sum(
                comparison.status == "possible_difference" for comparison in comparisons
            ),
            warnings=warnings,
        )


def render_matrix_docx(matrix: EvidenceMatrixResponse) -> bytes:
    """Create a review-only Word report without invented facts or page references."""
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin, section.bottom_margin = Cm(2), Cm(2)
    section.left_margin, section.right_margin = Cm(3), Cm(1.5)
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)

    def add(text: str, *, heading: bool = False) -> None:
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if heading else WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.add_run(_nobreak_short_words(text))
        _disable_hyphenation(paragraph)

    add("СЛУЖЕБНАЯ СПРАВКА ПО СОПОСТАВЛЕНИЮ ДОКУМЕНТОВ", heading=True)
    add(f"Дело: {matrix.matter_title}")
    if matrix.comparison_subject:
        add("Предмет сопоставления (указан пользователем): " + matrix.comparison_subject)
    add("Исходные документы:")
    for i, source in enumerate(matrix.sources, start=1):
        add(f"{i}. {source.filename} (идентификатор: {source.document_id})")
    add(f"Потенциальных различий для проверки: {matrix.possible_difference_count}")
    for comparison in matrix.comparisons:
        add(comparison.label + ": " + {
            "same_labelled_value": "одинаковые значения поля",
            "possible_difference": "разные значения, требуется сверка",
            "ambiguous_within_document": "несколько значений внутри источника",
        }[comparison.status])
        for item in comparison.evidence:
            add(f"{item.filename}. Значение: {item.value}. "
                f"Техническая ссылка: {item.citation}. "
                f"Извлечённая строка: «{item.excerpt}»")
        for note in comparison.interpretations:
            add(note)
    if matrix.other_values:
        add("Значения без достаточной пары для сравнения:")
        for item in matrix.other_values:
            add(f"{item.label}: {item.value}. {item.filename}. "
                f"Техническая ссылка: {item.citation}. "
                f"Извлечённая строка: «{item.excerpt}»")
    add("Ограничения проверки:")
    for warning in matrix.warnings:
        add(warning)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("ВНУТРЕННЯЯ ПРОВЕРОЧНАЯ СПРАВКА. НЕ ПРОЦЕССУАЛЬНЫЙ ДОКУМЕНТ.")
    result = BytesIO()
    doc.save(result)
    return result.getvalue()
