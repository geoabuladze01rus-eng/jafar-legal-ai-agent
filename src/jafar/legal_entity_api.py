from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .legal_entity_research import EntityQuery, LegalEntityResearchService

router = APIRouter(prefix="/v1/legal-entities", tags=["legal-entities"])
service = LegalEntityResearchService()


class EntityResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    query_type: str = Field(default="auto", pattern="^(auto|name|inn|ogrn|kpp)$")


@router.post("/research-plan")
def research_plan(request: EntityResearchRequest):
    query_type = request.query_type
    if query_type == "auto":
        digits = "".join(ch for ch in request.query if ch.isdigit())
        query_type = "inn" if len(digits) == 10 else "ogrn" if len(digits) == 13 else "name"
    return service.build_research_plan(EntityQuery(request.query, query_type))
