"""Matter-scoped, source-grounded legal document drafts for the local macOS runtime.

This composer deliberately does not invent facts, statutes, procedural standing,
court addresses, or case-file page numbers. User-authored assertions remain user
authored. Quoted extracts are review aids, not verified findings of fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal, Protocol

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from pydantic import BaseModel, Field, field_validator

from .legal_models import Matter
from .matter_repository import MatterRepository
from .matter_rag import MatterChunk


DraftKind = Literal["motion", "complaint", "objections", "appeal", "statement"]
TITLES: dict[str, str] = {
    "motion": "ХОДАТАЙСТВО",
    "complaint": "ЖАЛОБА",
    "objections": "ВОЗРАЖЕНИЯ",
    "appeal": "АПЕЛЛЯЦИОННАЯ ЖАЛОБА",
    "statement": "ЗАЯВЛЕНИЕ",
}
MAX_SOURCE_DOCUMENTS = 8
MAX_EXCERPTS_PER_DOCUMENT = 2
MAX_EXCERPT_CHARS = 320


class LegalDraftRequest(BaseModel):
    kind: DraftKind
    recipient: str = Field(default="", max_length=500)
    author: str = Field(default="", max_length=500)
    position: str = Field(default="", max_length=12_000)
    legal_basis: str = Field(default="", max_length=5_000)
    requested_action: str = Field(default="", max_length=5_000)
    source_document_ids: list[str] = Field(default_factory=list, max_length=MAX_SOURCE_DOCUMENTS)
    review_record_ids: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("source_document_ids")
    @classmethod
    def unique_document_ids(cls, ids: list[str]) -> list[str]:
        if len(set(ids)) != len(ids) or any(not value.strip() for value in ids):
            raise ValueError("Source document identifiers must be distinct and nonempty")
        return ids

    @field_validator("review_record_ids")
    @classmethod
    def unique_review_ids(cls, ids: list[str]) -> list[str]:
        if len(set(ids)) != len(ids) or any(not v.strip() for v in ids):
            raise ValueError("Review record identifiers must be distinct and nonempty")
        return ids


class LegalDraftEvidence(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    citation: str
    excerpt: str


class LegalDraftReviewSource(BaseModel):
    filename: str
    document_id: str
    citation: str
    quote: str


class LegalDraftReviewNote(BaseModel):
    record_id: str
    candidate_id: str
    note: str
    left: LegalDraftReviewSource
    right: LegalDraftReviewSource


class LegalDraftPreview(BaseModel):
    kind: DraftKind
    title: str
    matter_id: str
    matter_title: str
    case_number: str | None
    recipient: str
    author: str
    position: str
    legal_basis: str
    requested_action: str
    evidence: list[LegalDraftEvidence]
    review_notes: list[LegalDraftReviewNote] = Field(default_factory=list)
    warnings: list[str]
    can_export: bool


class LocalReviewLedger(Protocol):
    def list(self, matter_id: str) -> list: ...


class LocalCorpus(Protocol):
    def get_document(self, matter_id: str, document_id: str): ...
    def verify_document(self, matter_id: str, document_id: str) -> str: ...
    def chunks(self, matter_id: str) -> list[MatterChunk]: ...


@dataclass(frozen=True)
class DraftNotFound(Exception):
    detail: str


def _clean(value: str) -> str:
    return " ".join(value.strip().split()) if value else ""


def _trim_excerpt(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= MAX_EXCERPT_CHARS:
        return normalized
    return normalized[:MAX_EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"


class LegalDraftService:
    def __init__(
        self, matters: MatterRepository, corpus: LocalCorpus,
        review_ledger: LocalReviewLedger | None = None,
    ) -> None:
        self.matters = matters
        self.corpus = corpus
        self.review_ledger = review_ledger

    def preview(self, matter_id: str, request: LegalDraftRequest) -> LegalDraftPreview:
        matter: Matter | None = self.matters.get(matter_id)
        if matter is None:
            raise DraftNotFound("Matter not found")

        documents = {}
        for document_id in request.source_document_ids:
            doc = self.corpus.get_document(matter_id, document_id)
            if doc is None or doc.state != "READY":
                raise DraftNotFound("Source document not found in selected Matter")
            # Authenticate encrypted source bytes and content integrity before citing.
            self.corpus.verify_document(matter_id, document_id)
            documents[document_id] = doc

        evidence: list[LegalDraftEvidence] = []
        seen: dict[str, int] = {}
        selected_chunks = [
            chunk for chunk in self.corpus.chunks(matter_id)
            if chunk.matter_id == matter_id and chunk.document_id in documents
        ]
        for chunk in selected_chunks:
            if chunk.document_id not in documents or not chunk.content.strip():
                continue
            count = seen.get(chunk.document_id, 0)
            if count >= MAX_EXCERPTS_PER_DOCUMENT:
                continue
            seen[chunk.document_id] = count + 1
            evidence.append(
                LegalDraftEvidence(
                    document_id=chunk.document_id,
                    filename=Path(documents[chunk.document_id].filename).name,
                    chunk_index=chunk.chunk_index,
                    citation=chunk.citation,
                    excerpt=_trim_excerpt(chunk.content),
                )
            )

        review_notes: list[LegalDraftReviewNote] = []
        if request.review_record_ids:
            if self.review_ledger is None:
                raise DraftNotFound("Local reviewer decisions are unavailable")
            # This list comes from an AES-GCM encrypted Matter-scoped ledger.
            all_reviews = self.review_ledger.list(matter_id)
            by_id = {record.record_id: record for record in all_reviews}
            newest_by_candidate = {}
            for record in all_reviews:
                newest_by_candidate.setdefault(record.candidate_id, record)
            chunks_by_citation = {chunk.citation: chunk for chunk in selected_chunks}
            for record_id in request.review_record_ids:
                record = by_id.get(record_id)
                if record is None or record.matter_id != matter_id:
                    raise DraftNotFound("Reviewer decision not found in selected Matter")
                if (
                    record.decision != "keep_for_work"
                    or newest_by_candidate.get(record.candidate_id).record_id != record.record_id
                ):
                    raise ValueError("Reviewer note is dismissed, superseded or not marked for work")
                sources: list[LegalDraftReviewSource] = []
                for claim in (record.left, record.right):
                    if claim.document_id not in documents:
                        raise ValueError("Reviewer note refers to a document not selected for this draft")
                    chunk = chunks_by_citation.get(claim.citation)
                    if chunk is None or chunk.document_id != claim.document_id:
                        raise ValueError("Reviewer note source fragment is unavailable")
                    # The note can only be exported if its *original* exact quotation
                    # still occurs in the current authenticated local source.
                    if " ".join(claim.quote.split()) not in " ".join(chunk.content.split()):
                        raise ValueError("Reviewer note quotation failed source verification")
                    filename = Path(documents[claim.document_id].filename).name
                    if claim.filename != filename:
                        raise ValueError("Reviewer note source filename has changed")
                    sources.append(
                        LegalDraftReviewSource(
                            filename=filename, document_id=claim.document_id,
                            citation=claim.citation, quote=claim.quote,
                        )
                    )
                review_notes.append(
                    LegalDraftReviewNote(
                        record_id=record.record_id,
                        candidate_id=record.candidate_id,
                        note=record.note,
                        left=sources[0], right=sources[1],
                    )
                )

        warnings: list[str] = []
        if review_notes:
            warnings.append(
                "Отобранные рабочие замечания помещены только в служебный лист "
                "после разрыва страницы, не в текст процессуального документа. "
                "Статус «оставить для работы» не подтверждает достоверность фактов."
            )
        required = {
            "recipient": "Не указан адресат документа",
            "author": "Не указаны заявитель и его процессуальное положение",
            "position": "Не изложены обстоятельства и позиция заявителя",
            "legal_basis": "Не заполнены правовые основания; нормы не подставляются автоматически",
            "requested_action": "Не сформулирована просительная часть",
        }
        for field_name, warning in required.items():
            if not _clean(getattr(request, field_name)):
                warnings.append(warning)
        if not request.source_document_ids:
            warnings.append("Не выбраны материалы дела для сверки фактических утверждений")
        if request.source_document_ids and not evidence:
            warnings.append("В выбранных документах нет доступных текстовых фрагментов")
        if not _clean(matter.case_number or ""):
            warnings.append("Номер дела не указан в карточке; проверьте необходимость его внесения")
        warnings.append(
            "Ссылки на фрагменты служебные: они не подтверждают номера листов дела или "
            "достоверность изложенных заявителем обстоятельств"
        )
        warnings.append(
            "Перед подачей юрист обязан проверить подведомственность, адресата, "
            "процессуальное положение, применимые нормы и все утверждения"
        )

        export_blockers = any(
            not _clean(getattr(request, field_name)) for field_name in required
        ) or not evidence
        return LegalDraftPreview(
            kind=request.kind,
            title=TITLES[request.kind],
            matter_id=matter_id,
            matter_title=matter.title,
            case_number=matter.case_number,
            recipient=request.recipient.strip(),
            author=request.author.strip(),
            position=request.position.strip(),
            legal_basis=request.legal_basis.strip(),
            requested_action=request.requested_action.strip(),
            evidence=evidence,
            review_notes=review_notes,
            warnings=warnings,
            can_export=not export_blockers,
        )


def _nobreak_short_words(text: str) -> str:
    """Prevent dangling short Russian prepositions/conjunctions in Word paragraphs."""
    import re

    return re.sub(
        r"(?<!\w)(в|во|к|ко|с|со|у|о|об|от|из|за|по|на|не|и|а|но|до|при)\s+",
        lambda match: match.group(1) + "\u00a0",
        text,
        flags=re.IGNORECASE,
    )


def _paragraph(doc: Document, value: str, *, centered: bool = False) -> None:
    for part in value.split("\n"):
        if not part.strip():
            continue
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.first_line_indent = None if centered else Cm(1.25)
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.line_spacing = 1.15
        paragraph.add_run(_nobreak_short_words(part.strip()))


def _disable_hyphenation(paragraph) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    element = OxmlElement("w:suppressAutoHyphens")
    element.set(qn("w:val"), "1")
    ppr.append(element)


def render_legal_draft_docx(preview: LegalDraftPreview) -> bytes:
    """Export a clearly marked, unsigned working draft only after all required fields exist."""
    if not preview.can_export:
        raise ValueError("Draft has unresolved required fields or no validated source excerpts")

    document = Document()
    section = document.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21)
    section.top_margin, section.bottom_margin = Cm(2), Cm(2)
    section.left_margin, section.right_margin = Cm(3), Cm(1.5)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.widow_control = True

    # A two-column header keeps the addressee on the right without visible borders.
    header_table = document.add_table(rows=1, cols=2)
    header_table.autofit = False
    header_table.columns[0].width = Cm(7.5)
    header_table.columns[1].width = Cm(9)
    recipient_cell = header_table.cell(0, 1)
    recipient_cell.text = ""
    for line in (preview.recipient, "От: " + preview.author):
        p = recipient_cell.paragraphs[0] if not recipient_cell.paragraphs[0].text else recipient_cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.add_run(_nobreak_short_words(line))
    # Grid borders absent by default; strip explicit table borders if present.
    tbl_pr = header_table._tbl.tblPr
    existing = tbl_pr.find(qn("w:tblBorders"))
    if existing is not None:
        tbl_pr.remove(existing)

    _paragraph(document, preview.title, centered=True)
    if preview.case_number:
        _paragraph(document, "По делу № " + preview.case_number)
    else:
        _paragraph(document, "По материалам: " + preview.matter_title)
    _paragraph(document, preview.position)
    _paragraph(document, "Правовые основания: " + preview.legal_basis)
    _paragraph(document, "ПРОШУ:")
    _paragraph(document, preview.requested_action)

    # Only selected and cryptographically verified sources appear in the source list.
    _paragraph(document, "Приложения (подлежат сверке с материалами дела):")
    unique = dict.fromkeys(item.filename for item in preview.evidence)
    for i, filename in enumerate(unique, start=1):
        _paragraph(document, f"{i}. {filename}")

    document.add_page_break()
    _paragraph(document, "СЛУЖЕБНЫЙ ЛИСТ ПРОВЕРКИ ИСТОЧНИКОВ", centered=True)
    _paragraph(
        document,
        "Этот лист предназначен для внутренней проверки юристом. Указанные фрагменты "
        "не являются ссылками на листы уголовного или судебного дела."
    )
    for item in preview.evidence:
        _paragraph(
            document,
            f"Документ: {item.filename}. Фрагмент № {item.chunk_index + 1}. "
            f"Техническая ссылка: {item.citation}."
        )
        _paragraph(document, "Извлечённый текст: " + item.excerpt)
    if preview.review_notes:
        _paragraph(document, "РАБОЧИЕ ЗАМЕЧАНИЯ ЮРИСТА (ВНУТРЕННЯЯ ПРОВЕРКА)", centered=True)
        _paragraph(
            document, "Записи включены по выбору юриста и не удостоверяют "
            "подлинность документов или факт противоречия. Этот раздел не "
            "предназначен для подачи в суд."
        )
        for index, note in enumerate(preview.review_notes, 1):
            _paragraph(document, f"Замечание № {index}. Позиция юриста: {note.note}")
            for source in (note.left, note.right):
                _paragraph(
                    document, f"Документ: {source.filename}. "
                    f"Техническая ссылка: {source.citation}. "
                    f"Дословная выдержка: «{source.quote}»"
                )
    for warning in preview.warnings:
        _paragraph(document, warning)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("ПРОЕКТ. НЕ ПОДПИСАН. ТРЕБУЕТ ПРОВЕРКИ ЮРИСТОМ.")
    for paragraph in document.paragraphs:
        _disable_hyphenation(paragraph)

    buf = BytesIO()
    document.save(buf)
    return buf.getvalue()
