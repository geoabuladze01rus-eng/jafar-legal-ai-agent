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
  const hasSignificantFindings = hasSummary ||
    SIGNIFICANT_FIELDS.some((field) => {
      const value = record[field];
      return Array.isArray(value) && value.length > 0;
    });

  if (hasSignificantFindings && normalized.citations.length === 0) {
    errors.push("significant_findings_without_citations");
  } else if (normalized.citations.length === 0) {
    errors.push("missing_citations");
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
