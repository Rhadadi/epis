/* A free chat endpoint for the site's signed-out readers, on Cloudflare Workers AI.

   It speaks the OpenAI chat-completions format (streaming), so the site's chat
   can use it like any other service. Workers AI has a daily free allowance;
   once it is used up, requests fail until the next day, so it never costs
   anything unless you add a paid plan. The model and the allowed sites are set
   in wrangler.toml. See README.md for how to deploy it. */

const MAX_INPUT_CHARS = 24000; // the page text plus the conversation
const MAX_OUTPUT_TOKENS = 900;

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
    const cors = {
      "Access-Control-Allow-Origin": allowed.includes(origin) ? origin : allowed[0] || "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "content-type, authorization",
      "Vary": "Origin",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    const url = new URL(request.url);
    if (request.method !== "POST" || !url.pathname.endsWith("/chat/completions")) {
      return new Response("Not found", { status: 404, headers: cors });
    }
    if (allowed.length && !allowed.includes(origin)) {
      return json({ error: { message: "This endpoint only serves the study guide's website." } }, 403, cors);
    }

    let body;
    try { body = await request.json(); } catch { return json({ error: { message: "Bad request" } }, 400, cors); }
    const messages = (body.messages || [])
      .filter((m) => m && typeof m.content === "string" && ["system", "user", "assistant"].includes(m.role))
      .map((m) => ({ role: m.role, content: m.content }));
    // Keep the system message and as much recent conversation as fits.
    const system = messages[0] && messages[0].role === "system" ? [messages.shift()] : [];
    if (system[0]) system[0].content = system[0].content.slice(0, MAX_INPUT_CHARS - 4000);
    let budget = MAX_INPUT_CHARS - (system[0] ? system[0].content.length : 0);
    const recent = [];
    for (let i = messages.length - 1; i >= 0 && budget > 0; i--) {
      budget -= messages[i].content.length;
      if (budget > 0) recent.unshift(messages[i]);
    }

    let stream;
    try {
      stream = await env.AI.run(env.MODEL, { messages: system.concat(recent), stream: true, max_tokens: MAX_OUTPUT_TOKENS });
    } catch (e) {
      const msg = /limit|quota|neurons/i.test(String(e)) ? "The free assistant has used up today's allowance. Please try again tomorrow." : "The free assistant is unavailable right now.";
      return json({ error: { message: msg } }, 429, cors);
    }

    // Workers AI streams {"response": "..."} events; re-emit them as OpenAI chunks.
    const encoder = new TextEncoder(), decoder = new TextDecoder();
    let buffer = "";
    const out = stream.pipeThrough(new TransformStream({
      transform(chunk, controller) {
        buffer += decoder.decode(chunk, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop();
        for (const ev of events) {
          const data = ev.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("");
          if (!data || data === "[DONE]") continue;
          try {
            const text = JSON.parse(data).response;
            if (text) controller.enqueue(encoder.encode("data: " + JSON.stringify({ choices: [{ index: 0, delta: { content: text } }] }) + "\n\n"));
          } catch { /* skip partial events */ }
        }
      },
      flush(controller) { controller.enqueue(encoder.encode("data: [DONE]\n\n")); },
    }));
    return new Response(out, { headers: { ...cors, "Content-Type": "text/event-stream", "Cache-Control": "no-cache" } });
  },
};

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), { status, headers: { ...headers, "Content-Type": "application/json" } });
}
