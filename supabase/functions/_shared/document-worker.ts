export type SourceChunk = {
  id: string;
  chunk_index: number;
  source_page: number | null;
};

export type NormalizedCitation = {
  claim: string;
  page: number;
  chunk_index: number;
  source_chunk_id: string;
};

export type FetchWithRetryOptions = {
  maxAttempts: number;
  timeoutMs: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  random?: () => number;
  requestIdPrefix?: string;
  stage?: string;
  logger?: (event: OpenAIRequestLog) => void;
  sleep?: (milliseconds: number) => Promise<void>;
};

export type OpenAIRequestLog = {
  event: "openai_request";
  request_id: string;
  stage: string;
  attempt: number;
  http_status: number | null;
  latency_ms: number;
  error_category: string;
};

const MODEL_NAME = /^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$/;
const SIGNIFICANT_FIELDS = [
  "persons",
  "dates",
  "case_numbers",
  "statutes",
  "monetary_amounts",
  "procedural_events",
  "contradictions",
  "risks",
];

export function configuredModel(envName: string, fallback: string): string {
  const configured = Deno.env.get(envName)?.trim();
  return configured && MODEL_NAME.test(configured) ? configured : fallback;
}

export function configuredInteger(
  envName: string,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  const value = Number(Deno.env.get(envName));
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    return fallback;
  }
  return value;
}

export function clampConfidence(value: unknown): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.max(0, Math.min(1, numeric)) : 0;
}

export function isRetryableStatus(status: number): boolean {
  return status === 408 || status === 409 || status === 429 ||
    (status >= 500 && status <= 599);
}

export function isTransientRequestFailure(value: unknown): boolean {
  const message = String(value);
  return message.includes("request_timeout") ||
    message.includes("request_network_error") ||
    /(?:file_upload|responses|embedding_api|analysis_api):(408|409|429|5\d\d):/
      .test(message);
}

export function pipelineFailureDisposition(
  value: unknown,
  attempts: number,
  maxRetryAttempts: number,
): "queued" | "failed" | "manual_review" {
  const message = String(value);
  if (message.includes("manual_review")) return "manual_review";
  if (
    isTransientRequestFailure(message) &&
    attempts < Math.max(1, maxRetryAttempts)
  ) return "queued";
  return "failed";
}

export function embeddingStageStatus(
  remainingChunks: number,
): "queued" | "completed" {
  return remainingChunks > 0 ? "queued" : "completed";
}

export function jobRetryDelayMs(attempts: number): number {
  const normalized = Number.isSafeInteger(attempts) && attempts > 0
    ? attempts
    : 1;
  const exponent = Math.max(0, Math.min(5, normalized - 1));
  return Math.min(120000, 5000 * 2 ** exponent);
}

function httpErrorCategory(status: number): string {
  if (status >= 200 && status <= 299) return "none";
  if (status === 408) return "http_timeout";
  if (status === 409) return "conflict";
  if (status === 429) return "rate_limit";
  if (status >= 500 && status <= 599) return "server_error";
  if (status === 400) return "invalid_request";
  if (status === 401 || status === 403) return "authentication";
  if (status === 404) return "not_found";
  return "permanent_http_error";
}

function emitRequestLog(
  options: FetchWithRetryOptions,
  event: OpenAIRequestLog,
): void {
  if (!options.stage || !options.requestIdPrefix) return;
  try {
    (options.logger ?? ((entry) => console.info(JSON.stringify(entry))))(event);
  } catch { /* observability must not change worker behavior */ }
}

function retryAfterMilliseconds(response: Response): number | null {
  const value = response.headers.get("retry-after")?.trim();
  if (!value) return null;

  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return seconds * 1000;

  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp)
    ? Math.max(0, timestamp - Date.now())
    : null;
}

async function defaultSleep(milliseconds: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function fetchWithRetry(
  request: (
    signal: AbortSignal,
    attempt: number,
    requestId: string,
  ) => Promise<Response>,
  options: FetchWithRetryOptions,
): Promise<Response> {
  const maxAttempts = Math.max(1, Math.min(10, options.maxAttempts));
  const timeoutMs = Math.max(1, options.timeoutMs);
  const baseDelayMs = Math.max(0, options.baseDelayMs ?? 500);
  const maxDelayMs = Math.max(baseDelayMs, options.maxDelayMs ?? 30000);
  const random = options.random ?? Math.random;
  const sleep = options.sleep ?? defaultSleep;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const controller = new AbortController();
    const requestId = options.requestIdPrefix
      ? `${options.requestIdPrefix}-${attempt}`
      : `local-${attempt}`;
    const startedAt = Date.now();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await request(controller.signal, attempt, requestId);
      emitRequestLog(options, {
        event: "openai_request",
        request_id: requestId,
        stage: options.stage ?? "unknown",
        attempt,
        http_status: response.status,
        latency_ms: Date.now() - startedAt,
        error_category: httpErrorCategory(response.status),
      });
      if (!isRetryableStatus(response.status) || attempt === maxAttempts) {
        return response;
      }

      const retryAfter = retryAfterMilliseconds(response) ?? 0;
      const exponential = baseDelayMs * 2 ** (attempt - 1);
      const jittered = exponential *
        (0.75 + Math.max(0, Math.min(1, random())) * 0.5);
      const delay = Math.round(
        Math.min(maxDelayMs, Math.max(retryAfter, jittered)),
      );
      try {
        await response.body?.cancel();
      } catch { /* response cleanup must not disable a retry */ }
      await sleep(delay);
    } catch (error) {
      const kind = controller.signal.aborted
        ? "request_timeout"
        : "request_network_error";
      emitRequestLog(options, {
        event: "openai_request",
        request_id: requestId,
        stage: options.stage ?? "unknown",
        attempt,
        http_status: null,
        latency_ms: Date.now() - startedAt,
        error_category: kind,
      });
      if (attempt === maxAttempts) {
        throw new Error(kind, { cause: error });
      }
      const exponential = baseDelayMs * 2 ** (attempt - 1);
      const jittered = exponential *
        (0.75 + Math.max(0, Math.min(1, random())) * 0.5);
      await sleep(Math.round(Math.min(maxDelayMs, jittered)));
    } finally {
      clearTimeout(timeoutId);
    }
  }

  throw new Error("request_retry_exhausted");
}

async function digest(value: string): Promise<Uint8Array> {
  const bytes = new TextEncoder().encode(value);
  return new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
}

export async function isAuthorizedWorker(
  req: Request,
  expectedSecret: string,
): Promise<boolean> {
  const supplied = req.headers.get("x-jafar-worker-secret") ?? "";
  if (!supplied || !expectedSecret) return false;

  const [left, right] = await Promise.all([
    digest(supplied),
    digest(expectedSecret),
  ]);
  let difference = 0;
  for (let index = 0; index < left.length; index++) {
    difference |= left[index] ^ right[index];
  }
  return difference === 0;
}

function integer(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isInteger(numeric) ? numeric : null;
}

export function normalizeCitations(
  citations: unknown,
  chunks: SourceChunk[],
): { citations: NormalizedCitation[]; invalidCount: number } {
  if (!Array.isArray(citations)) return { citations: [], invalidCount: 0 };

  const sources = new Map(
    chunks.map((chunk) => [`${chunk.source_page}:${chunk.chunk_index}`, chunk]),
  );
  const normalized: NormalizedCitation[] = [];
  const seen = new Set<string>();
  let invalidCount = 0;

  for (const value of citations) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      invalidCount++;
      continue;
    }
    const citation = value as Record<string, unknown>;
    const page = integer(citation.page ?? citation.source_page);
    const chunkIndex = integer(citation.chunk_index);
    const claim = typeof citation.claim === "string"
      ? citation.claim.trim()
      : "";
    const source =
      page === null || page <= 0 || chunkIndex === null || chunkIndex < 0
        ? undefined
        : sources.get(`${page}:${chunkIndex}`);
    const requestedChunkId = typeof citation.source_chunk_id === "string"
      ? citation.source_chunk_id
      : typeof citation.chunk_id === "string"
      ? citation.chunk_id
      : null;

    if (
      !source || !claim ||
      (requestedChunkId !== null && requestedChunkId !== source.id)
    ) {
      invalidCount++;
      continue;
    }
    const citationKey = `${source.id}:${claim}`;
    if (seen.has(citationKey)) {
      invalidCount++;
      continue;
    }
    seen.add(citationKey);
    normalized.push({
      claim,
      page: page!,
      chunk_index: chunkIndex!,
      source_chunk_id: source.id,
    });
  }

  return { citations: normalized, invalidCount };
}

export function validateAnalysisResult(
  result: unknown,
  chunks: SourceChunk[],
): { valid: boolean; errors: string[]; citations: NormalizedCitation[] } {
  if (!result || typeof result !== "object" || Array.isArray(result)) {
    return { valid: false, errors: ["analysis_not_an_object"], citations: [] };
  }

  const record = result as Record<string, unknown>;
  const normalized = normalizeCitations(record.citations, chunks);
  const errors: string[] = [];
  const hasSummary = typeof record.summary === "string" &&
    record.summary.trim().length > 0;
  const significantFindingCount = (hasSummary ? 1 : 0) +
    SIGNIFICANT_FIELDS.reduce((count, field) => {
      const value = record[field];
      return count + (Array.isArray(value) ? value.length : 0);
    }, 0);
  const confidence = Number(record.confidence);

  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
    errors.push("invalid_confidence");
  }
  if (significantFindingCount > 0 && normalized.citations.length === 0) {
    errors.push("significant_findings_without_citations");
  } else if (normalized.citations.length === 0) {
    errors.push("missing_citations");
  } else if (normalized.citations.length < significantFindingCount) {
    errors.push("uncited_significant_findings");
  }
  if (normalized.invalidCount > 0) errors.push("invalid_citations");

  return {
    valid: errors.length === 0,
    errors,
    citations: normalized.citations,
  };
}

export function chunkPages(
  pages: Array<{ page_number: number; extracted_text: unknown }>,
  size = 3500,
  overlap = 350,
): Array<{ chunk_index: number; content: string; source_page: number }> {
  if (size <= 0 || overlap < 0 || overlap >= size) {
    throw new Error("invalid_chunk_configuration");
  }

  const rows: Array<
    { chunk_index: number; content: string; source_page: number }
  > = [];
  let chunkIndex = 0;
  for (const page of pages) {
    const text = String(page.extracted_text ?? "").replace(/\r\n/g, "\n")
      .trim();
    if (!text) continue;
    for (let start = 0; start < text.length;) {
      const end = Math.min(text.length, start + size);
      rows.push({
        chunk_index: chunkIndex++,
        content: text.slice(start, end),
        source_page: page.page_number,
      });
      if (end === text.length) break;
      start = end - overlap;
    }
  }
  return rows;
}
