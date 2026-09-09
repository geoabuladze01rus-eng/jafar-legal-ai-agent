import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ALLOWED_CHAT_IDS = new Set(["-1004412524447", "8999343417"]);

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function headers() {
  return {
    authorization: `Bearer ${SERVICE_KEY}`,
    apikey: SERVICE_KEY,
    "content-type": "application/json",
  };
}

async function rpc<T>(name: string): Promise<T> {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: headers(),
    body: "{}",
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`rpc_${name}_${response.status}`);
  return await response.json() as T;
}

function constantTimeEqual(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function authorized(req: Request): Promise<boolean> {
  const supplied = req.headers.get("x-jafar-worker-secret")?.trim() ?? "";
  const expectedRaw = await rpc<unknown>("get_jafar_worker_secret_for_publisher");
  const expected = typeof expectedRaw === "string" ? expectedRaw.trim() : "";
  return constantTimeEqual(supplied, expected);
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
  const chatId = String(body.chat_id ?? "-1004412524447");
  if (!ALLOWED_CHAT_IDS.has(chatId)) return json({ ok: false, error: "chat_not_allowed" }, 403);

  let tokenRaw: unknown;
  try {
    tokenRaw = await rpc<unknown>("get_telegram_bot_token_for_egress");
  } catch {
    return json({ ok: false, error: "telegram_token_unavailable" }, 503);
  }
  const token = typeof tokenRaw === "string" ? tokenRaw.trim() : "";
  if (!token || token.length < 20 || /\s/.test(token)) return json({ ok: false, error: "telegram_token_invalid" }, 503);

  try {
    const meResponse = await fetch(`https://api.telegram.org/bot${token}/getMe`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
      signal: AbortSignal.timeout(12000),
    });
    const meBody = await meResponse.json();
    const botId = Number(meBody?.result?.id);
    if (!meResponse.ok || meBody?.ok !== true || !Number.isInteger(botId) || botId <= 0) {
      return json({ ok: false, error: "getme_failed", telegram_status: meResponse.status }, 502);
    }

    const memberResponse = await fetch(`https://api.telegram.org/bot${token}/getChatMember`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, user_id: botId }),
      signal: AbortSignal.timeout(12000),
    });
    const memberBody = await memberResponse.json();
    if (!memberResponse.ok || memberBody?.ok !== true) {
      return json({ ok: false, error: "getchatmember_failed", telegram_status: memberResponse.status }, 502);
    }

    const member = memberBody.result ?? {};
    return json({
      ok: true,
      chat_id: chatId,
      bot: {
        id: botId,
        username: typeof meBody?.result?.username === "string" ? meBody.result.username : null,
        first_name: typeof meBody?.result?.first_name === "string" ? meBody.result.first_name : null,
      },
      membership: {
        status: typeof member.status === "string" ? member.status : null,
        can_post_messages: member.can_post_messages === true,
        can_edit_messages: member.can_edit_messages === true,
        can_delete_messages: member.can_delete_messages === true,
      },
    });
  } catch (error) {
    return json({
      ok: false,
      error: "telegram_access_probe_transport_error",
      error_type: error instanceof Error ? error.name : "UnknownError",
    }, 502);
  }
});
