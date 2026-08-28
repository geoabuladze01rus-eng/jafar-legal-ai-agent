from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import __version__
from .ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from .api_security import require_api_key
from .command_runtime import JafarCommandRuntime
from .config import settings
from .deadline_repository import DeadlineRepository, MatterDeadlineSummary
from .document_intake import DocumentExtractionError, DocumentExtractor
from .document_repository import (
    EmptyDocumentRepository,
    MatterDocumentSummary,
    SupabaseDocumentRepository,
)
from .document_workflow import DocumentWorkflow
from .domains import DocumentTask, MatterType
from .gmail_gateway import make_local_gmail_gateway
from .lawyer_context import LawyerContext
from .legal_analysis import LegalAnalyzer
from .legal_entity_api import router as legal_entity_router
from .legal_models import AnalysisRequest, AnalysisResponse, Matter
from .legal_position_service import LegalPositionRead, LegalPositionReadService
from .matters import MatterStore
from .supabase_config import SupabaseSettings, build_supabase_client
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


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
app.include_router(legal_entity_router)
heuristic_analyzer = LegalAnalyzer()
openai_analyzer = (
    OpenAILegalAnalyzer(config=AIProviderConfig())
    if settings.external_ai_enabled and settings.openai_api_key
    else None
)


class ResilientLegalAnalyzer:
    """Use structured OpenAI analysis when configured, with deterministic local fallback."""

    def analyze(
        self,
        text: str,
        task: DocumentTask,
        matter_type: MatterType = MatterType.GENERAL,
    ):
        if openai_analyzer is not None:
            try:
                return openai_analyzer.analyze(
                    text=text,
                    task=task,
                    matter_type=matter_type,
                )
            except RuntimeError:
                pass
        return heuristic_analyzer.analyze(text, task, matter_type)


analyzer = ResilientLegalAnalyzer()
matter_store = MatterStore()
lawyer_context = LawyerContext()
document_extractor = DocumentExtractor()
document_workflow = DocumentWorkflow(matter_store, analyzer)
try:
    supabase_client = build_supabase_client(SupabaseSettings())
    document_repository = SupabaseDocumentRepository(supabase_client)
    from .legal_position_service import SupabaseAnalysisRepository
    legal_position_service = LegalPositionReadService(matter_store, SupabaseAnalysisRepository(supabase_client), SupabaseDocumentRepository(supabase_client))
except Exception:  # noqa: BLE001 - absent local Supabase configuration uses safe fallback.
    document_repository = EmptyDocumentRepository()
deadline_repository = DeadlineRepository(matter_store)
legal_position_service = LegalPositionReadService(matter_store)
command_runtime = JafarCommandRuntime(
    matter_store,
    lawyer_context,
    mail_gateway=make_local_gmail_gateway(),
)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = Field(default=settings.app_name)


class ReadinessResponse(BaseModel):
    status: str
    version: str
    backend: str
    gmail_configured: bool
    outlook_configured: bool = False
    local_db_configured: bool = False
    external_ai_enabled: bool
    voice_client: str = "local-client"


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
    approved: bool = False


class CommandResponse(BaseModel):
    message: str
    intent: str
    approval_required: bool = False
    request_id: str
    data: dict | None = None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/readiness", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    """Expose safe component status only; never return credentials or client data."""
    gmail_configured = (
        bool(settings.gmail_client_secrets_path)
        if hasattr(settings, "gmail_client_secrets_path")
        else False
    )
    return ReadinessResponse(
        status="ready",
        version=__version__,
        backend="ready",
        gmail_configured=gmail_configured,
        external_ai_enabled=settings.external_ai_enabled,
    )


def _resolve_command(text: str) -> tuple[str | None, dict]:
    normalized = " ".join(text.lower().split())
    if "здоров" in normalized or "проверка связи" in normalized:
        return "health", {}
    if any(
        phrase in normalized
        for phrase in ("что требует моего внимания", "что требует внимания")
    ):
        return "attention_summary", {}
    if "что нового по делу" in normalized:
        query = normalized.split("что нового по делу", 1)[1].strip(" ?!.,:;«»\"")
        return "matter_update", {"query": query}
    if any(
        phrase in normalized
        for phrase in ("разбери последнее юридическое письмо", "последнее юридическое письмо")
    ):
        return "latest_legal_email", {}
    if any(phrase in normalized for phrase in ("подготовь ответ", "подготовить ответ")):
        return "prepare_reply", {}
    if any(
        phrase in normalized
        for phrase in ("покажи мои дела", "список дел", "мои дела")
    ):
        return "list_matters", {}
    return None, {}


@app.post(
    "/v1/command",
    response_model=CommandResponse,
    dependencies=[Depends(require_api_key)],
)
def command(request: CommandRequest) -> CommandResponse:
    intent, args = _resolve_command(request.text)
    if intent is None:
        return CommandResponse(
            message=(
                "Команда получена. Для выполнения действия требуется "
                "дальнейшая маршрутизация intent."
            ),
            intent="natural_language_command",
            request_id=str(uuid4()),
        )

    result = command_runtime.execute(
        intent,
        args=args,
        approved=request.approved,
    )
    return CommandResponse(
        message=result.message,
        intent=result.intent,
        approval_required=result.approval_required,
        request_id=result.request_id,
        data=result.data,
    )


def _analyze(text: str, task: DocumentTask, matter_type: MatterType):
    return analyzer.analyze(text, task, matter_type)


@app.post(
    "/v1/analyze",
    response_model=AnalysisResponse,
    dependencies=[Depends(require_api_key)],
)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    analysis = _analyze(request.text, request.task, request.matter_type)
    if request.matter_id:
        matter = matter_store.get(request.matter_id)
        if matter is None:
            raise HTTPException(status_code=404, detail="Matter not found")
        matter_store.add_deadlines(request.matter_id, analysis.deadlines)
    return AnalysisResponse(analysis=analysis, matter_id=request.matter_id)


@app.post(
    "/v1/documents/analyze",
    response_model=AnalysisResponse,
    dependencies=[Depends(require_api_key)],
)
async def analyze_document(
    file: UploadFile = File(...),  # noqa: B008 - FastAPI dependency declaration.
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
        file.filename or "document",
        extracted,
        document_task,
        matter_type,
        matter_id=matter_id,
    )
    resolved_matter_id = result.match.matter_id if result.match else matter_id
    return AnalysisResponse(analysis=result.analysis, matter_id=resolved_matter_id)


@app.post(
    "/v1/matters",
    response_model=Matter,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
def create_matter(request: CreateMatterRequest) -> Matter:
    now = datetime.now(UTC)
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


@app.get(
    "/v1/matters",
    response_model=list[Matter],
    dependencies=[Depends(require_api_key)],
)
def list_matters() -> list[Matter]:
    return matter_store.list_matters()


@app.get(
    "/v1/matters/{matter_id}",
    response_model=Matter,
    dependencies=[Depends(require_api_key)],
)
def get_matter(matter_id: str) -> Matter:
    matter = matter_store.get(matter_id)
    if matter is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter

@app.get("/v1/matters/{matter_id}/documents", response_model=list[MatterDocumentSummary], dependencies=[Depends(require_api_key)])
def list_matter_documents(matter_id: str) -> list[MatterDocumentSummary]:
    if matter_store.get(matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return document_repository.list_for_matter(matter_id)

@app.get("/v1/matters/{matter_id}/deadlines", response_model=list[MatterDeadlineSummary], dependencies=[Depends(require_api_key)])
def list_matter_deadlines(matter_id: str) -> list[MatterDeadlineSummary]:
    if matter_store.get(matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return deadline_repository.list_for_matter(matter_id)

@app.get("/v1/matters/{matter_id}/legal-position", response_model=LegalPositionRead, dependencies=[Depends(require_api_key)])
def get_legal_position(matter_id: str) -> LegalPositionRead:
    try:
        return legal_position_service.get(matter_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Matter not found") from exc


@app.get(
    "/v1/matters/{matter_id}/events",
    dependencies=[Depends(require_api_key)],
)
def get_matter_events(matter_id: str):
    if matter_store.get(matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter_store.events(matter_id)
