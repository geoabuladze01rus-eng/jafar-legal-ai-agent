import { createClient } from "npm:@supabase/supabase-js@2.112.3";
import {
  chunkPages,
  clampConfidence,
  configuredInteger,
  configuredModel,
  embeddingStageStatus,
  fetchWithRetry,
  isAuthorizedWorker,
  jobRetryDelayMs,
  pipelineFailureDisposition,
  type SourceChunk,
  validateAnalysisResult,
} from "../_shared/document-worker.ts";

const ANALYSIS_MODEL = configuredModel("JAFAR_ANALYSIS_MODEL", "gpt-5.6");
const EMBEDDING_MODEL = configuredModel(
  "JAFAR_EMBEDDING_MODEL",
  "text-embedding-3-small",
);
const EMBEDDING_BATCH_SIZE = configuredInteger(
  "JAFAR_EMBEDDING_BATCH_SIZE",
  100,
  1,
  100,
);
const ANALYSIS_MAX_CONTEXT_CHARS = configuredInteger(
  "JAFAR_ANALYSIS_MAX_CONTEXT_CHARS",
  700000,
  10000,
  2000000,
);
const DEFAULT_PIPELINE_MAX_RETRIES = configuredInteger(
  "JAFAR_PIPELINE_MAX_RETRIES",
  3,
  1,
  20,
);
const OPENAI_MAX_ATTEMPTS = configuredInteger(
  "JAFAR_OPENAI_MAX_ATTEMPTS",
  3,
  1,
  10,
);
const OPENAI_TIMEOUT_MS = configuredInteger(
  "JAFAR_OPENAI_TIMEOUT_MS",
  90000,
  1000,
  600000,
);
const CHUNK_WRITE_BATCH_SIZE = 200;
const CHUNK_READ_PAGE_SIZE = 500;

type PageRow = {
  page_number: number;
  extracted_text: unknown;
  status: string;
};

type PipelineChunk = SourceChunk & { content: string };
type EmbeddingResponse = {
  data?: Array<{ index?: number; embedding?: number[] }>;
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

function configuredServiceKey(): string | undefined {
  try {
    const configured = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
    const defaultKey = configured.default;
    if (typeof defaultKey === "string" && defaultKey) return defaultKey;
  } catch { /* legacy fallback below */ }
  return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || undefined;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const workerSecret = Deno.env.get("JAFAR_WORKER_SECRET")?.trim();
  if (!workerSecret) {
    return json({ error: "worker_secret_not_configured" }, 503);
  }
  if (!await isAuthorizedWorker(req, workerSecret)) {
    return json({ error: "unauthorized_worker" }, 401);
  }

  const url = Deno.env.get("SUPABASE_URL");
  const service = configuredServiceKey();
  const key = Deno.env.get("OPENAI_API_KEY");
  if (!url || !service || !key) {
    return json({ error: "server_not_configured" }, 503);
  }

  const db = createClient(url, service);
  const readAllChunks = async (
    documentId: string,
  ): Promise<PipelineChunk[]> => {
    const chunks: PipelineChunk[] = [];
    for (let offset = 0;; offset += CHUNK_READ_PAGE_SIZE) {
      const { data, error } = await db.from("document_chunks")
        .select("id,chunk_index,source_page,content")
        .eq("document_id", documentId)
        .order("chunk_index")
        .range(offset, offset + CHUNK_READ_PAGE_SIZE - 1);
      if (error) throw new Error(`analysis_context_failed:${error.message}`);
      const page = (data ?? []) as PipelineChunk[];
      chunks.push(...page);
      if (page.length < CHUNK_READ_PAGE_SIZE) return chunks;
    }
  };
  const workerId = crypto.randomUUID();
  const { data: jobs, error: claimError } = await db.rpc(
    "claim_document_pipeline_job",
    {
      p_worker_id: workerId,
      p_lease_seconds: 600,
    },
  );
  if (claimError) {
    return json({ error: "claim_failed", detail: claimError.message }, 500);
  }

  const job = jobs?.[0];
  if (!job) return json({ ok: true, status: "idle" });
  const requestTrace = `${job.id}-${job.stage}-${crypto.randomUUID()}`;
  let pipelineMaxRetries = DEFAULT_PIPELINE_MAX_RETRIES;

  const finish = async (
    status: "queued" | "completed" | "failed" | "manual_review",
    error: string | null = null,
    availableAt: string | null = null,
  ) => {
    const parameters: Record<string, unknown> = {
      p_job_id: job.id,
      p_document_id: job.document_id,
      p_worker_id: workerId,
      p_error: error?.slice(0, 2000) ?? null,
    };
    if (availableAt) {
      parameters.p_available_at = availableAt;
    } else {
      parameters.p_status = status;
    }
    const { error: finishError } = await db.rpc(
      availableAt
        ? "retry_document_pipeline_job"
        : "finish_document_pipeline_job",
      parameters,
    );
    if (finishError) {
      throw new Error(`pipeline_finish_failed:${finishError.message}`);
    }
  };

  const heartbeat = async () => {
    await db.from("worker_heartbeats").upsert({
      worker_name: "document-pipeline-worker",
      last_seen_at: new Date().toISOString(),
      status: "active",
      updated_at: new Date().toISOString(),
    });
  };

  try {
    const { data: doc, error: docError } = await db.from("documents")
      .select(
        "id,matter_id,filename,processing_status,manual_review_required,max_retry_attempts",
      )
      .eq("id", job.document_id)
      .maybeSingle();
    if (docError || !doc) throw new Error("document_not_found");
    pipelineMaxRetries = Number.isSafeInteger(Number(doc.max_retry_attempts))
      ? Math.max(1, Number(doc.max_retry_attempts))
      : DEFAULT_PIPELINE_MAX_RETRIES;
    if (
      doc.manual_review_required || doc.processing_status === "manual_review"
    ) {
      throw new Error("ocr_manual_review_required");
    }

    if (job.stage === "chunk") {
      const { data: pages, error } = await db.from("document_pages")
        .select("page_number,extracted_text,ocr_confidence,status")
        .eq("document_id", doc.id)
        .order("page_number");
      if (error) throw new Error(`page_read_failed:${error.message}`);
      if (!pages?.length) throw new Error("no_pages");
      const pageRows = (pages ?? []) as PageRow[];
      if (pageRows.some((page) => page.status !== "completed")) {
        throw new Error("ocr_manual_review_required");
      }

      const chunks = chunkPages(pageRows).map((chunk) => ({
        document_id: doc.id,
        ...chunk,
      }));
      if (!chunks.length) throw new Error("empty_document_text");

      const { error: deleteError } = await db.from("document_chunks")
        .delete()
        .eq("document_id", doc.id);
      if (deleteError) {
        throw new Error(`chunk_replace_failed:${deleteError.message}`);
      }
      for (
        let start = 0;
        start < chunks.length;
        start += CHUNK_WRITE_BATCH_SIZE
      ) {
        const { error: insertError } = await db.from("document_chunks")
          .insert(chunks.slice(start, start + CHUNK_WRITE_BATCH_SIZE));
        if (insertError) {
          throw new Error(`chunk_persist_failed:${insertError.message}`);
        }
      }
    } else if (job.stage === "embed") {
      const { data: chunks, error } = await db.from("document_chunks")
        .select("id,content")
        .eq("document_id", doc.id)
        .is("embedding", null)
        .order("chunk_index")
        .limit(EMBEDDING_BATCH_SIZE);
      if (error) throw new Error(`chunk_read_failed:${error.message}`);

      const pendingChunks = (chunks ?? []) as Array<
        { id: string; content: string }
      >;
      if (pendingChunks.length) {
        const response = await fetchWithRetry(
          (signal, _attempt, requestId) => {
            return fetch("https://api.openai.com/v1/embeddings", {
              method: "POST",
              headers: {
                authorization: `Bearer ${key}`,
                "content-type": "application/json",
                "x-client-request-id": requestId,
              },
              body: JSON.stringify({
                model: EMBEDDING_MODEL,
                input: pendingChunks.map((chunk) => chunk.content),
              }),
              signal,
            });
          },
          {
            maxAttempts: OPENAI_MAX_ATTEMPTS,
            timeoutMs: OPENAI_TIMEOUT_MS,
            stage: "embed",
            requestIdPrefix: `${requestTrace}-embedding`,
          },
        );
        if (!response.ok) {
          throw new Error(
            `embedding_api:${response.status}:${
              (await response.text()).slice(0, 800)
            }`,
          );
        }
        const output = await response.json() as EmbeddingResponse;
        for (let index = 0; index < pendingChunks.length; index++) {
          const embedding = output.data?.find((item) =>
            item.index === index
          )?.embedding ??
            output.data?.[index]?.embedding;
          if (!embedding) throw new Error(`embedding_missing:${index}`);
          const { error: updateError } = await db.from("document_chunks")
            .update({ embedding })
            .eq("id", pendingChunks[index].id)
            .is("embedding", null);
          if (updateError) {
            throw new Error(`embedding_persist_failed:${updateError.message}`);
          }
        }
      }

      const { count: remaining, error: remainingError } = await db.from(
        "document_chunks",
      )
        .select("id", { count: "exact", head: true })
        .eq("document_id", doc.id)
        .is("embedding", null);
      if (remainingError) {
        throw new Error(`embedding_count_failed:${remainingError.message}`);
      }
      if (embeddingStageStatus(remaining ?? 0) === "queued") {
        await finish("queued");
        await heartbeat();
        return json({
          ok: true,
          job_id: job.id,
          document_id: job.document_id,
          stage: job.stage,
          status: "queued",
          remaining_chunks: remaining,
          model: EMBEDDING_MODEL,
        });
      }
    } else if (job.stage === "analyze") {
      if (!doc.matter_id) {
        throw new Error("analysis_manual_review_matter_id_missing");
      }

      const { count: missingEmbeddings, error: countError } = await db.from(
        "document_chunks",
      )
        .select("id", { count: "exact", head: true })
        .eq("document_id", doc.id)
        .is("embedding", null);
      if (countError) {
        throw new Error(`embedding_count_failed:${countError.message}`);
      }
      if ((missingEmbeddings ?? 0) > 0) {
        throw new Error("analysis_manual_review_embeddings_incomplete");
      }

      const pipelineJobId = String(job.id);
      const { data: existingAnalysis, error: existingError } = await db.from(
        "ai_analyses",
      )
        .select("id,status")
        .eq("document_id", doc.id)
        .eq("analysis_type", "document_pipeline")
        .eq("created_by", "document-pipeline-worker")
        .contains("result", { pipeline_job_id: pipelineJobId })
        .in("status", ["completed", "manual_review"])
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle();
      if (existingError) {
        throw new Error(
          `analysis_idempotency_check_failed:${existingError.message}`,
        );
      }
      if (existingAnalysis) {
        const existingStatus = existingAnalysis.status === "completed"
          ? "completed"
          : "manual_review";
        await finish(
          existingStatus,
          existingStatus === "manual_review"
            ? "analysis_manual_review:existing_result"
            : null,
        );
        await heartbeat();
        return json({
          ok: existingStatus === "completed",
          job_id: job.id,
          document_id: job.document_id,
          stage: job.stage,
          status: existingStatus,
          idempotent_replay: true,
        }, existingStatus === "completed" ? 200 : 422);
      }

      const chunks = await readAllChunks(doc.id);
      if (!chunks.length) throw new Error("no_chunks");
      const context = chunks.map((chunk) => {
        return `[page ${chunk.source_page}, chunk ${chunk.chunk_index}]\n${chunk.content}`;
      }).join("\n\n");
      if (context.length > ANALYSIS_MAX_CONTEXT_CHARS) {
        throw new Error("analysis_manual_review_context_too_large");
      }

      const prompt =
        `Analyze ONLY the supplied legal document. Do not invent facts and do not silently correct the source. Return JSON with summary, persons, dates, case_numbers, statutes, monetary_amounts, procedural_events, contradictions, risks, missing_information, confidence, requires_lawyer_review, citations. citations must be an array of {claim, page, chunk_index}; every significant factual finding must have a citation to the supplied page and chunk. Explicitly distinguish: (1) statements of the suspect, (2) questions/statements of the investigator, (3) information about third parties, and (4) procedural boilerplate. If the supplied pages are incomplete, say so.\n\nDOCUMENT:\n${context}`;
      const response = await fetchWithRetry(
        (signal, _attempt, requestId) => {
          return fetch("https://api.openai.com/v1/responses", {
            method: "POST",
            headers: {
              authorization: `Bearer ${key}`,
              "content-type": "application/json",
              "x-client-request-id": requestId,
            },
            body: JSON.stringify({
              model: ANALYSIS_MODEL,
              input: prompt,
              text: { format: { type: "json_object" } },
            }),
            signal,
          });
        },
        {
          maxAttempts: OPENAI_MAX_ATTEMPTS,
          timeoutMs: OPENAI_TIMEOUT_MS,
          stage: "analyze",
          requestIdPrefix: `${requestTrace}-analysis`,
        },
      );
      if (!response.ok) {
        throw new Error(
          `analysis_api:${response.status}:${
            (await response.text()).slice(0, 1200)
          }`,
        );
      }
      const output = await response.json();
      let parsed: unknown;
      try {
        parsed = JSON.parse(output.output_text || "{}");
      } catch {
        throw new Error("analysis_invalid_json");
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("analysis_not_an_object");
      }
      const result = parsed as Record<string, unknown>;

      const validation = validateAnalysisResult(result, chunks);
      const sourceChunks = chunks.map((chunk) => ({
        id: chunk.id,
        page: chunk.source_page,
        chunk_index: chunk.chunk_index,
      }));
      const persistedResult = {
        ...result,
        pipeline_job_id: pipelineJobId,
        citations: validation.citations,
        source_chunks: sourceChunks,
        confidence: clampConfidence(result.confidence),
        requires_lawyer_review: true,
        validation_errors: validation.errors,
      };
      const { error: persistError } = await db.from("ai_analyses").insert({
        matter_id: doc.matter_id,
        document_id: doc.id,
        analysis_type: "document_pipeline",
        result: persistedResult,
        citations: validation.citations,
        source_chunks: sourceChunks,
        confidence: clampConfidence(result.confidence),
        requires_lawyer_review: true,
        status: validation.valid ? "completed" : "manual_review",
        review_status: "pending",
        model: ANALYSIS_MODEL,
        created_by: "document-pipeline-worker",
      });
      if (persistError) {
        throw new Error(`analysis_persist_failed:${persistError.message}`);
      }

      if (!validation.valid) {
        const validationError = `analysis_manual_review:${
          validation.errors.join(",")
        }`;
        await finish("manual_review", validationError);
        await heartbeat();
        return json({
          ok: false,
          job_id: job.id,
          document_id: job.document_id,
          stage: job.stage,
          status: "manual_review",
          error: validationError,
        }, 422);
      }
    } else {
      throw new Error(`unknown_pipeline_stage:${job.stage}`);
    }

    await finish("completed");
    await heartbeat();
    return json({
      ok: true,
      job_id: job.id,
      document_id: job.document_id,
      stage: job.stage,
      status: "completed",
      model: job.stage === "embed" ? EMBEDDING_MODEL : ANALYSIS_MODEL,
    });
  } catch (error) {
    const message = String(error);
    const attempts = Number(job.attempts ?? 1);
    const disposition = pipelineFailureDisposition(
      message,
      attempts,
      pipelineMaxRetries,
    );
    const manualReview = disposition === "manual_review";
    const retrying = disposition === "queued";
    try {
      const retryAt = retrying
        ? new Date(Date.now() + jobRetryDelayMs(attempts)).toISOString()
        : null;
      await finish(
        manualReview ? "manual_review" : retrying ? "queued" : "failed",
        message,
        retryAt,
      );
    } catch (finishError) {
      return json({
        ok: false,
        job_id: job.id,
        document_id: job.document_id,
        stage: job.stage,
        status: "processing",
        error: String(finishError),
        cause: message,
      }, 500);
    }
    return json({
      ok: false,
      job_id: job.id,
      document_id: job.document_id,
      stage: job.stage,
      status: manualReview ? "manual_review" : retrying ? "queued" : "failed",
      retry_scheduled: retrying || undefined,
      error: message,
    }, manualReview ? 422 : retrying ? 503 : 502);
  }
});
