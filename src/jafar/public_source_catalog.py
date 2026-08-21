from __future__ import annotations

from .legal_entity_adapters import LegalEntitySourceRegistry, PublicUrlSourceAdapter


def build_public_source_registry() -> LegalEntitySourceRegistry:
    registry = LegalEntitySourceRegistry()
    # URL templates are deliberately conservative: they create navigation
    # targets only. Transport/auth/CAPTCHA handling belongs to a separate layer.
    registry.register(
        PublicUrlSourceAdapter(
            "kad",
            "https://kad.arbitr.ru/Search/CaseNumber?query={query}",
        )
    )
    registry.register(
        PublicUrlSourceAdapter(
            "open_web",
            "https://www.google.com/search?q={query}",
        )
    )
    return registry
