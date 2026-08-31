import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { semanticLegalChunks } from "../_shared/legal_chunking.ts";

const MODEL = "gpt-5.6-luna";
const EMBED_MODEL = "text-embedding-3-small";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json" },
});

function configuredKeys(): string[] {
  const keys: string[] = [];
  for (const envName of ["SUPABASE_PUBLISHABLE_KEYS", "SUPABASE_SECRET_KEYS"]) {
    try {
      const raw = Deno.env.get(envName);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      for (const value of Object.values(parsed)) if (typeof value === "string") keys.push(value);
    } catch { /* ignore malformed optional key maps */ }
  }
  const worker = Deno.env.get("JAFAR_WORKER_SECRET");
  if (worker) keys.push(worker);
  return [...new Set(keys)];
}

function isInternal(req: Request): boolean {
  const apiKey = req.headers.get("apikey") ?? "";
  const auth = req.headers.get("Authorization") ?? "";
  const bearer = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  return configuredKeys().includes(apiKey) || configuredKeys().includes(bearer);
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  if (!isInternal(req)) return json({ error: "unauthorized_worker" }, 401);

  const url = Deno.env.get("SUPABASE_URL");
  const service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const key = Deno.env.get("OPENAI_API_KEY");
  if (!url || !service || !key) return json({ error: "server_not_configured" }, 503);

  const db = createClient(url, service);
  const { data: jobs, error: claimError } = await db.rpc("claim_document_pipeline_job", {
    p_worker_id: crypto.randomUUID(),
    p_lease_seconds: 600,
  });
  if (claimError) return json({ error: "claim_failed", detail: claimError.message }, 500);

  const job = jobs?.[0];
  if (!job) return json({ ok: true, status: "idle" });

  const finish = async (status: string, error: string | null = null) => {
    await db.from("document_pipeline_jobs").update({
      status,
      last_error: error?.slice(0, 2000) ?? null,
      locked_at: null,
      lease_expires_at: null,
      updated_at: new Date().toISOString(),
    }).eq("id", job.id);
  };

  try {
    const { data: doc, error: docError } = await db.from("documents")
      .select("id,matter_id,filename,processing_status,manual_review_required")
      .eq("id", job.document_id)
      .maybeSingle();
    if (docError || !doc) throw new Error("document_not_found");
    if (doc.manual_review_required) throw new Error("ocr_manual_review_required");

    if (job.stage === "chunk") {
      const { data: pages, error } = await db.from("document_pages")
        .select("page_number,extracted_text,ocr_confidence,status")
        .eq("document_id", doc.id)
        .order("page_number");
      if (error) throw new Error(`page_read_failed:${error.message}`);
      if (!pages?.length) throw new Error("no_pages");
      if (pages.some((page: any) => page.status === "manual_review")) throw new Error("ocr_manual_review_required");

      await db.from("document_chunks").delete().eq("document_id", doc.id);
      const rows: any[] = [];
      let chunkIndex = 0;

      for (const page of pages) {
        const text = String(page.extracted_text ?? "").replace(/\r\n/g, "\n").trim();
        if (!text) continue;
        for (const chunk of semanticLegalChunks(text)) {
          rows.push({
            document_id: doc.id,
            chunk_index: chunkIndex++,
            content: chunk.content,
            source_page: page.page_number,
            stable_chunk_id: `v1:${page.page_number}:${chunk.sourceStart}:${chunk.sourceEnd}`,
            source_section: chunk.section,
            source_start: chunk.sourceStart,
            source_end: chunk.sourceEnd,
          });
        }
      }
      if (!rows.length) throw new Error("empty_document_text");
      const { error: insertError } = await db.from("document_chunks").insert(rows);
      if (insertError) throw new Error(`chunk_persist_failed:${insertError.message}`);
    }

    if (job.stage === "embed") {
      const { data: chunks, error } = await db.from("document_chunks")
        .select("id,content")
        .eq("document_id", doc.id)
        .is("embedding", null)
        .order("chunk_index")
        .limit(100);
      if (error) throw new Error(`chunk_read_failed:${error.message}`);
      if (chunks?.length) {
        const response = await fetch("https://api.openai.com/v1/embeddings", {
          method: "POST",
          headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
          body: JSON.stringify({ model: EMBED_MODEL, input: chunks.map((chunk: any) => chunk.content) }),
        });
        if (!response.ok) throw new Error(`embedding_api:${response.status}:${(await response.text()).slice(0, 800)}`);
        const output = await response.json();
        for (let i = 0; i < chunks.length; i++) {
          const embedding = output.data?.[i]?.embedding;
          if (!embedding) throw new Error(`embedding_missing:${i}`);
          const { error: updateError } = await db.from("document_chunks").update({ embedding }).eq("id", chunks[i].id);
          if (updateError) throw new Error(`embedding_persist_failed:${updateError.message}`);
        }
      }
    }

    if (job.stage === "analyze") {
      const { data: chunks, error } = await db.from("document_chunks")
        .select("id,chunk_index,source_page,content")
        .eq("document_id", doc.id)
        .order("chunk_index")
        .limit(80);
      if (error) throw new Error(`analysis_context_failed:${error.message}`);
      if (!chunks?.length) throw new Error("no_chunks");

      const context = chunks.map((chunk: any) => `[page ${chunk.source_page}, chunk ${chunk.chunk_index}]\n${chunk.content}`).join("\n\n");
      const prompt = `Analyze ONLY the supplied legal document. Do not invent facts and do not silently correct the source. Return JSON with summary, persons, dates, case_numbers, statutes, monetary_amounts, procedural_events, contradictions, risks, missing_information, confidence, requires_lawyer_review, citations. Every factual claim must cite page and chunk. Explicitly distinguish: (1) statements of the suspect, (2) questions/statements of the investigator, (3) information about third parties, and (4) procedural boilerplate. If the supplied pages are incomplete, say so.\n\nDOCUMENT:\n${context}`;
      const response = await fetch("https://api.openai.com/v1/responses", {
        method: "POST",
        headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
        body: JSON.stringify({ model: MODEL, input: prompt, text: { format: { type: "json_object" } } }),
      });
      if (!response.ok) throw new Error(`analysis_api:${response.status}:${(await response.text()).slice(0, 1200)}`);
      const output = await response.json();
      let result: any;
      try { result = JSON.parse(output.output_text || "{}"); } catch { throw new Error("analysis_invalid_json"); }

      const { error: persistError } = await db.from("ai_analyses").insert({
        matter_id: doc.matter_id,
        document_id: doc.id,
        analysis_type: "document_pipeline",
        result,
        citations: result.citations || [],
        source_chunks: chunks.map((chunk: any) => ({ id: chunk.id, page: chunk.source_page, chunk_index: chunk.chunk_index })),
        confidence: Number(result.confidence) || 0,
        requires_lawyer_review: true,
        status: "completed",
        review_status: "pending",
        model: MODEL,
        created_by: "document-pipeline-worker",
      });
      if (persistError) throw new Error(`analysis_persist_failed:${persistError.message}`);
    }

    await finish("completed");
    await db.from("worker_heartbeats").upsert({ worker_name: "document-pipeline-worker", last_seen_at: new Date().toISOString(), status: "active", updated_at: new Date().toISOString() });
    return json({ ok: true, job_id: job.id, document_id: job.document_id, stage: job.stage, status: "completed" });
  } catch (error) {
    const message = String(error);
    const manual = message.includes("manual_review");
    await finish(manual ? "manual_review" : "failed", message);
    return json({ ok: false, job_id: job.id, document_id: job.document_id, stage: job.stage, status: manual ? "manual_review" : "failed", error: message }, manual ? 422 : 502);
  }
});
