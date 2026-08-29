from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hmac
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .action_approval import ActionRequest, ActionState, LegalActionApprovalEngine
from .ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from .command_runtime import JafarCommandRuntime
from .config import settings
from .cost_runtime import build_cost_runtime, validate_production_ai_scale
from .dashboard import DashboardService, DashboardSnapshot
from .document_intake import DocumentExtractionError, DocumentExtractor
from .document_workflow import DocumentWorkflow
from .domains import DocumentTask, MatterType
from .legal_analysis import LegalAnalyzer
from .legal_entity_api import router as legal_entity_router
from .legal_models import AnalysisRequest, AnalysisResponse, LegalAnalysis, Matter
from .rate_limit_runtime import RateLimiter, build_ai_rate_limiter
from .storage import build_runtime_repositories, validate_storage_security
from .structured_analysis_runtime import MeteredStructuredLegalAnalyzer
from .telegram_runtime import TelegramRuntime

telegram_runtime: TelegramRuntime | None = None
metered_openai_analyzer: MeteredStructuredLegalAnalyzer | None = None
ai_rate_limiter: RateLimiter | None = None
AI_RATE_LIMIT_PATHS = frozenset({"/v1/analyze", "/v1/documents/analyze"})


def production_api_key_is_secure() -> bool:
    api_key = (settings.api_key or "").strip()
    placeholders = {"replace-me", "changeme", "change-me", "secret"}
    return len(api_key) >= 24 and api_key.casefold() not in placeholders


def validate_runtime_security() -> None:
    if settings.environment.strip().casefold() != "production":
        return
    if not production_api_key_is_secure():
        raise RuntimeError(
            "Production requires a non-placeholder API_KEY of at least 24 characters"
        )
    if not (settings.lawyer_approver_id or "").strip():
        raise RuntimeError("Production requires LAWYER_APPROVER_ID for auditable decisions")
    validate_storage_security(settings)
    validate_production_ai_scale(settings)


def _approval_identity() -> str:
    configured = (settings.lawyer_approver_id or "").strip()
    if not configured:
        raise RuntimeError("LAWYER_APPROVER_ID is required to record approval decisions")
    return configured


def _ensure_metered_openai_runtime() -> MeteredStructuredLegalAnalyzer | None:
    global metered_openai_analyzer
    if openai_analyzer is None or not settings.ai_cost_control_enabled:
        return None
    if metered_openai_analyzer is not None:
        return metered_openai_analyzer

    cost_runtime = build_cost_runtime(settings)
    control = cost_runtime.control
    if control is None:
        raise RuntimeError("AI cost control unexpectedly unavailable")
    user_id = (settings.lawyer_approver_id or "local-development-user").strip()
    metered_openai_analyzer = MeteredStructuredLegalAnalyzer(
        analyzer=openai_analyzer,
        cost_control=control,
        user_id=user_id,
        reservations=cost_runtime.reservations,
    )
    return metered_openai_analyzer


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ai_rate_limiter, telegram_runtime
    validate_runtime_security()
    ai_rate_limiter = build_ai_rate_limiter(settings)
    if settings.ai_cost_control_enabled and openai_analyzer is not None:
        _ensure_metered_openai_runtime()
    if settings.telegram_polling_enabled and settings.telegram_bot_token:
        telegram_runtime = TelegramRuntime(
            settings.telegram_bot_token,
            production_send=settings.telegram_production_send,
        )
        telegram_runtime.start()
    try:
        yield
    finally:
        ai_rate_limiter = None
        if telegram_runtime is not None:
            await telegram_runtime.stop()
            telegram_runtime = None


app = FastAPI(title=settings.app_name, version="0.9.12", lifespan=lifespan)
app.include_router(legal_entity_router)
heuristic_analyzer = LegalAnalyzer()
openai_analyzer = (
    OpenAILegalAnalyzer(
        config=AIProviderConfig(max_retries=0 if settings.ai_cost_control_enabled else 2)
    )
    if settings.openai_api_key
    else None
)
runtime_repositories = build_runtime_repositories(settings)
matter_store = runtime_repositories.matters
action_approval_store = runtime_repositories.approvals
document_extractor = DocumentExtractor()
document_workflow = DocumentWorkflow(matter_store, heuristic_analyzer)
command_runtime = JafarCommandRuntime(matter_store)
dashboard_service = DashboardService(matter_store)
action_approval_engine = LegalActionApprovalEngine(action_approval_store)


def _analyze(request: AnalysisRequest) -> LegalAnalysis:
    if openai_analyzer is not None:
        if settings.ai_cost_control_enabled:
            runtime = _ensure_metered_openai_runtime()
            if runtime is None:
                raise RuntimeError("Metered OpenAI runtime is required when cost control is enabled")
            return runtime.analyze(request)
        if settings.environment.strip().casefold() == "production":
            raise RuntimeError("Production OpenAI analysis cannot bypass AI cost control")
        return openai_analyzer.analyze(
            text=request.text,
            task=request.task,
            matter_type=request.matter_type,
        )
    return heuristic_analyzer.analyze(
        request.text,
        request.task,
        request.matter_type,
    )


@app.middleware("http")
async def protect_v1_api(request: Request, call_next):
    if request.url.path.startswith("/v1"):
        production = settings.environment.strip().casefold() == "production"
        if production and not production_api_key_is_secure():
            return JSONResponse(
                status_code=503,
                content={"detail": "Production API authentication is not securely configured"},
            )
        if settings.api_key:
            supplied = request.headers.get("Authorization", "")
            expected = f"Bearer {settings.api_key}"
            if not hmac.compare_digest(supplied, expected):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        if request.url.path in AI_RATE_LIMIT_PATHS:
            limiter = ai_rate_limiter
            if production and limiter is None:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Production AI rate limiting is unavailable"},
                )
            if limiter is not None:
                try:
                    allowed = limiter.allow(request.url.path)
                except Exception:
                    # A broken distributed limiter must fail closed rather than silently allowing
                    # an unbounded model-spend path during a Supabase/network incident.
                    return JSONResponse(
                        status_code=503,
                        content={"detail": "AI rate-limit safety service unavailable"},
                    )
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "AI request rate limit exceeded"},
                        headers={"Retry-After": str(settings.ai_rate_limit_window_seconds)},
                    )
    return await call_next(request)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = Field(default=settings.app_name)


class CreateMatterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    matter_type: MatterType = MatterType.GENERAL
    client_name: str | None = None
    opposing_party: str | None = None
    court_or_authority: str | None = None
    case_number: str | None = None


class CommandRequest(BaseModel):
    """Untrusted client command envelope.

    Approval is deliberately absent: a client cannot promote its own request across the
    human-approval boundary. Mutating actions must enter the approval repository and be
    decided through the dedicated approval endpoints.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    user_id: str = Field(min_length=1, max_length=200)
    source_device: str = Field(min_length=1, max_length=100)


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
    payload_bound: bool = False
    created_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    execution_claimed_at: str | None = None
    execution_claimed_by: str | None = None
    execution_error: str | None = None
    executed_at: str | None = None


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
        payload_bound=bool(request.payload_hash),
        created_at=request.created_at,
        decided_at=request.decided_at,
        decided_by=request.decided_by,
        decision_reason=request.decision_reason,
        execution_claimed_at=request.execution_claimed_at,
        execution_claimed_by=request.execution_claimed_by,
        execution_error=request.execution_error,
        executed_at=request.executed_at,
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/v1/matters", response_model=Matter)
def create_matter(request: CreateMatterRequest) -> Matter:
    matter = Matter(
        id=str(uuid4()),
        title=request.title,
        matter_type=request.matter_type,
        client_name=request.client_name,
        opposing_party=request.opposing_party,
        court_or_authority=request.court_or_authority,
        case_number=request.case_number,
    )
    return matter_store.create_matter(matter)


@app.get("/v1/matters", response_model=list[Matter])
def list_matters() -> list[Matter]:
    return matter_store.list_matters()


@app.get("/v1/dashboard", response_model=DashboardSnapshot)
def dashboard() -> DashboardSnapshot:
    return dashboard_service.snapshot()


@app.post("/v1/command", response_model=CommandResponse)
def command(request: CommandRequest) -> CommandResponse:
    result = command_runtime.execute(request.text)
    return CommandResponse(
        message=result.message,
        intent=result.intent,
        approval_required=result.approval_required,
        request_id=result.request_id,
        data=result.data,
    )


@app.get("/v1/approvals", response_model=list[ApprovalItemResponse])
def approvals() -> list[ApprovalItemResponse]:
    return [_approval_item(item) for item in action_approval_store.list_all()]


@app.post("/v1/approvals/{action_id}/approve", response_model=ApprovalDecisionResponse)
def approve_action(action_id: str, request: ApprovalDecisionRequest) -> ApprovalDecisionResponse:
    decided_by = _approval_identity()
    try:
        item = action_approval_engine.approve(
            action_id,
            decided_by=decided_by,
            reason=request.reason,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApprovalDecisionResponse(
        action_id=item.action_id,
        state=item.state,
        decided_by=item.decided_by or decided_by,
        decided_at=item.decided_at or datetime.now(timezone.utc).isoformat(),
        reason=item.decision_reason,
    )


@app.post("/v1/approvals/{action_id}/reject", response_model=ApprovalDecisionResponse)
def reject_action(action_id: str, request: ApprovalDecisionRequest) -> ApprovalDecisionResponse:
    decided_by = _approval_identity()
    try:
        item = action_approval_engine.reject(
            action_id,
            decided_by=decided_by,
            reason=request.reason,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApprovalDecisionResponse(
        action_id=item.action_id,
        state=item.state,
        decided_by=item.decided_by or decided_by,
        decided_at=item.decided_at or datetime.now(timezone.utc).isoformat(),
        reason=item.decision_reason,
    )


@app.post("/v1/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    if request.matter_id:
        try:
            matter_store.get_matter(request.matter_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Matter not found") from exc
    return AnalysisResponse(
        analysis=_analyze(request),
        matter_id=request.matter_id,
        persisted=False,
        requires_approval_to_persist=True,
    )


@app.post("/v1/documents/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    matter_id: str | None = None,
    task: DocumentTask = DocumentTask.LEGAL_ANALYSIS,
):
    if matter_id:
        try:
            matter_store.get_matter(matter_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Matter not found") from exc

    try:
        document = await document_extractor.extract_upload(file)
        result = document_workflow.analyze_document(document, matter_id=matter_id, task=task)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "document": document.model_dump(),
        "analysis": result.analysis.model_dump(),
        "event": None,
        "persisted": False,
        "requires_approval_to_persist": True,
    }
