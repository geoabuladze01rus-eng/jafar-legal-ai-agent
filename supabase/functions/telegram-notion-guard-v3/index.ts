import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

type Expected = {
  publication_id: string;
  source_notion_page_id: string;
  publication_type: string;
  scheduled_at: string;
  content: string;
  caption?: string | null;
  question?: string | null;
  options?: unknown;
  correct_option_ids?: unknown;
  explanation?: string | null;
  visual_asset_key?: string | null;
  visual_category?: string | null;
  fact_check_status: string;
  legal_risk: string;
  privacy_risk: string;
  current_case_risk: boolean;
  editorial_blockers?: unknown;
  content_fingerprint: string;
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
function constantTimeEqual(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
function internalAuthorized(req: Request): boolean {
  if (!SERVICE_KEY) return false;
  return constantTimeEqual(req.headers.get("authorization")?.trim() ?? "", `Bearer ${SERVICE_KEY}`);
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
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`rpc_${name}_${response.status}`);
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}
function richText(prop: any): string {
  const arr = Array.isArray(prop?.rich_text) ? prop.rich_text : [];
  return arr.map((x: any) => typeof x?.plain_text === "string" ? x.plain_text : "").join("").trim();
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
function parseOptions(value: string): string[] {
  const raw = value.trim();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map((item: any) => {
      if (typeof item === "string") return item.trim();
      if (item && typeof item === "object" && typeof item.text === "string") return item.text.trim();
      return "";
    });
  } catch {
    return [];
  }
}
function normalizeOptions(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item: any) => {
    if (typeof item === "string") return item.trim();
    if (item && typeof item === "object" && typeof item.text === "string") return item.text.trim();
    return "";
  });
}
function parseCorrectIds(value: string, legacy: number | null): number[] {
  const raw = value.trim();
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed.map(Number).filter((x) => Number.isInteger(x));
    } catch {
      return [];
    }
  }
  return Number.isInteger(legacy) ? [Number(legacy)] : [];
}
function normalizeCorrectIds(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.map(Number).filter((x) => Number.isInteger(x));
}
function sameArray(a: unknown[], b: unknown[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
function sameInstant(a: string, b: string): boolean {
  const x = Date.parse(a);
  const y = Date.parse(b);
  return Number.isFinite(x) && Number.isFinite(y) && x === y;
}
async function notionPage(token: string, pageId: string): Promise<any> {
  const response = await fetch(`https://api.notion.com/v1/pages/${pageId}`, {
    method: "GET",
    headers: {
      authorization: `Bearer ${token}`,
      "notion-version": "2025-09-03",
      "content-type": "application/json",
    },
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`notion_page_${response.status}`);
  return await response.json();
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
  if (!SUPABASE_URL || !SERVICE_KEY) return json({ ok: false, error: "supabase_runtime_missing" }, 500);
  if (!internalAuthorized(req)) return json({ ok: false, error: "internal_authorization_required" }, 403);

  let expected: Expected;
  try {
    expected = await req.json() as Expected;
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }
  if (!expected?.publication_id || !expected?.source_notion_page_id) {
    return json({ ok: true, allowed: false, reasons: ["notion_source_missing"] });
  }

  try {
    const tokenRaw = await rpc<unknown>("get_notion_token_for_sync", {});
    const token = typeof tokenRaw === "string" ? tokenRaw.trim() : "";
    if (!token) return json({ ok: true, allowed: false, reasons: ["notion_token_missing"] });

    const page = await notionPage(token, expected.source_notion_page_id);
    const p = page?.properties ?? {};
    const reasons: string[] = [];

    const platform = selectName(p["Platform"]);
    const status = statusName(p["Status"]);
    const publicationId = richText(p["Publication ID"]);
    const publicationType = selectName(p["Publication Type"]);
    const publishDate = dateStart(p["Publish Date"]);
    const fingerprint = richText(p["Content Fingerprint"]);
    const deliveryState = selectName(p["Delivery State"]);
    const reconciliation = checkboxValue(p["Reconciliation Required"]);
    const messageId = numberValue(p["Telegram Message ID"]);
    const factStatus = selectName(p["Fact Check Status"]);
    const legalRisk = selectName(p["Legal Risk"]);
    const privacyRisk = selectName(p["Privacy Risk"]);
    const currentCaseRisk = checkboxValue(p["Current Case Risk"]);
    const blockers = parseArrayText(richText(p["Editorial Blockers"]));
    const visualRequired = checkboxValue(p["Visual Required"]);

    if (platform !== "Telegram") reasons.push("notion_platform_not_telegram");
    if (["Ready", "Scheduled"].includes(status) === false) reasons.push("notion_status_not_scheduled");
    if (publicationId !== expected.publication_id) reasons.push("notion_publication_id_mismatch");
    if (publicationType !== expected.publication_type) reasons.push("notion_publication_type_mismatch");
    if (!sameInstant(publishDate, expected.scheduled_at)) reasons.push("notion_publish_date_mismatch");
    if (fingerprint !== expected.content_fingerprint) reasons.push("notion_fingerprint_mismatch");
    if (deliveryState !== "pending") reasons.push("notion_delivery_state_not_pending");
    if (reconciliation) reasons.push("notion_reconciliation_required");
    if (messageId !== null) reasons.push("notion_already_has_message_id");
    if (factStatus !== expected.fact_check_status || !["verified", "not_required"].includes(factStatus)) reasons.push("notion_fact_check_mismatch");
    if (legalRisk !== expected.legal_risk || legalRisk !== "low") reasons.push("notion_legal_risk_mismatch");
    if (privacyRisk !== expected.privacy_risk || privacyRisk !== "low") reasons.push("notion_privacy_risk_mismatch");
    if (currentCaseRisk !== expected.current_case_risk || currentCaseRisk) reasons.push("notion_current_case_risk");
    if (blockers.length) reasons.push("notion_editorial_blockers_present");
    if (visualRequired && expected.publication_type !== "photo") reasons.push("notion_visual_required_but_not_photo");

    if (richText(p["Content"]) !== (expected.content ?? "").trim()) reasons.push("notion_content_mismatch");
    if (richText(p["Caption"]) !== (expected.caption ?? "").trim()) reasons.push("notion_caption_mismatch");
    if (richText(p["Question"]) !== (expected.question ?? "").trim()) reasons.push("notion_question_mismatch");
    if (richText(p["Explanation"]) !== (expected.explanation ?? "").trim()) reasons.push("notion_explanation_mismatch");
    if (richText(p["Visual Asset Key"]) !== (expected.visual_asset_key ?? "").trim()) reasons.push("notion_visual_asset_key_mismatch");
    const notionCategory = selectName(p["Visual Category"]) || richText(p["Visual Category"]);
    if (notionCategory !== (expected.visual_category ?? "").trim()) reasons.push("notion_visual_category_mismatch");

    const notionOptions = parseOptions(richText(p["Options JSON"]));
    const queueOptions = normalizeOptions(expected.options);
    if (!sameArray(notionOptions, queueOptions)) reasons.push("notion_options_mismatch");
    const notionCorrect = parseCorrectIds(richText(p["Correct Option IDs JSON"]), numberValue(p["Correct Option ID"]));
    const queueCorrect = normalizeCorrectIds(expected.correct_option_ids);
    if (!sameArray(notionCorrect, queueCorrect)) reasons.push("notion_correct_option_ids_mismatch");

    return json({ ok: true, allowed: reasons.length === 0, reasons });
  } catch (error) {
    return json({
      ok: false,
      allowed: false,
      error: "notion_revalidation_unavailable",
      error_type: error instanceof Error ? error.name : "UnknownError",
    }, 503);
  }
});