from jafar.matter_runtime import build_matter_repository_from_env
from jafar.matters import MatterStore


def test_matter_runtime_falls_back_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("JAFAR_SUPABASE_URL", raising=False)
    monkeypatch.delenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", raising=False)

    repository = build_matter_repository_from_env()

    assert isinstance(repository, MatterStore)
