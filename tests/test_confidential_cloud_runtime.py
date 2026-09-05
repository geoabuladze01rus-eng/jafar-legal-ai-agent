from __future__ import annotations

import pytest

import jafar.analysis_service as analysis_runtime
import jafar.legal_research_runtime as research_runtime
import jafar.memory_runtime as memory_runtime


def configure_cloud_runtime(monkeypatch, *, enabled: bool) -> None:
    monkeypatch.setenv("CONFIDENTIAL_CLOUD_FALLBACK", "true" if enabled else "false")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("JAFAR_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "synthetic-service-key")
    monkeypatch.setenv("JAFAR_LEGAL_RESEARCH_OWNER_USER_ID", "owner-test")


def test_openai_backed_runtimes_are_disabled_without_cloud_opt_in(monkeypatch) -> None:
    configure_cloud_runtime(monkeypatch, enabled=False)

    monkeypatch.setattr(
        research_runtime,
        "create_client",
        lambda *_: pytest.fail("Supabase client must not be created"),
    )
    monkeypatch.setattr(
        memory_runtime,
        "create_client",
        lambda *_: pytest.fail("Supabase client must not be created"),
    )

    assert research_runtime.build_legal_research_service_from_env() is None
    assert memory_runtime.build_memory_service_from_env() is None
    with pytest.raises(RuntimeError, match="Confidential cloud processing is not enabled"):
        analysis_runtime.LegalAnalysisService.from_environment()


def test_openai_backed_runtimes_can_be_explicitly_enabled(monkeypatch) -> None:
    configure_cloud_runtime(monkeypatch, enabled=True)
    client = object()
    embedding = object()
    answer = object()

    monkeypatch.setattr(research_runtime, "create_client", lambda *_: client)
    monkeypatch.setattr(research_runtime, "OpenAIEmbeddingProvider", lambda: embedding)
    monkeypatch.setattr(research_runtime, "OpenAIResearchAnswerProvider", lambda **_: answer)
    monkeypatch.setattr(research_runtime, "build_memory_service_from_env", lambda: None)
    monkeypatch.setattr(memory_runtime, "create_client", lambda *_: client)
    monkeypatch.setattr(memory_runtime, "OpenAIEmbeddingProvider", lambda: embedding)

    research = research_runtime.build_legal_research_service_from_env()
    memory = memory_runtime.build_memory_service_from_env()

    assert research is not None
    assert research.embeddings is embedding
    assert research.answers is answer
    assert memory is not None
    assert memory.embeddings is embedding


def test_analysis_runtime_can_be_explicitly_enabled(monkeypatch) -> None:
    configure_cloud_runtime(monkeypatch, enabled=True)

    class FakeOpenAIProvider:
        key = "openai"

        def __init__(self, *, config) -> None:
            self.config = config

        def available(self) -> bool:
            return True

    monkeypatch.setattr(analysis_runtime, "OpenAILegalAnalyzer", FakeOpenAIProvider)

    service = analysis_runtime.LegalAnalysisService.from_environment()

    assert service.router.providers["openai"].config.model
