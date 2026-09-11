import "jsr:@supabase/functions-js/edge-runtime.d.ts";

type EditorialPlan = {
  plan_id: string;
  slot_key: string;
  scheduled_at: string;
  publication_type: "photo" | "quiz";
  theme: string;
  prompt_context: string;
};

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY") ?? "";

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
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`rpc_${name}_${response.status}`);
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

async function authorized(req: Request): Promise<boolean> {
  const supplied = req.headers.get("x-jafar-worker-secret")?.trim() ?? "";
  if (!supplied) return false;
  const expected = (await rpc<unknown>("get_jafar_worker_secret_for_publisher", {}));
  const secret = typeof expected === "string" ? expected.trim() : "";
  if (!secret || supplied.length !== secret.length) return false;

  let diff = 0;
  for (let index = 0; index < supplied.length; index++) {
    diff |= supplied.charCodeAt(index) ^ secret.charCodeAt(index);
  }
  return diff === 0;
}

async function fetchDuePlans(limit: number): Promise<EditorialPlan[]> {
  const now = encodeURIComponent(new Date().toISOString());
  const url = `${SUPABASE_URL}/rest/v1/jafar_editorial_plan` +
    `?status=eq.pending&scheduled_at=lte.${now}` +
    `&order=scheduled_at.asc,plan_id.asc&limit=${limit}`;
  const response = await fetch(url, {
    headers: serviceHeaders(),
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`plan_fetch_${response.status}`);
  return await response.json() as EditorialPlan[];
}

async function markPlanError(planId: string, code: string): Promise<void> {
  await fetch(
    `${SUPABASE_URL}/rest/v1/jafar_editorial_plan?plan_id=eq.${encodeURIComponent(planId)}&status=eq.pending`,
    {
      method: "PATCH",
      headers: { ...serviceHeaders(), prefer: "return=minimal" },
      body: JSON.stringify({
        status: "error",
        attempt_count: 1,
        last_error: code.slice(0, 120),
      }),
      signal: AbortSignal.timeout(15000),
    },
  );
}

function textPrompt(plan: EditorialPlan): string {
  const quiz = plan.publication_type === "quiz";
  return [
    "Подготовь одну текстовую публикацию для российского Telegram-канала юридической практики JAFAR.",
    `Тема слота: ${plan.theme}`,
    `Контекст редакционного плана: ${plan.prompt_context}`,
    "Пиши на русском, спокойно и понятно, без персональной юридической консультации.",
    "Используй только общеобразовательные и evergreen-формулировки; не придумывай номера дел, статистику, цитаты и актуальные события.",
    "Не включай реальные имена, телефоны, адреса, документы, персональные данные или инструкции по обходу закона.",
    "Отделяй общую информацию от мнения и добавь короткий практический вывод.",
    quiz
      ? "Это квиз: подготовь ровно 4 коротких варианта ответа, один правильный, correct_option_ids — массив с одним zero-based индексом."
      : "Это экспертный текстовый материал с сильным заголовком и полезным объяснением. Добавь 2–5 уместных эмодзи, не перегружай ими текст.",
    "Верни только валидный JSON без markdown и без дополнительных полей:",
    JSON.stringify({
      content: "текст публикации 500-1200 знаков",
      caption: "оставь пустым — визуализация отключена",
      question: quiz ? "вопрос квиза до 180 знаков" : "",
      options: quiz ? ["вариант 1", "вариант 2", "вариант 3", "вариант 4"] : [],
      correct_option_ids: quiz ? [0] : [],
      explanation: quiz ? "короткое объяснение правильного ответа" : "",
    }),
  ].join("\n");
}

async function generateText(plan: EditorialPlan): Promise<Record<string, unknown>> {
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      authorization: `Bearer ${OPENAI_API_KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-5-mini",
      messages: [
        {
          role: "system",
          content: "Ты аккуратный редактор юридического Telegram-канала. Соблюдай заданную JSON-схему.",
        },
        { role: "user", content: textPrompt(plan) },
      ],
      response_format: { type: "json_object" },
      max_completion_tokens: 1800,
    }),
    signal: AbortSignal.timeout(90000),
  });
  if (!response.ok) {
    let code = "unknown";
    try {
      const errorBody = await response.json() as Record<string, unknown>;
      const errorObject = errorBody.error;
      if (errorObject && typeof errorObject === "object") {
        const candidate = (errorObject as Record<string, unknown>).code ??
          (errorObject as Record<string, unknown>).type;
        if (typeof candidate === "string") {
          code = candidate.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80);
        }
      }
    } catch {
      // Keep only the HTTP classification when OpenAI returns no JSON body.
    }
    throw new Error(`openai_text_http_${response.status}_${code}`);
  }

  const payload = await response.json() as Record<string, unknown>;
  const choices = payload.choices;
  if (!Array.isArray(choices) || !choices.length) throw new Error("openai_text_empty");
  const first = choices[0];
  if (!first || typeof first !== "object") throw new Error("openai_text_invalid");
  const message = (first as Record<string, unknown>).message;
  if (!message || typeof message !== "object") throw new Error("openai_text_invalid");
  const content = (message as Record<string, unknown>).content;
  if (typeof content !== "string" || !content.trim()) throw new Error("openai_text_empty");

  try {
    JSON.parse(content);
  } catch {
    throw new Error("openai_text_not_json");
  }
  return payload;
}

async function enqueue(plan: EditorialPlan, textResponse: Record<string, unknown>) {
  return await rpc<Record<string, unknown>>("enqueue_jafar_editorial_text_publication_v1", {
    p_plan_id: plan.plan_id,
    p_text_response: textResponse,
  });
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
  if (!SUPABASE_URL || !SERVICE_KEY) return json({ ok: false, error: "supabase_runtime_missing" }, 500);
  if (!OPENAI_API_KEY) return json({ ok: false, error: "openai_secret_missing" }, 503);

  try {
    if (!(await authorized(req))) return json({ ok: false, error: "unauthorized" }, 401);
  } catch {
    return json({ ok: false, error: "worker_auth_unavailable" }, 503);
  }

  let requestBody: Record<string, unknown> = {};
  try { requestBody = await req.json(); } catch { requestBody = {}; }
  const requested = Number(requestBody.limit ?? 1);
  const limit = Math.max(1, Math.min(Number.isInteger(requested) ? requested : 1, 3));

  try {
    const plans = await fetchDuePlans(limit);
    const results: Record<string, unknown>[] = [];

    for (const plan of plans) {
      try {
        const textResponse = await generateText(plan);
        const imageResponse = await generateImage(plan);
        const result = await enqueue(plan, textResponse, imageResponse);

        if (result?.ok !== true && result?.error !== "plan_not_pending") {
          await markPlanError(plan.plan_id, String(result?.error ?? "enqueue_failed"));
        }
        results.push({
          plan_id: plan.plan_id,
          ok: result?.ok === true,
          error: result?.ok === true ? undefined : result?.error ?? "enqueue_failed",
          publication_id: result?.publication_id,
        });
      } catch (error) {
        const code = error instanceof Error && error.message.startsWith("openai_")
          ? error.message
          : "editorial_generation_failed";
        await markPlanError(plan.plan_id, code);
        results.push({ plan_id: plan.plan_id, ok: false, error: code });
      }
    }

    return json({ ok: true, due_count: plans.length, results });
  } catch (error) {
    return json({
      ok: false,
      error: error instanceof Error && error.message === "openai_secret_missing"
        ? "openai_secret_missing"
        : "autopilot_internal_error",
    }, 500);
  }
});
