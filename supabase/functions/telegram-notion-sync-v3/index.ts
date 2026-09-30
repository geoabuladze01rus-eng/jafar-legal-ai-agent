import "jsr:@supabase/functions-js/edge-runtime.d.ts";

type SyncConfig = {
  enabled: boolean;
  dry_run: boolean;
  data_source_id: string;
  batch_size: number;
};

type NotionPage = {
  id: string;
  properties: Record<string, any>;
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
  if (!response.ok) throw new Error(`rpc_${name}_${response.status}`);
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

async function getSecret(name: string): Promise<string> {
  const value = await rpc<unknown>(name, {});
  return typeof value === "string" ? value.trim() : "";
}

async function authorized(req: Request): Promise<boolean> {
  const supplied = req.headers.get("x-jafar-worker-secret")?.trim() ?? "";
  if (!supplied) return false;
  const expected = await getSecret("get_jafar_worker_secret_for_publisher");
  if (!expected || supplied.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < supplied.length; i++) {
    diff |= supplied.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
}

async function fetchConfig(): Promise<SyncConfig> {
  const response = await fetch(
    `${SUPABASE_URL}/rest/v1/telegram_notion_sync_config?id=eq.1&select=enabled,dry_run,data_source_id,batch_size`,
    { headers: serviceHeaders(), signal: AbortSignal.timeout(10000) },
  );
  if (!response.ok) throw new Error(`sync_config_fetch_${response.status}`);
  const rows = await response.json();
  if (!Array.isArray(rows) || !rows.length) throw new Error("sync_config_missing");
  return rows[0] as SyncConfig;
}

function richText(prop: any): string {
  const arr = Array.isArray(prop?.rich_text) ? prop.rich_text : [];
  return arr
    .map((x: any) => typeof x?.plain_text === "string" ? x.plain_text : "")
    .join("")
    .trim();
}

function selectName(prop: any): string {
  return typeof prop?.select?.name === "string" ? prop.select.name.trim() : "";
}

function statusName(prop: any): string {
  return typeof prop?.status?.name === "string" ? prop.status.name.trim() : "";
}

function checkboxValue(prop: any): boolean {
  return prop?.checkbox === true;
}

function numberValue(prop: any): number | null {
  return typeof prop?.number === "number" && Number.isFinite(prop.number) ? prop.number : null;
}

function dateStart(prop: any): string {
  return typeof prop?.date?.start === "string" ? prop.date.start : "";
}

function parseArrayText(value: string): unknown[] {
  const raw = value.trim();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [raw];
  } catch {
    return [raw];
  }
}

function parseOptions(value: string): unknown[] {
  const raw = value.trim();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function parseCorrectIds(value: string, legacy: number | null): number[] {
  const raw = value.trim();
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.map(Number).filter((x) => Number.isInteger(x));
      }
    } catch {
      return [];
    }
  }
  return Number.isInteger(legacy) ? [Number(legacy)] : [];
}

function notionRow(page: NotionPage) {
  const p = page.properties ?? {};
  const publicationId = richText(p["Publication ID"]);
  const publicationType = selectName(p["Publication Type"]);
  const scheduledAt = dateStart(p["Publish Date"]);
  const fingerprint = richText(p["Content Fingerprint"]);
  const deliveryState = selectName(p["Delivery State"]);
  const reconciliationRequired = checkboxValue(p["Reconciliation Required"]);
  const telegramMessageId = numberValue(p["Telegram Message ID"]);
  const visualRequired = checkboxValue(p["Visual Required"]);

  const row = {
    publication_id: publicationId,
    status: statusName(p["Status"]),
    publication_type: publicationType,
    scheduled_at: scheduledAt,
    content: richText(p["Content"]),
    caption: richText(p["Caption"]),
    question: richText(p["Question"]),
    options: parseOptions(richText(p["Options JSON"])),
    correct_option_ids: parseCorrectIds(
      richText(p["Correct Option IDs JSON"]),
      numberValue(p["Correct Option ID"]),
    ),
    explanation: richText(p["Explanation"]),
    visual_asset_key: richText(p["Visual Asset Key"]),
    visual_category: selectName(p["Visual Category"]) || richText(p["Visual Category"]),
    fact_check_status: selectName(p["Fact Check Status"]),
    legal_risk: selectName(p["Legal Risk"]),
    privacy_risk: selectName(p["Privacy Risk"]),
    current_case_risk: checkboxValue(p["Current Case Risk"]),
    editorial_blockers: parseArrayText(richText(p["Editorial Blockers"])),
    content_fingerprint: fingerprint,
  };

  const reasons: string[] = [];
  if (selectName(p["Platform"]) !== "Telegram") reasons.push("platform_not_telegram");
  if (["Ready", "Scheduled"].includes(row.status) === false) reasons.push("status_not_scheduled");
  if (!publicationId) reasons.push("publication_id_missing");
  if (!["text", "photo", "poll", "quiz"].includes(publicationType)) {
    reasons.push("publication_type_invalid");
  }
  if (!scheduledAt) reasons.push("publish_date_missing");
  if (!HEX64.test(fingerprint)) reasons.push("content_fingerprint_invalid");
  if (deliveryState !== "pending") reasons.push("delivery_state_not_pending");
  if (reconciliationRequired) reasons.push("reconciliation_required");
  if (telegramMessageId !== null) reasons.push("already_has_telegram_message_id");
  if (!["verified", "not_required"].includes(row.fact_check_status)) {
    reasons.push("fact_check_not_verified");
  }
  if (row.legal_risk !== "low") reasons.push("legal_risk_not_low");
  if (row.privacy_risk !== "low") reasons.push("privacy_risk_not_low");
  if (row.current_case_risk) reasons.push("current_case_risk");
  if (!Array.isArray(row.editorial_blockers) || row.editorial_blockers.length) {
    reasons.push("editorial_blockers_present");
  }
  if (visualRequired && publicationType !== "photo") reasons.push("visual_required_but_not_photo");
  if (publicationType === "photo") {
    if (!row.visual_asset_key) reasons.push("visual_asset_key_missing");
    if (!row.visual_category) reasons.push("visual_category_missing");
  }

  return { page_id: page.id, publication_id: publicationId, row, reasons };
}

async function notionQueryReady(token: string, dataSourceId: string, limit: number): Promise<NotionPage[]> {
  const response = await fetch(`https://api.notion.com/v1/data_sources/${dataSourceId}/query`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "notion-version": "2025-09-03",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      filter: {
        and: [
          { property: "Platform", select: { equals: "Telegram" } },
          {
            or: [
              { property: "Status", status: { equals: "Ready" } },
              { property: "Status", status: { equals: "Scheduled" } },
            ],
          },
        ],
      },
      sorts: [{ property: "Publish Date", direction: "ascending" }],
      page_size: Math.max(1, Math.min(limit, 100)),
    }),
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`notion_query_${response.status}`);
  const body = await response.json();
  return Array.isArray(body?.results) ? body.results as NotionPage[] : [];
}

function richTextValue(value: string | null) {
  if (!value) return { rich_text: [] };
  return {
    rich_text: [{ type: "text", text: { content: value.slice(0, 1900) } }],
  };
}

async function notionWriteback(token: string, candidate: Record<string, unknown>) {
  const pageId = String(candidate.source_notion_page_id ?? "");
  const status = String(candidate.status ?? "");
  const deliveryState = String(candidate.delivery_state ?? "");
  const properties: Record<string, unknown> = {
    Status: { status: { name: status } },
    "Delivery State": { select: { name: deliveryState } },
    "Reconciliation Required": { checkbox: Boolean(candidate.reconciliation_required) },
  };

  const payloadHash = typeof candidate.delivery_payload_hash === "string"
    ? candidate.delivery_payload_hash
    : "";
  if (payloadHash) properties["Delivery Payload Hash"] = richTextValue(payloadHash);

  const messageId = Number(candidate.telegram_message_id);
  if (Number.isInteger(messageId) && messageId > 0) {
    properties["Telegram Message ID"] = { number: messageId };
  }

  if (typeof candidate.published_at === "string" && candidate.published_at) {
    properties["Published At"] = { date: { start: candidate.published_at } };
  }

  const lastError = typeof candidate.last_error === "string" ? candidate.last_error : "";
  properties["Last Error"] = richTextValue(lastError);

  const response = await fetch(`https://api.notion.com/v1/pages/${pageId}`, {
    method: "PATCH",
    headers: {
      authorization: `Bearer ${token}`,
      "notion-version": "2025-09-03",
      "content-type": "application/json",
    },
    body: JSON.stringify({ properties }),
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`notion_writeback_${response.status}`);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return json({ ok: false, error: "supabase_runtime_missing" }, 500);
  }

  try {
    if (!(await authorized(req))) return json({ ok: false, error: "unauthorized" }, 401);
  } catch {
    return json({ ok: false, error: "worker_auth_unavailable" }, 503);
  }

  let body: Record<string, unknown> = {};
  try { body = await req.json(); } catch { body = {}; }
  const mode = body.mode === "sync" ? "sync" : "preflight";

  try {
    const config = await fetchConfig();
    const requested = Number(body.limit ?? config.batch_size ?? 50);
    const limit = Math.max(1, Math.min(Number.isInteger(requested) ? requested : 50, 100));
    const notionToken = await getSecret("get_notion_token_for_sync");
    if (!notionToken) return json({ ok: false, error: "notion_token_missing" }, 503);

    const pages = await notionQueryReady(notionToken, config.data_source_id, limit);
    const parsed = pages.map(notionRow);
    const result: Record<string, unknown> = {
      ok: true,
      mode,
      enabled: config.enabled,
      dry_run: config.dry_run,
      ready_count: pages.length,
      candidates: parsed.map((x) => ({
        publication_id: x.publication_id,
        page_id: x.page_id,
        allowed: x.reasons.length === 0,
        reasons: x.reasons,
      })),
      upserts: [],
      writebacks: [],
    };

    if (mode !== "sync" || !config.enabled || config.dry_run) return json(result);

    const upserts: Record<string, unknown>[] = [];
    for (const item of parsed) {
      if (item.reasons.length) {
        upserts.push({ publication_id: item.publication_id, outcome: "blocked", reasons: item.reasons });
        continue;
      }
      try {
        const outcome = await rpc<string>("upsert_telegram_publication_from_notion_v3", {
          p_page_id: item.page_id,
          p_row: item.row,
        });
        upserts.push({ publication_id: item.publication_id, outcome });
      } catch (error) {
        upserts.push({
          publication_id: item.publication_id,
          outcome: "upsert_error",
          error_type: error instanceof Error ? error.name : "UnknownError",
        });
      }
    }

    const writebackRows = await rpc<Record<string, unknown>[]>(
      "get_telegram_notion_writeback_candidates_v3",
      { p_limit: limit },
    );
    const writebacks: Record<string, unknown>[] = [];
    for (const candidate of Array.isArray(writebackRows) ? writebackRows : []) {
      const publicationId = String(candidate.publication_id ?? "");
      try {
        await notionWriteback(notionToken, candidate);
        await rpc<void>("mark_telegram_notion_synced_v3", {
          p_publication_id: publicationId,
        });
        writebacks.push({
          publication_id: publicationId,
          outcome: "synced",
          status: candidate.status,
          delivery_state: candidate.delivery_state,
        });
      } catch (error) {
        try {
          await rpc<void>("mark_telegram_notion_sync_error_v3", {
            p_publication_id: publicationId,
            p_error: `notion_writeback:${error instanceof Error ? error.message : "UnknownError"}`,
          });
        } catch {}
        writebacks.push({
          publication_id: publicationId,
          outcome: "writeback_error",
          error_type: error instanceof Error ? error.name : "UnknownError",
        });
      }
    }

    result.upserts = upserts;
    result.writebacks = writebacks;
    return json(result);
  } catch (error) {
    return json({
      ok: false,
      error: "notion_sync_internal_error",
      error_type: error instanceof Error ? error.name : "UnknownError",
    }, 500);
  }
});
