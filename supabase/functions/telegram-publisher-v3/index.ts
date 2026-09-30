import "jsr:@supabase/functions-js/edge-runtime.d.ts";

type QueueRow = {
  publication_id: string;
  source_notion_page_id: string | null;
  status: string;
  publication_type: "text" | "photo" | "poll" | "quiz";
  scheduled_at: string;
  content: string;
  caption: string | null;
  question: string | null;
  options: unknown;
  correct_option_ids: unknown;
  explanation: string | null;
  visual_asset_key: string | null;
  visual_category: string | null;
  fact_check_status: string;
  legal_risk: string;
  privacy_risk: string;
  current_case_risk: boolean;
  editorial_blockers: unknown;
  content_fingerprint: string;
  delivery_state: string;
  reconciliation_required: boolean;
  telegram_message_id: number | null;
};

type PublisherConfig = {
  enabled: boolean;
  dry_run: boolean;
  chat_id: string;
  batch_size: number;
};

type VisualAsset = {
  asset_key: string;
  category: string;
  version: number;
  filename: string;
  mime_type: string;
  sha256: string;
  data_base64: string;
};

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const HEX64 = /^[0-9a-f]{64}$/;

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function serviceHeaders() {
  return {
    authorization: `Bearer ${SERVICE_KEY}`,
    apikey: SERVICE_KEY,
    "content-type": "application/json",
  };
}

async function rpc<T>(name: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: serviceHeaders(),
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) {
    throw new Error(`rpc_${name}_${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

async function fetchExpectedWorkerSecret(): Promise<string> {
  const value = await rpc<unknown>("get_jafar_worker_secret_for_publisher", {});
  return typeof value === "string" ? value : "";
}

async function authorized(req: Request): Promise<boolean> {
  const supplied = req.headers.get("x-jafar-worker-secret")?.trim() ?? "";
  if (!supplied) return false;
  const expected = (await fetchExpectedWorkerSecret()).trim();
  if (!expected || supplied.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < supplied.length; i++) diff |= supplied.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

async function fetchConfig(): Promise<PublisherConfig> {
  const response = await fetch(
    `${SUPABASE_URL}/rest/v1/telegram_publisher_config?id=eq.1&select=enabled,dry_run,chat_id,batch_size`,
    { headers: serviceHeaders(), signal: AbortSignal.timeout(10000) },
  );
  if (!response.ok) throw new Error(`config_fetch_${response.status}`);
  const rows = await response.json();
  if (!Array.isArray(rows) || !rows.length) throw new Error("publisher_config_missing");
  return rows[0] as PublisherConfig;
}

async function fetchDue(limit: number): Promise<QueueRow[]> {
  const now = encodeURIComponent(new Date().toISOString());
  const url = `${SUPABASE_URL}/rest/v1/telegram_publication_queue` +
    `?status=eq.Ready&delivery_state=eq.pending&reconciliation_required=eq.false` +
    `&scheduled_at=lte.${now}&order=scheduled_at.asc,publication_id.asc&limit=${limit}`;
  const response = await fetch(url, { headers: serviceHeaders(), signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`queue_fetch_${response.status}`);
  return await response.json() as QueueRow[];
}

function normalizeOptions(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    if (typeof item === "string") return item.trim();
    if (item && typeof item === "object" && "text" in item) {
      const text = (item as Record<string, unknown>).text;
      return typeof text === "string" ? text.trim() : "";
    }
    return "";
  });
}

function normalizeCorrectIds(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.map(Number).filter((x) => Number.isInteger(x));
}

async function resolveVisual(row: QueueRow): Promise<VisualAsset | null> {
  if (row.publication_type !== "photo") return null;
  const data = await rpc<unknown>("resolve_telegram_visual_asset", {
    p_asset_key: row.visual_asset_key,
    p_category: row.visual_category,
  });
  const first = Array.isArray(data) ? data[0] : data;
  if (!first || typeof first !== "object") throw new Error("visual_asset_missing");
  return first as VisualAsset;
}

async function revalidateNotion(row: QueueRow): Promise<string[]> {
  const source = row.source_notion_page_id?.trim() ?? "";
  // Trusted autopilot rows are created by a service-role-only RPC and do not
  // have a Notion page. They still pass every queue validation gate below.
  if (source.startsWith("autopilot:")) return [];
  if (!source) return ["notion_source_missing"];
  const response = await fetch(`${SUPABASE_URL}/functions/v1/telegram-notion-guard-v3`, {
    method: "POST",
    headers: serviceHeaders(),
    body: JSON.stringify(row),
    signal: AbortSignal.timeout(22000),
  });
  if (!response.ok) return ["notion_guard_unavailable"];
  let body: Record<string, unknown> = {};
  try { body = await response.json(); } catch { return ["notion_guard_non_json"]; }
  if (body.ok !== true) return ["notion_guard_unavailable"];
  if (body.allowed === true) return [];
  const reasons = Array.isArray(body.reasons) ? body.reasons.map(String).filter(Boolean) : [];
  return reasons.length ? reasons : ["notion_guard_blocked"];
}

function validate(row: QueueRow, visual: VisualAsset | null): string[] {
  const reasons: string[] = [];
  if (row.status !== "Ready") reasons.push("status_not_ready");
  if (new Date(row.scheduled_at).getTime() > Date.now()) reasons.push("publish_time_not_due");
  if (!HEX64.test(row.content_fingerprint || "")) reasons.push("content_fingerprint_invalid");
  if (!["verified", "not_required"].includes(row.fact_check_status)) reasons.push("fact_check_not_verified");
  if (row.legal_risk !== "low") reasons.push("legal_risk_not_low");
  if (row.privacy_risk !== "low") reasons.push("privacy_risk_not_low");
  if (row.current_case_risk) reasons.push("current_case_risk");
  if (row.delivery_state !== "pending") reasons.push("delivery_state_not_pending");
  if (row.reconciliation_required) reasons.push("reconciliation_required");
  if (row.telegram_message_id !== null) reasons.push("already_has_telegram_message_id");
  if (!Array.isArray(row.editorial_blockers) || row.editorial_blockers.length) reasons.push("editorial_blockers_present");

  if (row.publication_type === "text") {
    if (!row.content.trim()) reasons.push("text_missing");
    if (row.content.length > 4096) reasons.push("text_too_long");
  } else if (row.publication_type === "photo") {
    if (!row.visual_asset_key?.trim()) reasons.push("visual_asset_key_missing");
    if (!row.visual_category?.trim()) reasons.push("visual_category_missing");
    if (!visual) reasons.push("visual_asset_unresolved");
    if (visual) {
      if (!["image/jpeg", "image/png", "image/webp"].includes(visual.mime_type)) {
        reasons.push("visual_mime_invalid");
      }
      try {
        const byteLength = atob(visual.data_base64).length;
        if (byteLength === 0 || byteLength > 10 * 1024 * 1024) reasons.push("visual_size_invalid");
      } catch {
        reasons.push("visual_base64_invalid");
      }
    }
    const caption = (row.caption ?? row.content ?? "").trim();
    if (caption.length > 1024) reasons.push("caption_too_long");
  } else if (row.publication_type === "poll" || row.publication_type === "quiz") {
    const question = (row.question ?? "").trim();
    const options = normalizeOptions(row.options);
    if (!question) reasons.push("question_missing");
    if (question.length > 300) reasons.push("question_too_long");
    if (options.length < 2 || options.length > 12 || options.some((x) => !x)) reasons.push("invalid_options");
    if (options.some((x) => x.length > 100)) reasons.push("option_too_long");
    if (row.publication_type === "quiz") {
      const ids = normalizeCorrectIds(row.correct_option_ids);
      if (!ids.length || new Set(ids).size !== ids.length || ids.some((id) => id < 0 || id >= options.length)) {
        reasons.push("invalid_correct_option_ids");
      }
      if ((row.explanation ?? "").length > 200) reasons.push("explanation_too_long");
      if (((row.explanation ?? "").match(/\n/g) ?? []).length > 2) reasons.push("explanation_too_many_line_feeds");
    }
  } else {
    reasons.push("publication_type_invalid");
  }
  return reasons;
}

function stableHashInput(row: QueueRow, config: PublisherConfig, visual: VisualAsset | null) {
  return {
    chat_id: config.chat_id,
    publication_type: row.publication_type,
    content: row.content ?? "",
    caption: row.caption ?? "",
    visual_asset_key: row.visual_asset_key ?? "",
    visual_category: row.visual_category ?? "",
    visual_sha256: visual?.sha256 ?? "",
    question: row.question ?? "",
    options: normalizeOptions(row.options),
    correct_option_ids: normalizeCorrectIds(row.correct_option_ids),
    explanation: row.explanation ?? "",
  };
}

async function sha256Hex(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(digest).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function buildEgressPayload(row: QueueRow, config: PublisherConfig, visual: VisualAsset | null) {
  if (row.publication_type === "text") {
    return { action: "sendMessage", chat_id: config.chat_id, text: row.content };
  }
  if (row.publication_type === "photo") {
    if (!visual) throw new Error("visual_asset_unresolved");
    return {
      action: "sendPhoto",
      chat_id: config.chat_id,
      photo_base64: visual.data_base64,
      filename: visual.filename,
      mime_type: visual.mime_type,
      caption: (row.caption ?? row.content ?? "").trim(),
    };
  }
  const base: Record<string, unknown> = {
    action: "sendPoll",
    chat_id: config.chat_id,
    question: row.question,
    options: normalizeOptions(row.options),
    type: row.publication_type === "quiz" ? "quiz" : "regular",
    is_anonymous: true,
  };
  if (row.publication_type === "quiz") {
    base.correct_option_ids = normalizeCorrectIds(row.correct_option_ids);
    if (row.explanation?.trim()) base.explanation = row.explanation.trim();
  }
  return base;
}

async function egress(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch(`${SUPABASE_URL}/functions/v1/telegram-egress`, {
    method: "POST",
    headers: serviceHeaders(),
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(70000),
  });
  let body: Record<string, unknown> = {};
  try { body = await response.json(); } catch { body = { ok: false, error: "non_json_egress_response" }; }
  return { ...body, _http_status: response.status };
}

function extractMessageId(result: Record<string, unknown>): number | null {
  const currentId = Number(result.telegram_message_id);
  if (Number.isInteger(currentId) && currentId > 0) return currentId;

  // Rolling-deploy compatibility only: the previous egress wrapped Telegram's
  // response. Never log or return that legacy body; remove after every deployment
  // is confirmed on the sanitized telegram_message_id contract.
  const telegram = result.telegram;
  if (!telegram || typeof telegram !== "object") return null;
  const message = (telegram as Record<string, unknown>).result;
  if (!message || typeof message !== "object") return null;
  const legacyId = Number((message as Record<string, unknown>).message_id);
  return Number.isInteger(legacyId) && legacyId > 0 ? legacyId : null;
}

async function markUncertain(publicationId: string, note: string) {
  try {
    await rpc<void>("mark_telegram_publication_uncertain_v3", {
      p_publication_id: publicationId,
      p_note: note.slice(0, 900),
    });
  } catch {
    // Fail closed. A claimed ledger record is still not retryable.
  }
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
  if (!SUPABASE_URL || !SERVICE_KEY) return json({ ok: false, error: "supabase_runtime_missing" }, 500);

  try {
    if (!(await authorized(req))) return json({ ok: false, error: "unauthorized" }, 401);
  } catch {
    return json({ ok: false, error: "worker_auth_unavailable" }, 503);
  }

  let body: Record<string, unknown> = {};
  try { body = await req.json(); } catch { body = {}; }
  const mode = body.mode === "publish" ? "publish" : "preflight";

  try {
    const config = await fetchConfig();
    const requested = Number(body.limit ?? config.batch_size ?? 3);
    const limit = Math.max(1, Math.min(Number.isInteger(requested) ? requested : 3, 20));
    const rows = await fetchDue(limit);
    const tokenPresent = await rpc<boolean>("telegram_bot_token_present", {});

    const candidates = [] as Record<string, unknown>[];
    for (const row of rows) {
      let visual: VisualAsset | null = null;
      let visualError: string | null = null;
      if (row.publication_type === "photo") {
        try { visual = await resolveVisual(row); } catch (error) { visualError = error instanceof Error ? error.message : "visual_resolve_error"; }
      }
      const reasons = validate(row, visual);
      if (visualError) reasons.push("visual_resolver_failed");
      if (reasons.length === 0) {
        try {
          reasons.push(...await revalidateNotion(row));
        } catch {
          reasons.push("notion_revalidation_failed");
        }
      }
      const payloadHash = await sha256Hex(stableHashInput(row, config, visual));

      const item: Record<string, unknown> = {
        publication_id: row.publication_id,
        publication_type: row.publication_type,
        scheduled_at: row.scheduled_at,
        allowed: reasons.length === 0,
        reasons,
        payload_hash: payloadHash,
        visual_asset_key: row.visual_asset_key,
        visual_sha256: visual?.sha256 ?? null,
      };

      if (mode !== "publish") {
        candidates.push(item);
        continue;
      }
      if (!config.enabled || config.dry_run) {
        candidates.push({ ...item, outcome: "publish_blocked_by_config" });
        continue;
      }
      if (!tokenPresent) {
        candidates.push({ ...item, outcome: "telegram_token_missing" });
        continue;
      }
      if (reasons.length) {
        candidates.push({ ...item, outcome: "gate_blocked" });
        continue;
      }

      let claimed = false;
      try {
        claimed = await rpc<boolean>("claim_telegram_publication_queue_v3", {
          p_publication_id: row.publication_id,
          p_payload_hash: payloadHash,
        });
      } catch (error) {
        candidates.push({ ...item, outcome: "claim_error", error_type: error instanceof Error ? error.name : "UnknownError" });
        continue;
      }
      if (!claimed) {
        candidates.push({ ...item, outcome: "claim_rejected" });
        continue;
      }

      let sendResult: Record<string, unknown>;
      try {
        sendResult = await egress(buildEgressPayload(row, config, visual));
      } catch (error) {
        await markUncertain(row.publication_id, `telegram_egress_transport_error:${error instanceof Error ? error.name : "UnknownError"}`);
        candidates.push({ ...item, outcome: "uncertain", reason: "egress_transport_error" });
        continue;
      }
      if (sendResult.ok !== true) {
        await markUncertain(row.publication_id, `telegram_egress_non_ok:http=${String(sendResult._http_status ?? "unknown")}`);
        candidates.push({ ...item, outcome: "uncertain", reason: "egress_non_ok" });
        continue;
      }

      const messageId = extractMessageId(sendResult);
      if (!messageId) {
        await markUncertain(row.publication_id, "telegram_success_without_message_id");
        candidates.push({ ...item, outcome: "uncertain", reason: "message_id_missing" });
        continue;
      }

      try {
        await rpc<void>("mark_telegram_publication_sent_v3", {
          p_publication_id: row.publication_id,
          p_telegram_message_id: messageId,
        });
        candidates.push({ ...item, outcome: "sent", telegram_message_id: messageId });
      } catch {
        try {
          const delivery = await rpc<Record<string, unknown> | null>("get_telegram_publication_delivery", {
            p_publication_id: row.publication_id,
          });
          if (delivery && delivery.state === "sent" && Number(delivery.telegram_message_id) === messageId) {
            candidates.push({ ...item, outcome: "sent_confirmed_after_commit_error", telegram_message_id: messageId });
          } else {
            await markUncertain(row.publication_id, "telegram_sent_but_database_commit_ambiguous");
            candidates.push({ ...item, outcome: "uncertain", telegram_message_id: messageId, reason: "database_commit_ambiguous" });
          }
        } catch {
          await markUncertain(row.publication_id, "telegram_sent_database_reconciliation_unavailable");
          candidates.push({ ...item, outcome: "uncertain", telegram_message_id: messageId, reason: "database_reconciliation_unavailable" });
        }
      }
    }

    return json({
      ok: true,
      mode,
      enabled: config.enabled,
      dry_run: config.dry_run,
      token_present: tokenPresent,
      due_count: rows.length,
      candidates,
    });
  } catch (error) {
    return json({
      ok: false,
      error: "publisher_internal_error",
      error_type: error instanceof Error ? error.name : "UnknownError",
    }, 500);
  }
});
