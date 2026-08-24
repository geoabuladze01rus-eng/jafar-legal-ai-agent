import { createClient } from "npm:@supabase/supabase-js@2.112.3";
import {
  clampConfidence,
  configuredInteger,
  configuredModel,
  isAuthorizedWorker,
} from "../_shared/document-worker.ts";

const OCR_MODEL = configuredModel("JAFAR_OCR_MODEL", "gpt-5.6");
const CONFIDENCE_THRESHOLD = 0.85;
const DEFAULT_MAX_RETRIES = configuredInteger(
  "JAFAR_OCR_MAX_RETRIES",
  3,
  1,
  20,
);

type OcrPage = {
  page_number?: unknown;
  text?: unknown;
  confidence?: unknown;
};

type ResponsesOutput = {
  output_text?: string;
  output?: Array<{ content?: Array<{ text?: string }> }>;
};

function isOcrPage(value: unknown): value is OcrPage {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

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

async function openaiFile(key: string, file: Blob) {
  const form = new FormData();
  form.append("purpose", "user_data");
  form.append("file", file, "document.pdf");
  const response = await fetch("https://api.openai.com/v1/files", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}` },
    body: form,
  });
  if (!response.ok) {
    throw new Error(
      `file_upload:${response.status}:${(await response.text()).slice(0, 700)}`,
    );
  }
  return await response.json();
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
  const workerId = crypto.randomUUID();
  const { data: jobs, error: claimError } = await db.rpc(
    "claim_document_ocr_job",
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

  let maxRetries = DEFAULT_MAX_RETRIES;
  const fail = async (message: string, retry = true) => {
    const attempts = Number(job.attempts ?? 1);
    const terminal = !retry || attempts >= maxRetries;
    const next = terminal ? null : new Date(
      Date.now() + Math.min(120000, 5000 * 2 ** Math.max(0, attempts - 1)),
    )
      .toISOString();
    const { error } = await db.rpc("fail_document_ocr_job", {
      p_job_id: job.id,
      p_document_id: job.document_id,
      p_worker_id: workerId,
      p_error: message,
      p_retry: !terminal,
      p_available_at: next,
    });
    if (error) throw new Error(`ocr_failure_persist_failed:${error.message}`);
  };

  const { data: doc, error: docError } = await db.from("documents")
    .select(
      "id,matter_id,storage_path,filename,content_type,max_retry_attempts",
    )
    .eq("id", job.document_id)
    .maybeSingle();
  if (docError || !doc) {
    await fail("document_not_found", false);
    return json({ error: "document_not_found" }, 404);
  }
  maxRetries = Number.isSafeInteger(Number(doc.max_retry_attempts))
    ? Math.max(1, Number(doc.max_retry_attempts))
    : DEFAULT_MAX_RETRIES;
  if (!doc.storage_path) {
    await fail("storage_path_missing", false);
    return json(
      { error: "storage_path_missing", manual_review_required: true },
      422,
    );
  }

  const { data: file, error: storageError } = await db.storage
    .from("jafar-legal-documents")
    .download(doc.storage_path);
  if (storageError || !file) {
    await fail(`storage_download_failed:${storageError?.message ?? "empty"}`);
    return json({ error: "storage_download_failed" }, 502);
  }

  let uploaded;
  try {
    uploaded = await openaiFile(key, file);
  } catch (error) {
    await fail(String(error));
    return json({ error: "openai_file_upload_failed" }, 502);
  }

  const payload = {
    model: OCR_MODEL,
    input: [{
      role: "user",
      content: [
        {
          type: "input_text",
          text:
            "OCR this legal PDF with maximum fidelity. Return JSON only: pages:[{page_number:number,text:string,confidence:number}]. Preserve Russian names, dates, case numbers, statutes, amounts, addresses and punctuation. Do not infer unreadable text; lower confidence when uncertain. confidence 0..1.",
        },
        { type: "input_file", file_id: uploaded.id },
      ],
    }],
    text: { format: { type: "json_object" } },
  };

  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    await fail(
      `responses:${response.status}:${(await response.text()).slice(0, 1500)}`,
    );
    return json({ error: "openai_ocr_failed" }, 502);
  }

  const output = await response.json() as ResponsesOutput;
  const raw = output.output_text ?? output.output
    ?.flatMap((item) => item.content ?? [])
    .map((item) => item.text ?? "")
    .join("") ??
    "";
  let parsed: { pages?: unknown };
  try {
    parsed = JSON.parse(raw);
  } catch {
    await fail("ocr_invalid_json", false);
    return json(
      { error: "ocr_invalid_json", manual_review_required: true },
      502,
    );
  }

  const pages = Array.isArray(parsed.pages)
    ? parsed.pages.filter(isOcrPage)
    : [];
  if (!pages.length) {
    await fail("ocr_empty_result", false);
    return json(
      { error: "ocr_empty_result", manual_review_required: true },
      502,
    );
  }

  const rows = pages
    .filter((page) =>
      Number.isInteger(Number(page.page_number)) && Number(page.page_number) > 0
    )
    .map((page) => {
      const confidence = clampConfidence(page.confidence);
      return {
        document_id: doc.id,
        page_number: Number(page.page_number),
        extracted_text: typeof page.text === "string" ? page.text : "",
        ocr_used: true,
        ocr_confidence: confidence,
        status: confidence < CONFIDENCE_THRESHOLD
          ? "manual_review"
          : "completed",
        error: null,
        updated_at: new Date().toISOString(),
      };
    });
  if (!rows.length) {
    await fail("ocr_no_valid_pages", false);
    return json(
      { error: "ocr_no_valid_pages", manual_review_required: true },
      502,
    );
  }

  const { error: persistError } = await db.from("document_pages")
    .upsert(rows, { onConflict: "document_id,page_number" });
  if (persistError) {
    await fail(`page_persist:${persistError.message}`, false);
    return json({ error: "page_persist_failed" }, 500);
  }

  const lowConfidencePages = rows.filter((page) => {
    return Number(page.ocr_confidence) < CONFIDENCE_THRESHOLD;
  }).length;
  const invalidPages = pages.length - rows.length;
  const manualReview = lowConfidencePages > 0 || invalidPages > 0;
  const { error: handoffError } = await db.rpc(
    "complete_ocr_and_enqueue_pipeline",
    {
      p_job_id: job.id,
      p_document_id: doc.id,
      p_pages_total: pages.length,
      p_pages_completed: rows.length,
      p_manual_review: manualReview,
      p_worker_id: workerId,
    },
  );
  if (handoffError) {
    await fail(`ocr_completion_handoff_failed:${handoffError.message}`);
    return json({ error: "ocr_completion_handoff_failed" }, 500);
  }

  await db.from("worker_heartbeats").upsert({
    worker_name: "document-ocr-worker",
    last_seen_at: new Date().toISOString(),
    status: "active",
    updated_at: new Date().toISOString(),
  });
  return json({
    ok: true,
    job_id: job.id,
    document_id: doc.id,
    pages: rows.length,
    low_confidence_pages: lowConfidencePages,
    invalid_pages: invalidPages,
    status: manualReview ? "manual_review" : "pipeline_processing",
    model: OCR_MODEL,
  });
});
