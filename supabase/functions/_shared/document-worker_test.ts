import {
  chunkPages,
  clampConfidence,
  configuredModel,
  embeddingStageStatus,
  fetchWithRetry,
  isAuthorizedWorker,
  isTransientRequestFailure,
  jobRetryDelayMs,
  type OpenAIRequestLog,
  pipelineFailureDisposition,
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
  assert(
    !await isAuthorizedWorker(
      new Request("https://example.test", {
        headers: { "x-jafar-worker-secret": "wrong-secret" },
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
    confidence: 0.7,
    citations: [],
  }, chunks);
  assert(!missing.valid);
  assert(missing.errors.includes("significant_findings_without_citations"));

  const invalid = validateAnalysisResult({
    summary: "A factual summary",
    confidence: 0.7,
    citations: [{ claim: "Fact", page: 99, chunk_index: 7 }],
  }, chunks);
  assert(!invalid.valid);
  assert(invalid.errors.includes("invalid_citations"));

  const valid = validateAnalysisResult({
    summary: "A factual summary",
    confidence: 0.7,
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

Deno.test("250 chunks require three embedding batches before completion", () => {
  const chunks = chunkPages([{
    page_number: 1,
    extracted_text: "x".repeat(3500 + 3150 * 249),
  }]);
  assertEquals(chunks.length, 250);
  assertEquals(chunks[0].chunk_index, 0);
  assertEquals(chunks.at(-1)?.chunk_index, chunks.length - 1);

  let remaining = chunks.length;
  const batches: number[] = [];
  const statuses: string[] = [];
  while (remaining > 0) {
    const processed = Math.min(100, remaining);
    batches.push(processed);
    remaining -= processed;
    statuses.push(embeddingStageStatus(remaining));
  }
  assertEquals(batches, [100, 100, 50]);
  assertEquals(statuses, ["queued", "queued", "completed"]);
});

Deno.test("rate limits are retried before the request fails", async () => {
  let attempts = 0;
  const delays: number[] = [];
  const response = await fetchWithRetry(() => {
    attempts++;
    return Promise.resolve(
      attempts === 1
        ? new Response(null, {
          status: 429,
          headers: { "retry-after": "0" },
        })
        : new Response("ok", { status: 200 }),
    );
  }, {
    maxAttempts: 3,
    timeoutMs: 100,
    baseDelayMs: 5,
    random: () => 0.5,
    sleep: (milliseconds) => {
      delays.push(milliseconds);
      return Promise.resolve();
    },
  });

  assertEquals(response.status, 200);
  assertEquals(attempts, 2);
  assertEquals(delays, [5]);
  assert(isTransientRequestFailure("embedding_api:429:rate limited"));
});

Deno.test("timed out requests are aborted and retried", async () => {
  let attempts = 0;
  const response = await fetchWithRetry((signal) => {
    attempts++;
    if (attempts > 1) return Promise.resolve(new Response("ok"));

    return new Promise<Response>((_resolve, reject) => {
      signal.addEventListener(
        "abort",
        () => reject(new DOMException("timed out", "AbortError")),
        { once: true },
      );
    });
  }, {
    maxAttempts: 2,
    timeoutMs: 5,
    baseDelayMs: 0,
    sleep: () => Promise.resolve(),
  });

  assertEquals(response.status, 200);
  assertEquals(attempts, 2);
  assert(isTransientRequestFailure("Error: request_timeout"));
});

Deno.test("network errors and retryable HTTP statuses are retried", async () => {
  let networkAttempts = 0;
  const networkResponse = await fetchWithRetry(() => {
    networkAttempts++;
    return networkAttempts === 1
      ? Promise.reject(new TypeError("connection reset"))
      : Promise.resolve(new Response("ok"));
  }, {
    maxAttempts: 2,
    timeoutMs: 100,
    baseDelayMs: 0,
    sleep: () => Promise.resolve(),
  });
  assertEquals(networkResponse.status, 200);
  assertEquals(networkAttempts, 2);

  for (const status of [408, 409, 429, 500, 599]) {
    let attempts = 0;
    const response = await fetchWithRetry(() => {
      attempts++;
      return Promise.resolve(
        new Response(null, {
          status: attempts === 1 ? status : 200,
        }),
      );
    }, {
      maxAttempts: 2,
      timeoutMs: 100,
      baseDelayMs: 0,
      sleep: () => Promise.resolve(),
    });
    assertEquals(response.status, 200);
    assertEquals(attempts, 2);
  }
});

Deno.test("pipeline retry delay is exponential and capped", () => {
  assertEquals(jobRetryDelayMs(1), 5000);
  assertEquals(jobRetryDelayMs(2), 10000);
  assertEquals(jobRetryDelayMs(3), 20000);
  assertEquals(jobRetryDelayMs(99), 120000);
});

Deno.test("repeated rate limits requeue the pipeline job", async () => {
  let attempts = 0;
  const response = await fetchWithRetry(() => {
    attempts++;
    return Promise.resolve(new Response(null, { status: 429 }));
  }, {
    maxAttempts: 3,
    timeoutMs: 100,
    baseDelayMs: 0,
    random: () => 0.5,
    sleep: () => Promise.resolve(),
  });

  assertEquals(attempts, 3);
  assertEquals(response.status, 429);
  assertEquals(
    pipelineFailureDisposition("embedding_api:429:rate limited", 1, 3),
    "queued",
  );
  assertEquals(
    pipelineFailureDisposition("embedding_api:429:rate limited", 3, 3),
    "failed",
  );
});

Deno.test("repeated timeouts requeue the pipeline job", async () => {
  let attempts = 0;
  let failure = "";
  try {
    await fetchWithRetry((signal) => {
      attempts++;
      return new Promise<Response>((_resolve, reject) => {
        signal.addEventListener(
          "abort",
          () => reject(new DOMException("timed out", "AbortError")),
          { once: true },
        );
      });
    }, {
      maxAttempts: 2,
      timeoutMs: 5,
      baseDelayMs: 0,
      random: () => 0.5,
      sleep: () => Promise.resolve(),
    });
  } catch (error) {
    failure = String(error);
  }

  assertEquals(attempts, 2);
  assert(failure.includes("request_timeout"));
  assertEquals(pipelineFailureDisposition(failure, 1, 3), "queued");
});

Deno.test("permanent HTTP errors are not retried", async () => {
  for (const status of [400, 401, 403, 404]) {
    let attempts = 0;
    const response = await fetchWithRetry(() => {
      attempts++;
      return Promise.resolve(new Response(null, { status }));
    }, {
      maxAttempts: 3,
      timeoutMs: 100,
      sleep: () => Promise.resolve(),
    });

    assertEquals(attempts, 1);
    assertEquals(response.status, status);
  }
  assertEquals(
    pipelineFailureDisposition("analysis_api:400:bad request", 1, 3),
    "failed",
  );
});

Deno.test("exponential retry delay is bounded and jittered", async () => {
  let attempts = 0;
  const delays: number[] = [];
  const randomValues = [0, 1];
  await fetchWithRetry(() => {
    attempts++;
    return Promise.resolve(
      new Response(null, {
        status: attempts < 3 ? 500 : 200,
      }),
    );
  }, {
    maxAttempts: 3,
    timeoutMs: 100,
    baseDelayMs: 100,
    maxDelayMs: 220,
    random: () => randomValues.shift() ?? 0.5,
    sleep: (milliseconds) => {
      delays.push(milliseconds);
      return Promise.resolve();
    },
  });

  assertEquals(delays, [75, 220]);
});

Deno.test("request logs contain safe operational metadata only", async () => {
  const events: OpenAIRequestLog[] = [];
  await fetchWithRetry((_signal, _attempt, requestId) => {
    assertEquals(requestId, "job-7-analyze-1");
    return Promise.resolve(new Response(null, { status: 200 }));
  }, {
    maxAttempts: 1,
    timeoutMs: 100,
    requestIdPrefix: "job-7-analyze",
    stage: "analyze",
    logger: (event) => events.push(event),
  });

  assertEquals(events.length, 1);
  assertEquals(events[0].request_id, "job-7-analyze-1");
  assertEquals(events[0].stage, "analyze");
  assertEquals(events[0].attempt, 1);
  assertEquals(events[0].http_status, 200);
  assertEquals(events[0].error_category, "none");
  const serialized = JSON.stringify(events);
  assert(!serialized.includes("OPENAI_API_KEY"));
  assert(!serialized.includes("JAFAR_WORKER_SECRET"));
  assert(!serialized.includes("document text"));
});

Deno.test("analysis validation rejects incomplete factual provenance", () => {
  const chunks = [
    { id: "chunk-1", source_page: 1, chunk_index: 0 },
    { id: "chunk-2", source_page: 1, chunk_index: 1 },
  ];
  const incomplete = validateAnalysisResult({
    summary: "Summary",
    risks: ["Risk without its own citation"],
    confidence: 1.4,
    citations: [{ claim: "Summary", page: 1, chunk_index: 0 }],
  }, chunks);
  assert(!incomplete.valid);
  assert(incomplete.errors.includes("invalid_confidence"));
  assert(incomplete.errors.includes("uncited_significant_findings"));
  assertEquals(
    pipelineFailureDisposition("analysis_invalid_json", 1, 3),
    "failed",
  );
  assertEquals(
    pipelineFailureDisposition(
      "analysis_manual_review:missing_citations",
      1,
      3,
    ),
    "manual_review",
  );
});
