from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import settings

app = FastAPI(title=settings.app_name, version="0.1.0")


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = Field(default=settings.app_name)


class AnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    task: str = "legal_analysis"


class AnalysisResponse(BaseModel):
    task: str
    status: str = "queued"
    message: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/v1/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    # Model execution is intentionally isolated behind this API boundary.
    # Credentials and provider-specific clients will be added in the next layer.
    return AnalysisResponse(
        task=request.task,
        message="Analysis pipeline is ready for model-provider integration.",
    )
