from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .api_security import require_api_key
from .config import settings
from .domains import DocumentTask, MatterType
from .document_intake import DocumentExtractionError, DocumentExtractor
from .document_workflow import DocumentWorkflow
from .legal_analysis import LegalAnalyzer
from .legal_entity_api import router as legal_entity_router
from .legal_models import AnalysisRequest, AnalysisResponse, Matter
from .matters import MatterStore
from .telegram_runtime import TelegramRuntime

telegram_runtime: TelegramRuntime | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_runtime
    if settings.telegram_polling_enabled and settings.telegram_bot_token:
        telegram_runtime = TelegramRuntime(
            settings.telegram_bot_token,
            production_send=settings.telegram_production_send,
        )
        telegram_runtime.start()
    try:
        yield
    finally:
        if telegram_runtime is not None:
            await telegram_runtime.stop()
            telegram_runtime = None


app = FastAPI(title=settings.app_name, version="0.5.1", lifespan=lifespan)
app.include_router(legal_entity_router)
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


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    user_id: str = Field(min_length=1, max_length=200)
    source_device: str = Field(min_length=1, max_length=100)


class CommandResponse(BaseModel):
    message: str
    intent: str
    approval_required: bool = False


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/v1/command", response_model=CommandResponse, dependencies=[Depends(require_api_key)])
def command(request: CommandRequest) -> CommandResponse:
    """Minimal safe command gateway for Apple clients.

    Read-only commands are handled here; externally visible actions remain
    behind the existing approval boundary.
    """
    normalized = " ".join(request.text.lower().split())

    if any(phrase in normalized for phrase in ("покажи мои дела", "список дел", "мои дела")):
        matters = matter_store.list_matters()
        if not matters:
            return CommandResponse(message="Сейчас открытых дел в хранилище нет.", intent="list_matters")
        titles = ", ".join(matter.title for matter in matters[:10])
        suffix = "" if len(matters) <= 10 else f" и ещё {len(matters) - 10}"
        return CommandResponse(
            message=f"У вас {len(matters)} дел: {titles}{suffix}.",
            intent="list_matters",
        )

    if "здоров" in normalized or "проверка связи" in normalized:
        return CommandResponse(message="Джафар на связи.", intent="health")

    return CommandResponse(
        message="Команда получена. Для выполнения действия требуется дальнейшая маршрутизация intent.",
        intent="natural_language_command",
    )


@app.post("/v1/analyze", response_model=AnalysisResponse, dependencies=[Depends(require_api_key)])
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    analysis = analyzer.analyze(request.text, request.task, request.matter_type)
    if request.matter_id:
        matter = matter_store.get(request.matter_id)
        if matter is None:
            raise HTTPException(status_code=404, detail="Matter not found")
        matter_store.add_deadlines(request.matter_id, analysis.deadlines)
    return AnalysisResponse(analysis=analysis, matter_id=request.matter_id)


@app.post("/v1/documents/analyze", response_model=AnalysisResponse, dependencies=[Depends(require_api_key)])
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

    if matter_id and matter_store.get(matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")

    result = document_workflow.process(
        file.filename or "document", extracted, document_task, matter_type
    )
    return AnalysisResponse(
        analysis=result.analysis,
        matter_id=result.match.matter_id if result.match else matter_id,
    )


@app.post("/v1/matters", response_model=Matter, status_code=201, dependencies=[Depends(require_api_key)])
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


@app.get("/v1/matters", response_model=list[Matter], dependencies=[Depends(require_api_key)])
def list_matters() -> list[Matter]:
    return matter_store.list_matters()


@app.get("/v1/matters/{matter_id}", response_model=Matter, dependencies=[Depends(require_api_key)])
def get_matter(matter_id: str) -> Matter:
    matter = matter_store.get(matter_id)
    if matter is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter


@app.get("/v1/matters/{matter_id}/events", dependencies=[Depends(require_api_key)])
def get_matter_events(matter_id: str):
    if matter_store.get(matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter_store.events(matter_id)
