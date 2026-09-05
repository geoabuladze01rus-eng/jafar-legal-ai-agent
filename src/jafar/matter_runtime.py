from __future__ import annotations

import os

from supabase import create_client

from .api_auth import PROTECTED_ENVIRONMENTS, configured_environment
from .matter_repository import MatterRepository
from .matters import MatterStore
from .supabase_matter_repository import SupabaseMatterRepository


def build_matter_repository_from_env() -> MatterRepository:
    """Return persistent Supabase matter storage when deployment secrets are present.

    Development and tests keep the existing in-memory MatterStore fallback. Production
    deployments can share the same matter catalog across restarts and client devices by
    setting the server-side Supabase credentials and fixed owner id.
    """

    url = os.getenv("JAFAR_SUPABASE_URL", "").strip()
    service_role_key = os.getenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    owner_user_id = os.getenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", "").strip()

    configured = (url, service_role_key, owner_user_id)
    if not all(configured):
        if configured_environment() in PROTECTED_ENVIRONMENTS:
            raise RuntimeError(
                "Persistent matter storage is required in staging and production"
            )
        return MatterStore()

    client = create_client(url, service_role_key)
    return SupabaseMatterRepository(client=client, owner_user_id=owner_user_id)
