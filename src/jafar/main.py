from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import __version__
from .ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from .api_auth import api_auth_middleware
from .command_runtime import JafarCommandRuntime
from .config import settings
from .document_intake import DocumentExtractionError, DocumentExtractor
from .document_workflow import DocumentWorkflow
from .domains import DocumentTask, MatterType
from .google_oauth_api import resolve_google_oauth_subject, router as google_oauth_router
from .google_workspace import NaturalLanguageWorkspaceRouter
from .google_workspace_http import (
    GoogleWorkspaceAPIError,
    GoogleWorkspaceAuthRequiredError,
    GoogleWorkspaceError,
    GoogleWorkspaceNetworkError,
    build_google_workspace_service_from_env,
)
from .legal_analysis import LegalAnalyzer
from .legal_entity_api import router as legal_entity_router
from .legal_models import AnalysisRequest, AnalysisResponse, Matter
from .legal_research_api import router as legal_research_router
from .legal_research_runtime import build_legal_research_service_from_env
from .matter_runtime import build_matter_repository_from_env
from .memory_command_router import NaturalLanguageMemoryRouter
from .memory_commands import MemoryCommandExecutor
from .memory_runtime import build_memory_service_from_env
from .model_router import ModelRouter
from .ollama_provider import OllamaLegalAnalyzer, OllamaProviderConfig
from .persistent_matter_catalog import PersistentMatterCatalog
from .privacy_policy import ProviderPrivacyPolicy
from .routed_legal_analyzer import RoutedLegalAnalyzer
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
app.middleware("http")(api_auth_middleware)
app.include_router(legal_entity_router)
app.include_router(legal_research_router)
app.include_router(google_oauth_router)

heuristic_analyzer = LegalAnalyzer()
ollama_analyzer = OllamaLegalAnalyzer(config=OllamaProviderConfig())
openai_analyzer = (
    OpenAILegalAnalyzer(config=AIProviderConfig()) if settings.openai_api_key else None
)
model_providers = {"ollama": ollama_analyzer}
if openai_analyzer is not None:
    model_providers["openai"] = openai_analyzer
confidential_providers = (
    ("ollama", "openai")
    if settings.confidential_cloud_fallback and openai_analyzer is not None
    else ("ollama",)
)
privacy_policy = ProviderPrivacyPolicy(confidential_providers=confidential_providers)
model_router = ModelRouter(model_providers, privacy_policy=privacy_policy)
routed_analyzer = RoutedLegalAnalyzer(model_router, heuristic_analyzer)

matter_store = build_matter_repository_from_env()
document_extractor = DocumentExtractor()
document_workflow = DocumentWorkflow(matter_store, routed_analyzer)
command_runtime = JafarCommandRuntime(matter_store)
persistent_matter_catalog = PersistentMatterCatalog(matter_store)
workspace_router = NaturalLanguageWorkspaceRouter()
memory_router = NaturalLanguageMemoryRouter()
_memory_service = build_memory_service_from_env()
memory_executor = MemoryCommandExecutor(_memory_service) if _memory_service is not None else None
app.state.memory_service = _memory_service
_legal_research_service = build_legal_research_service_from_env()
app.state.legal_research_service_factory = (
    (lambda _matter_id: _legal_research_service) if _legal_research_service is not None else None
)


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


@app.post("/v1/command", response_model=CommandResponse)
def command(request: CommandRequest) -> CommandResponse:
    normalized = " ".join(request.text.lower().split())

    if "здоров" in normalized or "проверка связи" in normalized:
        intent = "health"
    elif any(phrase in normalized for phrase in ("покажи мои дела", "список дел", "мои дела")):
        intent = "list_matters"
    else:
        workspace_route = workspace_router.route(request.text)
        if workspace_route.intent is not None:
            try:
                oauth_subject = resolve_google_oauth_subject(request.user_id)
            except RuntimeError:
                return CommandResponse(
                    message="Google Workspace identity не настроен на этом сервере.",
                    intent="google_workspace_unavailable",
                    request_id=str(uuid4()),
                )
            google_workspace_service = build_google_workspace_service_from_env(oauth_subject)
            if google_workspace_service is None:
                return CommandResponse(
                    message="Google Workspace пока не подключён. Выполните OAuth-подключение.",
                    intent="google_workspace_unavailable",
                    request_id=str(uuid4()),
                    data={"oauth_subject": oauth_subject},
                )
            try:
                if workspace_route.intent == "gmail_inbox":
                    workspace_data = google_workspace_service.inbox(
                        unread_only=workspace_route.unread_only,
                        limit=10,
                    )
                else:
                    workspace_data = google_workspace_service.calendar_events(
                        window=workspace_route.window or "week",
                        limit=20,
                    )
            except GoogleWorkspaceAuthRequiredError:
                return CommandResponse(
                    message="Google Workspace не авторизован. Выполните OAuth-подключение.",
                    intent="google_workspace_auth_required",
                    request_id=str(uuid4()),
                    data={"oauth_subject": oauth_subject},
                )
            except GoogleWorkspaceNetworkError:
                return CommandResponse(
                    message="Не удалось связаться с Google Workspace. Попробуйте повторить запрос.",
                    intent="google_workspace_network_error",
                    request_id=str(uuid4()),
                    data={"oauth_subject": oauth_subject},
                )
            except GoogleWorkspaceAPIError as exc:
                messages = {
                    "api_disabled": "Нужный Google API не включён для этого проекта.",
                    "insufficient_scope": "У OAuth-подключения недостаточно разрешений Google.",
                }
                return CommandResponse(
                    message=messages.get(exc.kind, "Google Workspace вернул ошибку при чтении данных."),
                    intent="google_workspace_api_error",
                    request_id=str(uuid4()),
                    data={
                        "oauth_subject": oauth_subject,
                        "google_error_kind": exc.kind,
                        "google_status_code": exc.status_code,
                    },
                )
            except GoogleWorkspaceError:
                return CommandResponse(
                    message="Google Workspace вернул недопустимый ответ. Данные не использованы.",
                    intent="google_workspace_error",
                    request_id=str(uuid4()),
                    data={"oauth_subject": oauth_subject},
                )
            except (RuntimeError, ValueError, OSError):
                return CommandResponse(
                    message="Не удалось обработать ответ Google Workspace. Данные не использованы.",
                    intent="google_workspace_error",
                    request_id=str(uuid4()),
                    data={"oauth_subject": oauth_subject},
                )
            return CommandResponse(
                message=str(workspace_data.get("message", "Данные получены.")),
                intent=workspace_route.intent,
                request_id=str(uuid4()),
                data=workspace_data,
            )

        memory_route = memory_router.route(request.text)
        if memory_route.intent is not None:
            if memory_executor is None:
                return CommandResponse(
                    message="Долговременная память пока не настроена на этом сервере.",
                    intent="memory_unavailable",
                    request_id=str(uuid4()),
                )
            matter_reference = persistent_matter_catalog.resolve_reference(request.text)
            if matter_reference.ambiguous:
                return CommandResponse(
                    message="Не удалось однозначно определить дело для этой записи памяти. Укажите номер дела или фамилию клиента.",
                    intent="memory_needs_matter",
                    request_id=str(uuid4()),
                )
            try:
                memory_result = memory_executor.execute(
                    memory_route,
                    approved=request.approved,
                    matter_id=matter_reference.matter_id,
                )
            except (ValueError, RuntimeError):
                return CommandResponse(
                    message="Не удалось выполнить операцию с долговременной памятью.",
                    intent="memory_failed",
                    request_id=str(uuid4()),
                )
            return CommandResponse(
                message=memory_result.message,
                intent=memory_result.intent,
                approval_required=memory_result.approval_required,
                request_id=str(uuid4()),
                data=memory_result.data,
            )

        route = persistent_matter_catalog.route(request.text)
        if route.is_research:
            if route.matter_id is None:
                message = (
                    "Не удалось однозначно определить дело. Укажите фамилию клиента или номер дела."
                    if route.ambiguous
                    else "Укажите дело: фамилию клиента или номер дела."
                )
                return CommandResponse(
                    message=message,
                    intent="legal_research_needs_matter",
                    request_id=str(uuid4()),
                )
            if _legal_research_service is None:
                return CommandResponse(
                    message="Контур исследования дела пока не настроен на этом сервере.",
                    intent="legal_research_unavailable",
                    request_id=str(uuid4()),
                    data={"matter_id": route.matter_id},
                )
            try:
                research = _legal_research_service.research(
                    matter_id=route.matter_id,
                    question=request.text,
                )
            except (ValueError, RuntimeError):
                return CommandResponse(
                    message="Не удалось выполнить исследование материалов дела.",
                    intent="legal_research_failed",
                    request_id=str(uuid4()),
                    data={"matter_id": route.matter_id},
                )
            return CommandResponse(
                message=research.answer,
                intent="legal_research",
                request_id=str(uuid4()),
                data={
                    "matter_id": route.matter_id,
                    "citations": list(research.citations),
                    "contradictions": list(research.contradictions),
                    "retrieved_chunks": len(research.context.results),
                },
            )

        return CommandResponse(
            message="Команда получена. Для выполнения действия требуется дальнейшая маршрутизация intent.",
            intent="natural_language_command",
            request_id=str(uuid4()),
        )

    result = command_runtime.execute(
        intent,
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
    return routed_analyzer.analyze(text, task, matter_type)


@app.post("/v1/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    analysis = _analyze(request.text, request.task, request.matter_type)
    if request.matter_id:
        matter = matter_store.get(request.matter_id)
        if matter is None:
            raise HTTPException(status_code=404, detail="Matter not found")
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
        raise HTTPException(status_code=400, detail="Document could not be extracted safely") from exc

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
    return AnalysisResponse(
        analysis=result.analysis,
        matter_id=result.match.matter_id if result.match else matter_id,
    )


@app.post("/v1/matters", response_model=Matter, status_code=201)
def create_matter(request: CreateMatterRequest) -> Matter:
    now = datetime.now(timezone.utc)
    matter = Matter(id=str(uuid4()), title=request.title, matter_type=request.matter_type, client_name=request.client_name, opposing_party=request.opposing_party, court_or_authority=request.court_or_authority, case_number=request.case_number, created_at=now, updated_at=now)
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
