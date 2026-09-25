import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ALLOWED_CHAT_IDS = new Set(["8999343417", "-1004412524447"]);
const ALLOWED_ACTIONS = new Set(["sendMessage", "sendPhoto", "sendPoll"]);
const ALLOWED_PHOTO_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

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
  const supplied = req.headers.get("authorization")?.trim() ?? "";
  return constantTimeEqual(supplied, `Bearer ${SERVICE_KEY}`);
}

function requireString(value: unknown, name: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${name}_required`);
  return value;
}

function decodeBase64(value: string): Uint8Array {
  const binary = atob(value);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

async function rpc<T>(name: string, body: Record<string, unknown>): Promise<T> {
  if (!SUPABASE_URL || !SERVICE_KEY) throw new Error("supabase_runtime_missing");
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${SERVICE_KEY}`,
      apikey: SERVICE_KEY,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`rpc_${name}_${response.status}`);
  return await response.json() as T;
}

async function tokenFromVault(): Promise<string> {
  try {
    const value = await rpc<unknown>("get_telegram_bot_token_for_egress", {});
    return typeof value === "string" ? value.trim() : "";
  } catch {
    return "";
  }
}

function normalizePollOptions(value: unknown): string[] {
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

function normalizeCorrectOptionIds(body: Record<string, unknown>, optionCount: number): number[] {
  const raw = Array.isArray(body.correct_option_ids) ? body.correct_option_ids : [];

  const ids = raw.map(Number);
  if (
    ids.length === 0 ||
    ids.some((id) => !Number.isInteger(id) || id < 0 || id >= optionCount) ||
    new Set(ids).size !== ids.length
  ) {
    return [];
  }
  return ids.sort((a, b) => a - b);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
  if (!internalAuthorized(req)) return json({ ok: false, error: "internal_authorization_required" }, 403);

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }

  const action = String(body.action ?? "");
  if (!ALLOWED_ACTIONS.has(action)) return json({ ok: false, error: "action_not_allowed" }, 400);

  const token = await tokenFromVault();
  if (!token || token.length < 20 || /\s/.test(token)) {
    return json({ ok: false, error: "telegram_token_missing" }, 401);
  }

  const chatId = String(body.chat_id ?? "");
  if (!ALLOWED_CHAT_IDS.has(chatId)) return json({ ok: false, error: "chat_not_allowed" }, 403);

  const endpoint = `https://api.telegram.org/bot${token}/${action}`;
  let telegramResponse: Response;

  try {
    if (action === "sendMessage") {
      const text = requireString(body.text, "text");
      const payload: Record<string, unknown> = {
        chat_id: chatId,
        text,
        disable_web_page_preview: Boolean(body.disable_web_page_preview ?? false),
      };
      if (typeof body.parse_mode === "string" && body.parse_mode) payload.parse_mode = body.parse_mode;

      telegramResponse = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(20000),
      });
    } else if (action === "sendPoll") {
      const question = requireString(body.question, "question");
      const options = normalizePollOptions(body.options);
      if (question.length > 300) return json({ ok: false, error: "poll_question_too_long" }, 400);
      if (
        options.length < 2 || options.length > 12 ||
        options.some((x) => !x || x.length > 100)
      ) {
        return json({ ok: false, error: "invalid_poll_options" }, 400);
      }

      const type = body.type === "quiz" ? "quiz" : "regular";
      const payload: Record<string, unknown> = {
        chat_id: chatId,
        question,
        options: options.map((text) => ({ text })),
        type,
        is_anonymous: body.is_anonymous !== false,
        allows_multiple_answers: Boolean(body.allows_multiple_answers ?? false),
      };

      if (type === "quiz") {
        if (body.allows_multiple_answers === true) {
          return json({ ok: false, error: "quiz_multiple_answers_not_supported" }, 400);
        }
        const correctIds = normalizeCorrectOptionIds(body, options.length);
        if (!correctIds.length) return json({ ok: false, error: "invalid_correct_option_ids" }, 400);
        payload.correct_option_ids = correctIds;
        if (typeof body.explanation === "string" && body.explanation.trim()) {
          const explanation = body.explanation.trim();
          if (explanation.length > 200 || (explanation.match(/\n/g) ?? []).length > 2) {
            return json({ ok: false, error: "invalid_quiz_explanation" }, 400);
          }
          payload.explanation = explanation;
        }
      } else if (Array.isArray(body.correct_option_ids) && body.correct_option_ids.length) {
        return json({ ok: false, error: "regular_poll_has_correct_option_ids" }, 400);
      }

      if (body.open_period !== undefined && body.open_period !== null) {
        const value = Number(body.open_period);
        if (!Number.isInteger(value) || value < 5 || value > 2628000) {
          return json({ ok: false, error: "invalid_open_period" }, 400);
        }
        payload.open_period = value;
      }
      if (body.close_date !== undefined && body.close_date !== null) {
        const value = Number(body.close_date);
        if (!Number.isInteger(value) || value <= 0) {
          return json({ ok: false, error: "invalid_close_date" }, 400);
        }
        payload.close_date = value;
      }

      telegramResponse = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(20000),
      });
    } else {
      const filename = typeof body.filename === "string" && body.filename.trim()
        ? body.filename.trim()
        : "image.jpg";

      const caption = typeof body.caption === "string" ? body.caption : "";
      if (caption.length > 1024) return json({ ok: false, error: "caption_too_long" }, 400);
      const mediaUrl = typeof body.photo_url === "string" ? body.photo_url.trim() : "";
      const mediaB64 = typeof body.photo_base64 === "string" ? body.photo_base64 : "";
      if (!!mediaUrl === !!mediaB64) {
        return json({ ok: false, error: "provide_exactly_one_media_source" }, 400);
      }

      const form = new FormData();
      form.set("chat_id", chatId);
      if (caption) form.set("caption", caption);
      if (typeof body.parse_mode === "string" && body.parse_mode) {
        form.set("parse_mode", String(body.parse_mode));
      }

      if (mediaUrl) {
        let parsed: URL;
        try { parsed = new URL(mediaUrl); } catch { return json({ ok: false, error: "photo_url_invalid" }, 400); }
        if (parsed.protocol !== "https:") return json({ ok: false, error: "photo_url_invalid" }, 400);
        form.set("photo", mediaUrl);
      } else {
        const mime = typeof body.mime_type === "string" ? body.mime_type.trim().toLowerCase() : "";
        if (!ALLOWED_PHOTO_MIME_TYPES.has(mime)) {
          return json({ ok: false, error: "photo_mime_invalid" }, 400);
        }
        let bytes: Uint8Array;
        try { bytes = decodeBase64(mediaB64); } catch {
          return json({ ok: false, error: "photo_base64_invalid" }, 400);
        }
        if (bytes.byteLength === 0 || bytes.byteLength > 10 * 1024 * 1024) {
          return json({ ok: false, error: "media_size_invalid" }, 400);
        }
        form.set("photo", new Blob([bytes], { type: mime }), filename);
      }

      telegramResponse = await fetch(endpoint, {
        method: "POST",
        body: form,
        signal: AbortSignal.timeout(60000),
      });
    }
  } catch (error) {
    return json({
      ok: false,
      error: "telegram_transport_error",
      error_type: error instanceof Error ? error.name : "UnknownError",
    }, 502);
  }

  let telegramMessageId: number | null = null;
  try {
    const body = await telegramResponse.json() as Record<string, unknown>;
    const result = body?.result;
    const rawId = result && typeof result === "object"
      ? Number((result as Record<string, unknown>).message_id)
      : NaN;
    if (Number.isInteger(rawId) && rawId > 0) telegramMessageId = rawId;
  } catch {}

  return json({
    ok: telegramResponse.ok && telegramMessageId !== null,
    telegram_status: telegramResponse.status,
    telegram_message_id: telegramMessageId,
  }, telegramResponse.ok ? 200 : 502);
});
