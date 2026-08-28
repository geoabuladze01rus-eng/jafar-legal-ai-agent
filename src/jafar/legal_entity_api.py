from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .legal_entity_intelligence import EntityQuery, LegalEntityIntelligence, SourceFinding
from .legal_entity_research import LegalEntityResearchService

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


def _entity_query(value: str, query_type: str) -> EntityQuery:
    try:
        return EntityQuery.infer(value) if query_type == "auto" else EntityQuery(value, query_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/research-plan")
def research_plan(request: EntityResearchRequest):
    query = _entity_query(request.query, request.query_type)
    return service.build_research_plan(query)


@router.post("/profile")
def entity_profile(request: EntityProfileRequest):
    query = _entity_query(request.query, request.query_type)
    findings = [SourceFinding(**finding.model_dump()) for finding in request.findings]
    profile = intelligence.build_profile(findings, trusted=False)
    profile.update({"query": query.value, "query_type": query.query_type})
    return profile
