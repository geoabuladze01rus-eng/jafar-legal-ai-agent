import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const ALLOWED_CHAT_IDS = new Set(["8999343417", "-1004412524447"]);
const ALLOWED_ACTIONS = new Set(["probe", "sendMessage", "sendPhoto", "sendVideo", "sendPoll"]);

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
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

async function tokenFromVault(): Promise<string> {
  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (!url || !serviceKey) return "";

  try {
    const response = await fetch(`${url}/rest/v1/rpc/get_telegram_bot_token_for_egress`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${serviceKey}`,
        apikey: serviceKey,
        "content-type": "application/json",
      },
      body: "{}",
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) return "";
    const value = await response.json();
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

function normalizeCorrectOptionIds(
  body: Record<string, unknown>,
  optionCount: number,
): number[] {
  const raw = Array.isArray(body.correct_option_ids)
    ? body.correct_option_ids
    : body.correct_option_id !== undefined && body.correct_option_id !== null
      ? [body.correct_option_id]
      : [];

  const ids = raw.map(Number);
  if (
    ids.length === 0
    || ids.some((id) => !Number.isInteger(id) || id < 0 || id >= optionCount)
    || new Set(ids).size !== ids.length
  ) {
    return [];
  }
  return ids.sort((a, b) => a - b);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400);
  }

  const action = String(body.action ?? "");
  if (!ALLOWED_ACTIONS.has(action)) return json({ ok: false, error: "action_not_allowed" }, 400);

  if (action === "probe") {
    const started = Date.now();
    try {
      const response = await fetch("https://api.telegram.org", {
        method: "GET",
        redirect: "manual",
        signal: AbortSignal.timeout(8000),
        headers: { "User-Agent": "JAFAR-Telegram-Egress-Probe/2.0" },
      });
      return json({
        ok: response.status >= 200 && response.status < 500,
        telegram_reachable: true,
        telegram_status: response.status,
        elapsed_ms: Date.now() - started,
      });
    } catch (error) {
      return json({
        ok: false,
        telegram_reachable: false,
        error_type: error instanceof Error ? error.name : "UnknownError",
        elapsed_ms: Date.now() - started,
      }, 502);
    }
  }

  let token = req.headers.get("x-telegram-bot-token")?.trim() ?? "";
  if (!token) token = await tokenFromVault();
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
      if (typeof body.parse_mode === "string" && body.parse_mode) {
        payload.parse_mode = body.parse_mode;
      }

      telegramResponse = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(20000),
      });
    } else if (action === "sendPoll") {
      const question = requireString(body.question, "question");
      const options = normalizePollOptions(body.options);
      if (options.length < 2 || options.length > 12 || options.some((x) => !x)) {
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
        const correctIds = normalizeCorrectOptionIds(body, options.length);
        if (!correctIds.length) {
          return json({ ok: false, error: "invalid_correct_option_ids" }, 400);
        }
        payload.correct_option_ids = correctIds;
        if (typeof body.explanation === "string" && body.explanation.trim()) {
          payload.explanation = body.explanation.trim();
        }
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
      const isPhoto = action === "sendPhoto";
      const mediaField = isPhoto ? "photo" : "video";
      const urlKey = isPhoto ? "photo_url" : "video_url";
      const b64Key = isPhoto ? "photo_base64" : "video_base64";
      const filename = typeof body.filename === "string" && body.filename.trim()
        ? body.filename.trim()
        : isPhoto ? "image.jpg" : "video.mp4";

      const caption = typeof body.caption === "string" ? body.caption : "";
      const mediaUrl = typeof body[urlKey] === "string" ? String(body[urlKey]) : "";
      const mediaB64 = typeof body[b64Key] === "string" ? String(body[b64Key]) : "";
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
        form.set(mediaField, mediaUrl);
      } else {
        const bytes = decodeBase64(mediaB64);
        const maxBytes = isPhoto ? 10 * 1024 * 1024 : 20 * 1024 * 1024;
        if (bytes.byteLength === 0 || bytes.byteLength > maxBytes) {
          return json({ ok: false, error: "media_size_invalid" }, 400);
        }
        const mime = isPhoto
          ? filename.toLowerCase().endsWith(".png")
            ? "image/png"
            : filename.toLowerCase().endsWith(".webp")
              ? "image/webp"
              : "image/jpeg"
          : "video/mp4";
        form.set(mediaField, new Blob([bytes], { type: mime }), filename);
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

  let telegramBody: unknown = null;
  try {
    telegramBody = await telegramResponse.json();
  } catch {
    telegramBody = { ok: false, description: "non_json_telegram_response" };
  }

  return json({
    ok: telegramResponse.ok,
    telegram_status: telegramResponse.status,
    telegram: telegramBody,
  }, telegramResponse.ok ? 200 : 502);
});