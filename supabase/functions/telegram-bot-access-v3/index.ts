import "jsr:@supabase/functions-js/edge-runtime.d.ts";

Deno.serve(() => new Response(
  JSON.stringify({ ok: false, error: "retired" }),
  {
    status: 410,
    headers: { "content-type": "application/json; charset=utf-8" },
  },
));
