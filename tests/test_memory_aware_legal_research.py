from datetime import datetime, timezone
from types import SimpleNamespace

from jafar.matter_rag import MatterChunk, MatterRAGContext, RetrievedChunk
from jafar.memory_models import MemoryKind, MemoryRecord, MemorySearchResult
from jafar.openai_legal_research import OpenAIResearchAnswerProvider


class FakeMemoryService:
    def recall(self, query, *, matter_id=None, limit=8, min_similarity=0.0):
        memory = MemoryRecord(
            id="mem-42",
            owner_user_id="owner-1",
            kind=MemoryKind.DECISION,
            content="Решили не делать вывод без текста апелляционного определения.",
            matter_id=matter_id,
            created_at=datetime.now(timezone.utc),
        )
        return [MemorySearchResult(memory=memory, similarity=0.88)]


class FakeResponses:
    def __init__(self):
        self.last_input = None

    def create(self, *, model, input):
        self.last_input = input
        return SimpleNamespace(output_text="Ответ [document:doc-1:page:2:chunk:0]")


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_legal_research_prompt_includes_memory_as_non_evidence_context():
    client = FakeClient()
    provider = OpenAIResearchAnswerProvider(client=client, memory_service=FakeMemoryService())
    chunk = MatterChunk(
        chunk_id="chunk-1",
        matter_id="matter-1",
        document_id="doc-1",
        source_page=2,
        chunk_index=0,
        content="Суд указал на необходимость дополнительной проверки.",
    )
    context = MatterRAGContext(
        matter_id="matter-1",
        query="Что делать дальше?",
        results=(RetrievedChunk(chunk=chunk, score=0.9),),
    )

    answer = provider.answer(question="Что делать дальше?", context=context)

    assert "document:doc-1:page:2:chunk:0" in answer
    user_prompt = client.responses.last_input[1]["content"]
    assert "LONG-TERM MEMORY" in user_prompt
    assert "memory:mem-42" in user_prompt
    system_prompt = client.responses.last_input[0]["content"]
    assert "never treat memory as documentary evidence" in system_prompt
