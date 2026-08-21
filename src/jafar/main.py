from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .config import settings
from .domains import DocumentTask, MatterType
from .document_intake import DocumentExtractionError, DocumentExtractor
from .legal_analysis import LegalAnalyzer
from .legal_models import AnalysisRequest, AnalysisResponse, Matter
from .matters import MatterStore
from .matter_matching import MatterMatch, MatterMatcher

app = FastAPI(title=settings.app_name, version="0.4.0")
analyzer = LegalAnalyzer()
matter_store = MatterStore()
document_extractor = DocumentExtractor()
matter_matcher = MatterMatcher()


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = Field(default=settings.app_name)


class CreateMatterRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    matter_type: MatterType = MatterType.GENERAL
    client_name: str | None = None
    opposing_party: str | None = None
    court_or_authority: str | None = None
    case_number: str | None = None


class MatterMatchResponse(BaseModel):
    matches: list[MatterMatch]
    assigned_matter_id: str | None = None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/v1/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    analysis = analyzer.analyze(request.text, request.task, request.matter_type)
    if request.matter_id:
        matter = matter_store.get(request.matter_id)
        if matter is None:
            raise HTTPException(status_code=404, detail="Matter not found")
        matter_store.add_deadlines(request.matter_id, analysis.deadlines)
    return AnalysisResponse(analysis=analysis, matter_id=request.matter_id)


@app.post("/v1/documents/analyze", response_model=AnalysisResponse)
async def analyze_document(
    file: UploadFile = File(...),
    task: str = "legal_analysis",
    matter_type: MatterType = MatterType.GENERAL,
    matter_id: str | None = None,
    auto_match: bool = True,
) -> AnalysisResponse:
    try:
        content = await file.read(document_extractor.MAX_BYTES + 1)
        extracted = document_extractor.extract(
            filename=file.filename or "document",
            content=content,
            media_type=file.content_type,
        )
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        document_task = DocumentTask(task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unsupported analysis task") from exc

    resolved_matter_id = matter_id
    if resolved_matter_id is None and auto_match:
        best = matter_matcher.best_match(extracted.text, matter_store.list())
        if best is not None:
            resolved_matter_id = best.matter_id

    request = AnalysisRequest(
        text=extracted.text,
        task=document_task,
        matter_type=matter_type,
        matter_id=resolved_matter_id,
    )
    return analyze(request)


@app.post("/v1/documents/match", response_model=MatterMatchResponse)
def match_document(text: str) -> MatterMatchResponse:
    matches = matter_matcher.match(text, matter_store.list())
    assigned = matches[0].matter_id if matches else None
    return MatterMatchResponse(matches=matches, assigned_matter_id=assigned)


@app.post("/v1/matters", response_model=Matter, status_code=201)
def create_matter(request: CreateMatterRequest) -> Matter:
    now = datetime.now(timezone.utc)
    matter = Matter(
        id=str(uuid4()),
        title=request.title,
        matter_type=request.matter_type,
        client_name=request.client_name,
        opposing_party=request.opposing_party,
        court_or_authority=request.court_or_authority,
        case_number=request.case_number,
        created_at=now,
        updated_at=now,
    )
    return matter_store.create(matter)


@app.get("/v1/matters", response_model=list[Matter])
def list_matters() -> list[Matter]:
    return matter_store.list()


@app.get("/v1/matters/{matter_id}", response_model=Matter)
def get_matter(matter_id: str) -> Matter:
    matter = matter_store.get(matter_id)
    if matter is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter


@app.get("/v1/matters/{matter_id}/events")
def get_matter_events(matter_id: str):
    if matter_store.get(matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter_store.events(matter_id)
