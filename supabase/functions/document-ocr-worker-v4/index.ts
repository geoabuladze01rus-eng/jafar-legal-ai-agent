import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const MODEL = "gpt-5.6-luna";
const THRESHOLD = 0.85;
const MAX_RETRIES = 3;

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json" },
});

function configuredKeys(): string[] {
  const worker = Deno.env.get("JAFAR_WORKER_SECRET")?.trim() ?? "";
  return worker.length >= 32 ? [worker] : [];
}

function safeEqual(left: string, right: string): boolean {
  const leftBytes = new TextEncoder().encode(left);
  const rightBytes = new TextEncoder().encode(right);
  if (leftBytes.length !== rightBytes.length) return false;
  let difference = 0;
  for (let index = 0; index < leftBytes.length; index++) {
    difference |= leftBytes[index] ^ rightBytes[index];
  }
  return difference === 0;
}

function isInternal(req: Request): boolean {
  const apiKey = req.headers.get("apikey") ?? "";
  const auth = req.headers.get("Authorization") ?? "";
  const bearer = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  return configuredKeys().some((key) => safeEqual(key, apiKey) || safeEqual(key, bearer));
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
  if (!response.ok) throw new Error(`file_upload:${response.status}:${(await response.text()).slice(0, 700)}`);
  return await response.json();
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  if (!isInternal(req)) return json({ error: "unauthorized_worker" }, 401);

  const url = Deno.env.get("SUPABASE_URL");
  const service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const key = Deno.env.get("OPENAI_API_KEY");
  if (!url || !service || !key) return json({ error: "server_not_configured" }, 503);

  const db = createClient(url, service);
  const { data: jobs, error: claimError } = await db.rpc("claim_document_ocr_job", {
    p_worker_id: crypto.randomUUID(),
    p_lease_seconds: 600,
  });
  if (claimError) return json({ error: "claim_failed" }, 500);

  const job = jobs?.[0];
  if (!job) return json({ ok: true, status: "idle" });

  const fail = async (message: string, retry = true) => {
    const attempts = Number(job.attempts ?? 1);
    const terminal = !retry || attempts >= MAX_RETRIES;
    const next = terminal ? null : new Date(Date.now() + Math.min(120000, 5000 * attempts)).toISOString();
    await db.from("document_ocr_jobs").update({
      status: terminal ? "manual_review" : "queued",
      last_error: message.slice(0, 2000),
      finished_at: terminal ? new Date().toISOString() : null,
      available_at: next,
      updated_at: new Date().toISOString(),
    }).eq("id", job.id);
    await db.from("documents").update({
      processing_status: terminal ? "failed" : "processing",
      manual_review_required: terminal,
      retry_attempts: attempts,
      last_error_at: new Date().toISOString(),
      next_retry_at: next,
    }).eq("id", job.document_id);
  };

  const { data: doc, error: docError } = await db.from("documents")
    .select("id,matter_id,storage_path,filename,content_type")
    .eq("id", job.document_id)
    .maybeSingle();
  if (docError || !doc) {
    await fail("document_not_found", false);
    return json({ error: "document_not_found" }, 404);
  }
  if (!doc.storage_path) {
    await fail("storage_path_missing", false);
    return json({ error: "storage_path_missing", manual_review_required: true }, 422);
  }

  await db.from("documents").update({ processing_status: "processing", manual_review_required: false }).eq("id", doc.id);

  const { data: file, error: storageError } = await db.storage.from("jafar-legal-documents").download(doc.storage_path);
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
    model: MODEL,
    input: [{ role: "user", content: [
      { type: "input_text", text: "OCR this legal PDF with maximum fidelity. Return JSON only: pages:[{page_number:number,text:string,confidence:number}]. Preserve Russian names, dates, case numbers, statutes, amounts, addresses and punctuation. Do not infer unreadable text; lower confidence when uncertain. confidence 0..1." },
      { type: "input_file", file_id: uploaded.id },
    ] }],
    text: { format: { type: "json_object" } },
  };

  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    await fail(`responses:${response.status}:${(await response.text()).slice(0, 1500)}`);
    return json({ error: "openai_ocr_failed" }, 502);
  }

  const output = await response.json();
  const raw = output.output_text ?? output.output?.flatMap((item: any) => item.content ?? []).map((item: any) => item.text ?? "").join("") ?? "";
  let parsed: any;
  try { parsed = JSON.parse(raw); } catch {
    await fail("ocr_invalid_json", false);
    return json({ error: "ocr_invalid_json", manual_review_required: true }, 502);
  }

  const pages = Array.isArray(parsed.pages) ? parsed.pages : [];
  if (!pages.length) {
    await fail("ocr_empty_result", false);
    return json({ error: "ocr_empty_result", manual_review_required: true }, 502);
  }

  const rows = pages
    .filter((page: any) => Number.isInteger(Number(page.page_number)) && Number(page.page_number) > 0)
    .map((page: any) => ({
      document_id: doc.id,
      page_number: Number(page.page_number),
      extracted_text: typeof page.text === "string" ? page.text : "",
      ocr_used: true,
      ocr_confidence: Math.max(0, Math.min(1, Number(page.confidence) || 0)),
      status: (Number(page.confidence) || 0) < THRESHOLD ? "manual_review" : "completed",
      error: null,
      updated_at: new Date().toISOString(),
    }));

  const { error: persistError } = await db.from("document_pages").upsert(rows, { onConflict: "document_id,page_number" });
  if (persistError) {
    await fail(`page_persist:${persistError.message}`, false);
    return json({ error: "page_persist_failed" }, 500);
  }

  const low = rows.filter((page: any) => Number(page.ocr_confidence) < THRESHOLD).length;
  const status = low ? "manual_review" : "completed";
  await db.from("document_ocr_jobs").update({
    status,
    pages_total: rows.length,
    pages_completed: rows.length,
    finished_at: new Date().toISOString(),
    last_error: low ? `low_ocr_confidence_pages:${low}` : null,
    updated_at: new Date().toISOString(),
  }).eq("id", job.id);
  await db.from("documents").update({
    processing_status: "completed",
    manual_review_required: low > 0,
    next_retry_at: null,
  }).eq("id", doc.id);

  await db.from("worker_heartbeats").upsert({ worker_name: "document-ocr-worker", last_seen_at: new Date().toISOString(), status: "active", updated_at: new Date().toISOString() });
  return json({ ok: true, job_id: job.id, document_id: doc.id, pages: rows.length, low_confidence_pages: low, status, model: MODEL });
});
