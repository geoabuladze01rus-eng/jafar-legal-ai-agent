from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .config import settings
from .domains import DocumentTask, MatterType
from .document_intake import DocumentExtractionError, DocumentExtractor
from .document_workflow import DocumentWorkflow
from .legal_analysis import LegalAnalyzer
from .legal_models import AnalysisRequest, AnalysisResponse, Matter
from .matters import MatterStore

app = FastAPI(title=settings.app_name, version="0.4.0")
analyzer = LegalAnalyzer()
matter_store = MatterStore()
document_extractor = DocumentExtractor()
document_workflow = DocumentWorkflow(matter_store, analyzer)


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

    if matter_id:
        if matter_store.get(matter_id) is None:
            raise HTTPException(status_code=404, detail="Matter not found")
        result = document_workflow.process(
            file.filename or "document", extracted, document_task, matter_type
        )
        return AnalysisResponse(analysis=result.analysis, matter_id=result.match.matter_id if result.match else None)

    result = document_workflow.process(file.filename or "document", extracted, document_task, matter_type)
    return AnalysisResponse(analysis=result.analysis, matter_id=result.match.matter_id if result.match else None)


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
    return matter_store.list_matters()


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
