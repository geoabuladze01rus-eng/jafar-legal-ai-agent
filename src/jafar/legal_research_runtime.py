from __future__ import annotations

import os

from supabase import create_client

from .legal_research_service import LegalResearchService
from .openai_legal_research import OpenAIEmbeddingProvider, OpenAIResearchAnswerProvider
from .supabase_matter_rag import SupabaseMatterRAG


def build_legal_research_service_from_env() -> LegalResearchService | None:
    """Build the single-user production research service from environment secrets.

    The service-role key is used only by the server-side API. The owner id is fixed
    by deployment configuration so callers cannot select another owner's matter.
    """

    url = os.getenv("JAFAR_SUPABASE_URL", "").strip()
    service_role_key = os.getenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    owner_user_id = os.getenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not all((url, service_role_key, owner_user_id, openai_key)):
        return None

    client = create_client(url, service_role_key)
    return LegalResearchService(
        embeddings=OpenAIEmbeddingProvider(),
        retrieval=SupabaseMatterRAG(client=client, owner_user_id=owner_user_id),
        answers=OpenAIResearchAnswerProvider(),
    )
