from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import settings
from .domains import MatterType
from .legal_analysis import LegalAnalyzer
from .legal_models import AnalysisRequest, AnalysisResponse, Matter
from .matters import MatterStore
from .model_provider import OpenAICompatibleProvider

app = FastAPI(title=settings.app_name, version="0.3.0")

model_provider = None
if settings.api_key and settings.model_provider.lower() in {"openai", "openai-compatible"}:
    model_provider = OpenAICompatibleProvider(
        api_key=settings.api_key,
        model=settings.model_name,
        base_url=settings.model_base_url,
        timeout_seconds=settings.model_timeout_seconds,
    )

analyzer = LegalAnalyzer(provider=model_provider)
matter_store = MatterStore()


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = Field(default=settings.app_name)
    model_provider: str = Field(default=settings.model_provider)
    model_configured: bool = False


class CreateMatterRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    matter_type: MatterType = MatterType.GENERAL
    client_name: str | None = None
    opposing_party: str | None = None
    court_or_authority: str | None = None
    case_number: str | None = None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(model_configured=model_provider is not None)


@app.post("/v1/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    analysis = analyzer.analyze(request.text, request.task, request.matter_type)
    if request.matter_id:
        matter = matter_store.get(request.matter_id)
        if matter is None:
            raise HTTPException(status_code=404, detail="Matter not found")
        matter_store.add_deadlines(request.matter_id, analysis.deadlines)
    return AnalysisResponse(analysis=analysis, matter_id=request.matter_id)


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
