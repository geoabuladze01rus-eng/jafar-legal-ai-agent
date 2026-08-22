import pytest

from jafar.telegram_dry_run_guard import (
    ProductionPublicationDisabled,
    production_publication_enabled,
    require_production_publication_enabled,
)


def test_production_publication_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PRODUCTION_ENABLED", raising=False)
    assert production_publication_enabled() is False
    with pytest.raises(ProductionPublicationDisabled):
        require_production_publication_enabled()


def test_production_publication_requires_explicit_true(monkeypatch):
    monkeypatch.setenv("TELEGRAM_PRODUCTION_ENABLED", "true")
    assert production_publication_enabled() is True
    require_production_publication_enabled()
