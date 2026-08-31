from __future__ import annotations

import os

from supabase import create_client

from .memory_service import LongTermMemoryService
from .openai_legal_research import OpenAIEmbeddingProvider
from .supabase_memory_repository import SupabaseMemoryRepository


def build_memory_service_from_env() -> LongTermMemoryService | None:
    url = os.getenv("JAFAR_SUPABASE_URL", "").strip()
    service_role_key = os.getenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    owner_user_id = os.getenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not all((url, service_role_key, owner_user_id, openai_key)):
        return None
    client = create_client(url, service_role_key)
    return LongTermMemoryService(
        repository=SupabaseMemoryRepository(client=client, owner_user_id=owner_user_id),
        embeddings=OpenAIEmbeddingProvider(),
    )
