from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from .legal_entity_intelligence import LegalEntityIntelligence, SourceFinding
from .legal_entity_research import EntityQuery, LegalEntityResearchService

router = APIRouter(prefix="/v1/legal-entities", tags=["legal-entities"])
service = LegalEntityResearchService()
intelligence = LegalEntityIntelligence()


class EntityResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    query_type: str = Field(default="auto", pattern="^(auto|name|inn|ogrn|kpp)$")


class SourceFindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(min_length=1, max_length=100)
    status: str = Field(pattern="^(found|negative|no_data|error)$")
    title: str = Field(min_length=1, max_length=500)
    details: dict = Field(default_factory=dict, max_length=100)
    source_url: str | None = Field(default=None, max_length=2048)


class EntityProfileRequest(EntityResearchRequest):
    findings: list[SourceFindingRequest] = Field(default_factory=list, max_length=100)


@router.post("/research-plan")
def research_plan(request: EntityResearchRequest):
    query_type = request.query_type
    if query_type == "auto":
        digits = "".join(ch for ch in request.query if ch.isdigit())
        query_type = "inn" if len(digits) == 10 else "ogrn" if len(digits) == 13 else "name"
    return service.build_research_plan(EntityQuery(request.query, query_type))


@router.post("/profile")
def entity_profile(request: EntityProfileRequest):
    query_type = request.query_type
    if query_type == "auto":
        digits = "".join(ch for ch in request.query if ch.isdigit())
        query_type = "inn" if len(digits) == 10 else "ogrn" if len(digits) == 13 else "name"

    findings = [SourceFinding(**finding.model_dump()) for finding in request.findings]
    profile = intelligence.build_profile(findings, trusted=False)
    profile.update({"query": request.query, "query_type": query_type})
    return profile
