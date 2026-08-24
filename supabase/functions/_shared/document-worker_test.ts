import {
  chunkPages,
  clampConfidence,
  configuredModel,
  isAuthorizedWorker,
  validateAnalysisResult,
} from "./document-worker.ts";

function assert(
  condition: unknown,
  message = "assertion failed",
): asserts condition {
  if (!condition) throw new Error(message);
}

function assertEquals(actual: unknown, expected: unknown): void {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) throw new Error(`expected ${right}, got ${left}`);
}

Deno.test("worker auth uses only the dedicated header", async () => {
  const secret = "worker-secret";
  assert(
    await isAuthorizedWorker(
      new Request("https://example.test", {
        headers: { "x-jafar-worker-secret": secret },
      }),
      secret,
    ),
  );
  assert(
    !await isAuthorizedWorker(
      new Request("https://example.test", {
        headers: { apikey: secret },
      }),
      secret,
    ),
  );
});

Deno.test("invalid model configuration falls back to a confirmed model", () => {
  const name = "JAFAR_TEST_MODEL";
  const previous = Deno.env.get(name);
  try {
    Deno.env.set(name, "invalid model name");
    assertEquals(configuredModel(name, "gpt-5.6"), "gpt-5.6");
    Deno.env.set(name, "configured-model_1");
    assertEquals(configuredModel(name, "gpt-5.6"), "configured-model_1");
  } finally {
    if (previous === undefined) Deno.env.delete(name);
    else Deno.env.set(name, previous);
  }
});

Deno.test("confidence is finite and bounded", () => {
  assertEquals(clampConfidence("1.4"), 1);
  assertEquals(clampConfidence(-0.2), 0);
  assertEquals(clampConfidence("not-a-number"), 0);
});

Deno.test("significant analysis requires a valid source citation", () => {
  const chunks = [{ id: "chunk-7", source_page: 3, chunk_index: 7 }];
  const missing = validateAnalysisResult({
    summary: "A factual summary",
    citations: [],
  }, chunks);
  assert(!missing.valid);
  assert(missing.errors.includes("significant_findings_without_citations"));

  const invalid = validateAnalysisResult({
    summary: "A factual summary",
    citations: [{ claim: "Fact", page: 99, chunk_index: 7 }],
  }, chunks);
  assert(!invalid.valid);
  assert(invalid.errors.includes("invalid_citations"));

  const valid = validateAnalysisResult({
    summary: "A factual summary",
    citations: [{ claim: "Fact", page: 3, chunk_index: 7 }],
  }, chunks);
  assert(valid.valid);
  assertEquals(valid.citations, [{
    claim: "Fact",
    page: 3,
    chunk_index: 7,
    source_chunk_id: "chunk-7",
  }]);
});

Deno.test("chunking supports documents larger than one embedding batch", () => {
  const chunks = chunkPages([{
    page_number: 1,
    extracted_text: "x".repeat(3500 + 3150 * 101),
  }]);
  assert(chunks.length > 100);
  assertEquals(chunks[0].chunk_index, 0);
  assertEquals(chunks.at(-1)?.chunk_index, chunks.length - 1);
});
