from __future__ import annotations

from datetime import datetime
import os

from .google_oauth import GoogleTokenSet, GoogleTokenStore


class SupabaseGoogleTokenStore(GoogleTokenStore):
    def __init__(self, client, encryption_key: str) -> None:
        if not encryption_key:
            raise ValueError("Google token encryption key is required")
        self.client = client
        self.encryption_key = encryption_key

    def load(self, subject: str) -> GoogleTokenSet | None:
        response = self.client.rpc(
            "load_google_oauth_token",
            {"p_subject": subject, "p_encryption_key": self.encryption_key},
        ).execute()
        rows = response.data or []
        if not rows:
            return None
        row = rows[0]
        return GoogleTokenSet(
            access_token=str(row["access_token"]),
            refresh_token=str(row["refresh_token"]) if row.get("refresh_token") else None,
            expires_at=datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00")),
            scope=str(row["scope"]) if row.get("scope") else None,
            token_type=str(row.get("token_type") or "Bearer"),
        )

    def save(self, subject: str, token_set: GoogleTokenSet) -> None:
        self.client.rpc(
            "upsert_google_oauth_token",
            {
                "p_subject": subject,
                "p_access_token": token_set.access_token,
                "p_refresh_token": token_set.refresh_token,
                "p_expires_at": token_set.expires_at.isoformat(),
                "p_scope": token_set.scope,
                "p_token_type": token_set.token_type,
                "p_encryption_key": self.encryption_key,
            },
        ).execute()


def build_google_token_store_from_env() -> GoogleTokenStore:
    url = os.getenv("JAFAR_SUPABASE_URL", "").strip()
    service_key = os.getenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    encryption_key = os.getenv("JAFAR_GOOGLE_TOKEN_ENCRYPTION_KEY", "").strip()
    if url and service_key and encryption_key:
        from supabase import create_client

        return SupabaseGoogleTokenStore(create_client(url, service_key), encryption_key)

    from .google_oauth import InMemoryGoogleTokenStore

    return InMemoryGoogleTokenStore()
