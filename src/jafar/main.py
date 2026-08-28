from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hmac
import os
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .action_approval import (
    ActionApprovalStore,
    ActionRequest,
    ActionState,
    LegalActionApprovalEngine,
)
from .ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from .command_runtime import JafarCommandRuntime
from .config import settings
from .dashboard import DashboardService, DashboardSnapshot
from .document_intake import DocumentExtractionError, DocumentExtractor
from .document_workflow import DocumentWorkflow
from .domains import DocumentTask, MatterType
from .legal_analysis import LegalAnalyzer
from .legal_entity_api import router as legal_entity_router
from .legal_models import AnalysisRequest, AnalysisResponse, Matter
from .matters import MatterStore
from .telegram_runtime import TelegramRuntime

telegram_runtime: TelegramRuntime | None = None


def validate_runtime_security() -> None:
    if settings.environment.strip().casefold() != "production":
        return
    api_key = (settings.api_key or "").strip()
    placeholders = {"replace-me", "changeme", "change-me", "secret"}
    if len(api_key) < 24 or api_key.casefold() in placeholders:
        raise RuntimeError(
            "Production requires a non-placeholder API_KEY of at least 24 characters"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_runtime
    validate_runtime_security()
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


app = FastAPI(title=settings.app_name, version="0.8.0", lifespan=lifespan)
app.include_router(legal_entity_router)
heuristic_analyzer = LegalAnalyzer()
openai_analyzer = (
    OpenAILegalAnalyzer(config=AIProviderConfig()) if os.getenv("OPENAI_API_KEY") else None
)
matter_store = MatterStore()
document_extractor = DocumentExtractor()
document_workflow = DocumentWorkflow(matter_store, heuristic_analyzer)
command_runtime = JafarCommandRuntime(matter_store)
dashboard_service = DashboardService(matter_store)
action_approval_store = ActionApprovalStore()
action_approval_engine = LegalActionApprovalEngine(action_approval_store)


@app.middleware("http")
async def protect_v1_api(request: Request, call_next):
    if request.url.path.startswith("/v1"):
        if settings.environment.strip().casefold() == "production" and not settings.api_key:
            return JSONResponse(
                status_code=503,
                content={"detail": "Production API authentication is not configured"},
            )
        if settings.api_key:
            supplied = request.headers.get("Authorization", "")
            expected = f"Bearer {settings.api_key}"
            if not hmac.compare_digest(supplied, expected):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


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


class ApprovalItemResponse(BaseModel):
    action_id: str
    action_type: str
    description: str
    requested_by: str
    state: ActionState
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    executed_at: str | None = None


class ApprovalDecisionRequest(BaseModel):
    approver: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=2000)


class ApprovalDecisionResponse(BaseModel):
    action_id: str
    state: ActionState
    decided_by: str
    decided_at: str
    reason: str | None = None


def _approval_item(request: ActionRequest) -> ApprovalItemResponse:
    return ApprovalItemResponse(
        action_id=request.action_id,
        action_type=request.action_type,
        description=request.description,
        requested_by=request.requested_by,
        state=request.state,
        evidence_ids=list(request.evidence_ids),
        created_at=request.created_at,
        decided_at=request.decided_at,
        decided_by=request.decided_by,
        decision_reason=request.decision_reason,
        executed_at=request.executed_at,
    )


def _dashboard_snapshot() -> DashboardSnapshot:
    pending = action_approval_store.pending()
    approval_signals = tuple(
        dashboard_service.approval_signal(
            action_id=item.action_id,
            action_type=item.action_type,
            description=item.description,
        )
        for item in pending
    )
    return dashboard_service.snapshot(
        pending_approvals=len(pending),
        extra_signals=approval_signals,
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/v1/dashboard", response_model=DashboardSnapshot)
def dashboard() -> DashboardSnapshot:
    return _dashboard_snapshot()


@app.get("/v1/approvals", response_model=list[ApprovalItemResponse])
def approvals(state: ActionState | None = None) -> list[ApprovalItemResponse]:
    actions = action_approval_store.all()
    if state is not None:
        actions = tuple(item for item in actions if item.state is state)
    return [_approval_item(item) for item in actions]


@app.post(
    "/v1/approvals/{action_id}/approve",
    response_model=ApprovalDecisionResponse,
)
def approve_action(
    action_id: str,
    request: ApprovalDecisionRequest,
) -> ApprovalDecisionResponse:
    action = action_approval_store.get(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Approval action not found")
    try:
        result = action_approval_engine.approve(action, request.approver)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApprovalDecisionResponse(
        action_id=result["action_id"],
        state=ActionState(result["state"]),
        decided_by=str(result["approved_by"]),
        decided_at=str(result["decided_at"]),
    )


@app.post(
    "/v1/approvals/{action_id}/reject",
    response_model=ApprovalDecisionResponse,
)
def reject_action(
    action_id: str,
    request: ApprovalDecisionRequest,
) -> ApprovalDecisionResponse:
    action = action_approval_store.get(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Approval action not found")
    reason = (request.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Rejection reason is required")
    try:
        result = action_approval_engine.reject(action, request.approver, reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApprovalDecisionResponse(
        action_id=result["action_id"],
        state=ActionState(result["state"]),
        decided_by=str(result["rejected_by"]),
        decided_at=str(result["decided_at"]),
        reason=str(result["reason"]),
    )


@app.post("/v1/command", response_model=CommandResponse)
def command(request: CommandRequest) -> CommandResponse:
    normalized = " ".join(request.text.lower().split())

    if "здоров" in normalized or "проверка связи" in normalized:
        intent = "health"
    elif any(
        phrase in normalized
        for phrase in ("покажи мои дела", "список дел", "мои дела")
    ):
        intent = "list_matters"
    else:
        return CommandResponse(
            message=(
                "Команда получена. Для выполнения действия требуется дальнейшая "
                "маршрутизация intent."
            ),
            intent="natural_language_command",
            request_id=str(uuid4()),
        )

    result = command_runtime.execute(intent, approved=request.approved)
    return CommandResponse(
        message=result.message,
        intent=result.intent,
        approval_required=result.approval_required,
        request_id=result.request_id,
        data=result.data,
    )


def _analyze(text: str, task: DocumentTask, matter_type: MatterType):
    if openai_analyzer is not None:
        return openai_analyzer.analyze(text=text, task=task, matter_type=matter_type)
    return heuristic_analyzer.analyze(text, task, matter_type)


@app.post("/v1/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    analysis = _analyze(request.text, request.task, request.matter_type)
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

    if matter_id and matter_store.get(matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")

    if openai_analyzer is not None:
        analysis = openai_analyzer.analyze(
            text=extracted,
            task=document_task,
            matter_type=matter_type,
        )
        return AnalysisResponse(analysis=analysis, matter_id=matter_id)

    result = document_workflow.process(
        file.filename or "document",
        extracted,
        document_task,
        matter_type,
    )
    matched_matter_id = result.match.matter_id if result.match else matter_id
    return AnalysisResponse(analysis=result.analysis, matter_id=matched_matter_id)


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
