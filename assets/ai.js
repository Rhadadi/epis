/* Mastering Epistemology — the AI study companion.

   A chat panel on chapter and concept pages that knows the page you are
   reading. Signed-in readers can use their own Claude (Anthropic) or ChatGPT
   (OpenAI) API key, or any OpenAI-compatible service; the browser talks to the
   provider directly and the key is kept in the reader's own Google Drive
   (see account.js). Everyone else gets the free assistant configured in
   assets/ai-config.js, or, if none is configured, a ready-made prompt to
   paste into the free ChatGPT or Claude website. */
(function () {
  "use strict";
  var SCRIPT = document.currentScript && document.currentScript.src;
  var ROOT = SCRIPT ? new URL("../", SCRIPT).href : new URL("./", location.href).href;
  var CONFIG = window.EPIS_AI_CONFIG || {};
  var FA = document.documentElement.lang === "fa";
  var HOME = ROOT + (FA ? "fa/" : "");
  function T(en, fa) { return FA ? fa : en; }
  function N(x) { return FA ? String(x).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }) : String(x); }

  var MODELS = {
    anthropic: [
      { id: "claude-opus-5", name: "Claude Opus 5", note: T("best answers · roughly $0.17 for the first question in a chapter, about 4¢ for each follow-up", "بهترین پاسخ‌ها · حدودِ ۱۷ سنت برای نخستین پرسش در هر فصل و حدودِ ۴ سنت برای هر پرسشِ بعدی") },
      { id: "claude-sonnet-5", name: "Claude Sonnet 5", note: T("fast and strong · roughly 7¢ for the first question in a chapter, 1–2¢ after", "سریع و قوی · حدودِ ۷ سنت برای نخستین پرسش در هر فصل و ۱ تا ۲ سنت پس از آن") },
      { id: "claude-haiku-4-5", name: "Claude Haiku 4.5", note: T("quickest and cheapest · roughly 3–4¢ for the first question in a chapter, under 1¢ after", "سریع‌ترین و ارزان‌ترین · حدودِ ۳ تا ۴ سنت برای نخستین پرسش در هر فصل و کمتر از ۱ سنت پس از آن") }
    ],
    openai: ["gpt-5", "gpt-5-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4o-mini"]
  };
  var MODES = {
    explain: { label: T("Explain", "توضیح"), hint: T("Ask anything about this page", "هر پرسشی دربارهٔ این صفحه بپرسید") },
    socratic: { label: T("Socratic tutor", "معلمِ سقراطی"), hint: T("It answers with questions that lead you there", "با پرسش شما را به پاسخ می‌رساند") },
    debate: { label: T("Debate me", "با من مناظره کن"), hint: T("State a view; it argues the other side", "دیدگاهی بگویید؛ از طرفِ مقابل دفاع می‌کند") },
    quiz: { label: T("Quiz me", "از من بپرس"), hint: T("It asks, you answer, it grades", "می‌پرسد، پاسخ می‌دهید، ارزیابی می‌کند") }
  };
  var MODE_RULES = {
    explain: "",
    socratic: "Teach Socratically. Do not give the answer outright. Ask one short question at a time that leads the reader toward it, respond to their answer, confirm what is right and gently correct what is not. Only summarise the answer once they have reached it or ask you to.",
    debate: "Act as a debate partner. Take the opposing side of whatever position the reader states and argue it as strongly and fairly as you can (steelman it). Keep each turn short. After a few exchanges, name the crux of the disagreement and what evidence would settle it.",
    quiz: "Quiz the reader on this page. Ask one question at a time, mixing recall, application to a new case, and 'what would change if…' questions. Wait for the answer, grade it briefly and explain, then ask the next. Keep a running score."
  };

  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  function json(k, fb) { try { return JSON.parse(get(k) || "null") || fb; } catch (e) { return fb; } }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function signedIn() { return !!(window.EpisAccount && window.EpisAccount.signedIn()); }

  /* ------------------------------------------------------------ settings */
  function settings() {
    var s = json("epis-ai", {});
    s.keys = s.keys || {}; s.models = s.models || {};
    s.provider = s.provider || "anthropic";
    return s;
  }
  function saveSettings(s) { s.updated = Date.now(); set("epis-ai", JSON.stringify(s)); document.dispatchEvent(new Event("epis:ai")); }
  // Which service answers right now: the reader's own key when signed in, otherwise the free option.
  function engine() {
    var s = settings();
    if (signedIn() && s.keys[s.provider]) {
      if (s.provider === "anthropic") {
        var m = s.models.anthropic || "claude-opus-5";
        var info = MODELS.anthropic.filter(function (x) { return x.id === m; })[0];
        return { kind: "anthropic", key: s.keys.anthropic, model: m, label: (info ? info.name : m) + T(" · your key", " · کلیدِ شما"), full: true };
      }
      if (s.provider === "openai") return { kind: "openai", base: "https://api.openai.com/v1", key: s.keys.openai, model: s.models.openai || "gpt-5-mini", label: (s.models.openai || "gpt-5-mini") + T(" · your key", " · کلیدِ شما"), full: true };
      return { kind: "openai", base: (s.base || "").replace(/\/+$/, ""), key: s.keys.compat, model: s.models.compat || "", label: (s.models.compat || "model") + " · " + (s.base || "").replace(/^https?:\/\//, "").split("/")[0], full: true };
    }
    if (CONFIG.freeBase) return { kind: "openai", base: CONFIG.freeBase.replace(/\/+$/, ""), key: CONFIG.freeKey || "", model: CONFIG.freeModel || "", label: CONFIG.freeName || T("Free assistant", "دستیارِ رایگان"), full: false };
    return { kind: "handoff", label: T("Free: continue in ChatGPT or Claude", "رایگان: ادامه در ChatGPT یا Claude"), full: false };
  }

  /* ------------------------------------------------------------ the page as context */
  var article = document.querySelector("article[data-slug]");
  var concept = document.querySelector(".cpage .entry");
  var pageKey = decodeURIComponent(location.href.split(/[?#]/)[0].slice(ROOT.length)).replace(/\.html$/, "").replace(/(^|\/)index$/, "$1");
  function pageTitle() {
    var t = document.querySelector(".focus-head .ftitle") || document.querySelector(".hero h1:not(.l-fa)") || document.querySelector("h1");
    return t ? t.textContent.trim() : document.title;
  }
  function blockText(el) {
    var c = el.cloneNode(true);
    c.querySelectorAll("button, .selfcheck, .hl-ui, figure.diagram svg, script, style").forEach(function (x) { x.remove(); });
    return c.textContent.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
  }
  function fullText() {
    if (article) {
      var out = [];
      article.querySelectorAll(".prose > *").forEach(function (el) {
        if (el.tagName === "H2") out.push("\n## " + (el.querySelector(".ht") || el).textContent.trim());
        else if (el.tagName === "H3") out.push("\n### " + el.textContent.trim());
        else { var t = blockText(el); if (t) out.push(t); }
      });
      return out.join("\n\n");
    }
    if (concept) return blockText(concept.querySelector(FA ? ".l-fa" : ".l-en") || concept);
    return "";
  }
  function currentSection() {
    if (!article) return { title: "", text: fullText().slice(0, 6000) };
    var heads = article.querySelectorAll(".prose h2[id]"), cur = null;
    for (var i = 0; i < heads.length; i++) if (heads[i].getBoundingClientRect().top < window.innerHeight * 0.4) cur = heads[i];
    var parts = [], el = cur ? cur.nextElementSibling : article.querySelector(".prose").firstElementChild;
    while (el && el.tagName !== "H2") { parts.push(blockText(el)); el = el.nextElementSibling; }
    return { title: cur ? (cur.querySelector(".ht") || cur).textContent.trim() : T("Introduction", "مقدمه"), text: parts.join("\n\n").slice(0, 7000) };
  }
  function systemPrompt(mode) {
    return ["You are a patient, rigorous study companion for \"Mastering Epistemology\", a free guide to epistemology and critical thinking.",
      "The reader is on the page given below. Ground your answers in it and say so when you go beyond it.",
      "Be concise: short paragraphs, plain words, and a concrete example when it helps. Use Markdown lightly (bold, short lists).",
      "When you draw on a section of the page, name it in double square brackets, exactly as titled, like [[The Gettier problem]].",
      FA ? "The reader is using the Persian edition, and the page below is in Persian. Reply in Persian (fluent, natural Persian, with English terms in parentheses only where they help), unless the reader writes in another language."
        : "Reply in the language the reader writes in; if they write in Persian, answer in Persian.",
      settings().depth === "deep"
        ? "Think carefully before answering: test the claim against objections and counter-examples, separate what the text says from your own view, and say how confident you are. Stay focused; length is fine when it earns its place."
        : "Keep answers short, about 150 words or fewer, unless the reader asks for more.",
      MODE_RULES[mode] || ""].join(" ").trim();
  }

  /* ------------------------------------------------------------ chats kept per page */
  function chats() { return json("epis-chats", {}); }
  var live = null; // the conversation while an answer is streaming in
  function chat() { return live || chats()[pageKey] || { mode: "explain", messages: [] }; }
  function saveChat(c) {
    var all = chats();
    c.updated = Date.now();
    c.title = pageTitle();
    c.messages = c.messages.slice(-40);
    all[pageKey] = c;
    set("epis-chats", JSON.stringify(all));
    document.dispatchEvent(new Event("epis:chats"));
  }

  /* ------------------------------------------------------------ markdown, safely */
  var headIds = {};
  if (article) article.querySelectorAll(".prose h2[id]").forEach(function (h) { headIds[(h.querySelector(".ht") || h).textContent.trim().toLowerCase()] = h.id; });
  function inline(s) {
    return s.replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/\[\[([^\]]+)\]\]/g, function (m, t) {
        var id = headIds[t.trim().toLowerCase()];
        return id ? '<a class="cite" href="#' + id + '">' + t + "</a>" : t;
      })
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }
  function md(text) {
    var lines = esc(text).split("\n"), out = [], list = null, code = null, para = [];
    function flush() { if (para.length) { out.push('<p dir="auto">' + inline(para.join("<br>")) + "</p>"); para = []; } }
    function endList() { if (list) { out.push("</" + list + ">"); list = null; } }
    lines.forEach(function (l) {
      if (code !== null) { if (/^```/.test(l)) { out.push("<pre><code>" + code.join("\n") + "</code></pre>"); code = null; } else code.push(l); return; }
      if (/^```/.test(l)) { flush(); endList(); code = []; return; }
      var h = l.match(/^(#{1,4})\s+(.*)/), ul = l.match(/^\s*[-*•]\s+(.*)/), ol = l.match(/^\s*\d+[.)]\s+(.*)/);
      if (h) { flush(); endList(); out.push('<h4 dir="auto">' + inline(h[2]) + "</h4>"); }
      else if (ul || ol) {
        flush();
        var kind = ul ? "ul" : "ol";
        if (list !== kind) { endList(); out.push("<" + kind + ' dir="auto">'); list = kind; }
        out.push('<li dir="auto">' + inline((ul || ol)[1]) + "</li>");
      } else if (/^&gt;\s?/.test(l)) { flush(); endList(); out.push('<blockquote dir="auto">' + inline(l.replace(/^&gt;\s?/, "")) + "</blockquote>"); }
      else if (!l.trim()) { flush(); endList(); }
      else { endList(); para.push(l); }
    });
    if (code !== null) out.push("<pre><code>" + code.join("\n") + "</code></pre>");
    flush(); endList();
    return out.join("");
  }

  /* ------------------------------------------------------------ talking to the providers */
  function readSSE(res, onData) {
    var reader = res.body.getReader(), dec = new TextDecoder(), buf = "";
    function pump() {
      return reader.read().then(function (r) {
        if (r.done) return;
        buf += dec.decode(r.value, { stream: true });
        var parts = buf.split(/\r?\n\r?\n/);
        buf = parts.pop();
        parts.forEach(function (block) {
          var data = block.split(/\r?\n/).filter(function (l) { return l.indexOf("data:") === 0; }).map(function (l) { return l.slice(5).trim(); }).join("\n");
          if (data) onData(data);
        });
        return pump();
      });
    }
    return pump();
  }
  function httpError(res, who) {
    return res.text().then(function (t) {
      var m = t;
      try { var j = JSON.parse(t); m = (j.error && (j.error.message || j.error.type)) || t; } catch (e) { /* not JSON */ }
      var e2 = new Error(res.status === 401 || res.status === 403 ? who + T(" rejected the key (", " کلید را نپذیرفت (") + N(res.status) + "): " + m
        : res.status === 429 ? who + T(" says there are too many requests or the account is out of credit. ", ": درخواست‌ها زیاد است یا اعتبارِ حساب تمام شده. ") + m
        : who + T(" returned an error (", " خطا داد (") + N(res.status) + "): " + m);
      e2.status = res.status;
      throw e2;
    });
  }
  function askAnthropic(eng, system, context, messages, onText, signal, withFallbacks) {
    var body = {
      model: eng.model, max_tokens: 8192, stream: true,
      system: [{ type: "text", text: system }, { type: "text", text: context, cache_control: { type: "ephemeral", ttl: "1h" } }],
      messages: messages.map(function (m) { return { role: m.role, content: m.content }; }),
      cache_control: { type: "ephemeral" }
    };
    if (eng.model !== "claude-haiku-4-5") body.output_config = { effort: settings().depth === "deep" ? "high" : "low" };
    var headers = { "content-type": "application/json", "x-api-key": eng.key, "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true" };
    if (withFallbacks && eng.model === "claude-opus-5") { body.fallbacks = "default"; headers["anthropic-beta"] = "server-side-fallback-2026-07-01"; }
    var stop = "";
    return fetch("https://api.anthropic.com/v1/messages", { method: "POST", headers: headers, body: JSON.stringify(body), signal: signal }).then(function (res) {
      if (!res.ok) return httpError(res, "Anthropic");
      return readSSE(res, function (data) {
        var ev; try { ev = JSON.parse(data); } catch (e) { return; }
        if (ev.type === "content_block_delta" && ev.delta && ev.delta.type === "text_delta") onText(ev.delta.text);
        else if (ev.type === "message_delta" && ev.delta && ev.delta.stop_reason) stop = ev.delta.stop_reason;
        else if (ev.type === "error") throw new Error("Anthropic: " + (ev.error && ev.error.message || "error"));
      }).then(function () {
        if (stop === "refusal") onText("\n\n*" + T("The model declined to answer this.", "مدل از پاسخ به این پرسش خودداری کرد.") + "*");
        else if (stop === "max_tokens") onText("\n\n*(" + T("The answer was cut off at the length limit.", "پاسخ در سقفِ طول قطع شد.") + ")*");
      });
    }).catch(function (e) {
      // If the optional fallback setting is what failed, try once more without it.
      if (withFallbacks && eng.model === "claude-opus-5" && (e.status === 400 || e instanceof TypeError) && !(signal && signal.aborted))
        return askAnthropic(eng, system, context, messages, onText, signal, false);
      throw e;
    });
  }
  function askOpenAI(eng, system, context, messages, onText, signal) {
    var headers = { "content-type": "application/json" };
    if (eng.key) headers.Authorization = "Bearer " + eng.key;
    var body = { model: eng.model, stream: true,
      messages: [{ role: "system", content: system + "\n\n<page>\n" + context + "\n</page>" }].concat(messages.map(function (m) { return { role: m.role, content: m.content }; })) };
    if (!eng.model) delete body.model;
    return fetch(eng.base + "/chat/completions", { method: "POST", headers: headers, body: JSON.stringify(body), signal: signal }).then(function (res) {
      if (!res.ok) return httpError(res, eng.full ? T("The AI service", "سرویسِ هوش مصنوعی") : T("The free assistant", "دستیارِ رایگان"));
      return readSSE(res, function (data) {
        if (data === "[DONE]") return;
        var ev; try { ev = JSON.parse(data); } catch (e) { return; }
        var d = ev.choices && ev.choices[0] && ev.choices[0].delta;
        if (d && d.content) onText(d.content);
        if (ev.error) throw new Error(ev.error.message || "error");
      });
    });
  }
  function testKey(provider, key, base) {
    if (provider === "anthropic") {
      return fetch("https://api.anthropic.com/v1/models", { headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true" } })
        .then(function (r) { if (!r.ok) return httpError(r, "Anthropic"); return T("The key works.", "کلید کار می‌کند."); });
    }
    var url = (provider === "openai" ? "https://api.openai.com/v1" : (base || "").replace(/\/+$/, "")) + "/models";
    return fetch(url, { headers: key ? { Authorization: "Bearer " + key } : {} }).then(function (r) { if (!r.ok) return httpError(r, T("The service", "سرویس")); return T("The key works.", "کلید کار می‌کند."); });
  }

  /* ------------------------------------------------------------ the chat panel */
  var panel = null, abort = null, pendingQuote = "";
  var launcher = document.getElementById("ask");
  var CHAT_ICON = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg>';
  function suggestions() {
    var t = pageTitle();
    if (FA) return article
      ? ["این فصل را در پنج نکته خلاصه کن", "قوی‌ترین اعتراض به ایدهٔ اصلیِ این فصل چیست؟", "یک مثالِ واقعی از «" + t.replace(/[؟?.:].*$/, "") + "» بزن", "Explain this chapter simply, in English"]
      : ["«" + t + "» را طوری توضیح بده که انگار تازه با فلسفه آشنا شده‌ام", "بهترین اعتراض به آن چیست و بهترین پاسخ کدام است؟", "این مفهوم با کدام ایده‌های دیگرِ کتاب پیوند دارد؟", "Explain this concept in English"];
    return article
      ? ["Summarise this chapter in five points", "What is the strongest objection to the main idea here?", "Give me a real-life example of " + t.replace(/[?.:].*$/, "").toLowerCase(), "این فصل را به زبان ساده به فارسی توضیح بده"]
      : ["Explain " + t + " as if I were new to philosophy", "What is the best objection to it, and the best reply?", "How does this connect to other ideas in the guide?", "این مفهوم را به فارسی توضیح بده"];
  }
  function build() {
    panel = document.createElement("aside");
    panel.className = "chat";
    panel.setAttribute("aria-label", T("Study companion", "همراهِ مطالعه"));
    panel.hidden = true;
    panel.innerHTML =
      '<header><div><span class="kicker">' + T("Study companion", "همراهِ مطالعه") + '</span><b></b></div>' +
      '<select aria-label="' + T("Mode", "حالت") + '">' + Object.keys(MODES).map(function (k) { return '<option value="' + k + '">' + MODES[k].label + "</option>"; }).join("") + "</select>" +
      '<button type="button" class="grow" aria-label="' + T("Expand", "بزرگ‌تر") + '">⤢</button><button type="button" class="x" aria-label="' + T("Close", "بستن") + '">✕</button></header>' +
      '<div class="msgs" aria-live="polite"></div>' +
      '<form><div class="quote" hidden></div><textarea rows="2" dir="auto" placeholder="' + T("Ask about this page…", "دربارهٔ این صفحه بپرسید…") + '" aria-label="' + T("Your question", "پرسشِ شما") + '"></textarea>' +
      '<button type="submit" class="send" aria-label="' + T("Send", "فرستادن") + '"><svg class="icon flip" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></form>' +
      '<footer><span class="eng"></span><span class="depth" role="group" aria-label="' + T("How much thinking", "میزانِ تأمل") + '">' +
      '<button type="button" data-depth="quick">' + T("Quick", "سریع") + '</button><button type="button" data-depth="deep">' + T("Thorough", "دقیق") + '</button></span>' +
      '<span><button type="button" data-act="new">' + T("New", "تازه") + '</button> · <a href="' + HOME + 'account/#ai">' + T("Settings", "تنظیمات") + '</a></span></footer>';
    document.body.appendChild(panel);
    panel.querySelector("header b").textContent = pageTitle();
    var sel = panel.querySelector("select");
    sel.value = chat().mode || "explain";
    sel.addEventListener("change", function () { var c = chat(); c.mode = sel.value; saveChat(c); paint(); });
    panel.querySelector(".x").addEventListener("click", close);
    panel.querySelector(".grow").addEventListener("click", function () { panel.classList.toggle("tall"); });
    panel.addEventListener("change", function (e) {
      if (e.target.matches(".setup select[name=prov]")) paint();
    });
    var ta = panel.querySelector("textarea");
    ta.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); }
      if (e.key === "Escape") close();
    });
    ta.addEventListener("input", function () { ta.style.height = "auto"; ta.style.height = Math.min(160, ta.scrollHeight) + "px"; });
    panel.querySelector("form").addEventListener("submit", function (e) { e.preventDefault(); if (abort) { abort.abort(); } else submit(); });
    panel.addEventListener("click", function (e) {
      var d = e.target.closest("[data-depth]");
      if (d) { var st = settings(); st.depth = d.getAttribute("data-depth") === "deep" ? "deep" : "quick"; saveSettings(st); paintFooter(); return; }
      var b = e.target.closest("[data-act]");
      if (!b) return;
      var act = b.getAttribute("data-act"), i = +b.getAttribute("data-i");
      var c = chat();
      if (act === "new") { if (abort) abort.abort(); saveChat({ mode: c.mode, messages: [] }); paint(); }
      else if (act === "suggest") { ta.value = b.textContent; submit(); }
      else if (act === "copy") { navigator.clipboard && navigator.clipboard.writeText(c.messages[i].content); b.textContent = T("Copied", "رونوشت شد"); }
      else if (act === "save") { saveToNotes(c.messages[i - 1], c.messages[i]); b.textContent = T("Saved", "ذخیره شد"); }
      else if (act === "unquote") { pendingQuote = ""; paint(); }
      else if (act === "follow") { ta.value = b.getAttribute("data-text"); submit(); }
      else if (act === "retry") {
        var cc = chat(), lastUser = null;
        while (cc.messages.length && cc.messages[cc.messages.length - 1].role === "assistant") cc.messages.pop();
        if (cc.messages.length) lastUser = cc.messages.pop();
        saveChat(cc);
        if (lastUser) { ta.value = lastUser.content; submit(); }
      }
      else if (act === "setup") {
        var f = panel.querySelector(".setup"), prov = f.querySelector("[name=prov]").value, key = f.querySelector("[name=key]").value.trim();
        var model = f.querySelector("[name=model]").value.trim(), msg = f.querySelector(".msg");
        if (!key) { msg.textContent = T("Paste your key first.", "نخست کلید را بچسبانید."); return; }
        var st = settings(), kind = prov === "openrouter" ? "compat" : prov;
        st.provider = kind; st.keys[kind] = key;
        if (model) st.models[kind] = model;
        if (prov === "openrouter") st.base = "https://openrouter.ai/api/v1";
        msg.textContent = T("Checking the key…", "در حال بررسیِ کلید…");
        testKey(kind, key, st.base).then(function () { saveSettings(st); paint(); },
          function (err) { msg.textContent = err instanceof TypeError ? T("Could not reach the service.", "به سرویس دسترسی نشد.") : err.message; });
      }
    });
  }
  function open() {
    if (!panel) build();
    panel.hidden = false;
    document.body.classList.add("chat-open");
    if (launcher) launcher.setAttribute("aria-expanded", "true");
    paint();
    fitKeyboard();
    // On phones, don't pop the keyboard up over the answer; tap the box to type.
    if (!matchMedia("(pointer: coarse)").matches) setTimeout(function () { panel.querySelector("textarea").focus(); }, 50);
  }
  // iPhone and Android keyboards cover fixed panels; lift the sheet above the keyboard instead.
  function fitKeyboard() {
    var vv = window.visualViewport;
    if (!panel || !vv || window.innerWidth > 600) { if (panel) { panel.style.bottom = ""; panel.style.maxHeight = ""; } return; }
    var covered = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
    panel.style.bottom = covered ? covered + "px" : "";
    panel.style.maxHeight = covered ? (vv.height - 12) + "px" : "";
  }
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", fitKeyboard);
    window.visualViewport.addEventListener("scroll", fitKeyboard);
  }
  function close() {
    if (!panel) return;
    panel.hidden = true;
    document.body.classList.remove("chat-open");
    if (launcher) { launcher.setAttribute("aria-expanded", "false"); launcher.focus(); }
  }
  var FOLLOW = FA ? [["ساده‌تر", "این را ساده‌تر و با یک مثالِ روزمره توضیح بده."],
    ["یک مثال", "یک مثالِ واقعی و ملموس بزن."],
    ["قوی‌ترین اعتراض", "قوی‌ترین اعتراض به این چیست و بهترین پاسخ به آن کدام است؟"],
    ["از من بپرس", "یک پرسش از من بپرس تا ببینی درست فهمیده‌ام یا نه."],
    ["In English", "Explain that in English."]]
    : [["Simpler, please", "Explain that more simply, with an everyday example."],
    ["An example", "Give me a concrete, real-life example."],
    ["Strongest objection", "What is the strongest objection to this, and the best reply?"],
    ["Quiz me", "Ask me one question to check I understood this."],
    ["به فارسی", "این را به فارسی توضیح بده."]];
  function paintFooter() {
    var eng = engine(), dep = panel.querySelector(".depth"), deep = settings().depth === "deep";
    panel.querySelector(".eng").textContent = eng.label;
    dep.hidden = !(eng.kind === "anthropic" && eng.model !== "claude-haiku-4-5");
    dep.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", (b.getAttribute("data-depth") === "deep") === deep ? "true" : "false"); });
  }
  function msgHTML(m, i, isLast, busy) {
    if (m.role === "user") return '<div class="m u" dir="auto">' + md(m.content) + "</div>";
    if (m.handoff) return '<div class="m a">' + handoffHTML(m.handoff) + "</div>";
    var html = '<div class="m a">' + (m.content ? md(m.content) : '<span class="typing" aria-label="' + T("Thinking", "در حال فکر") + '"><i></i><i></i><i></i></span>');
    if (m.content && !(isLast && busy)) {
      html += '<div class="acts"><button type="button" data-act="copy" data-i="' + i + '">' + T("Copy", "رونوشت") + '</button><button type="button" data-act="save" data-i="' + i + '">' + T("Save to notebook", "ذخیره در دفترچه") + "</button></div>";
      if (isLast) {
        html += '<div class="follow">' + (m.error ? '<button type="button" data-act="retry">' + T("Try again", "دوباره") + "</button>" : "") +
          FOLLOW.map(function (f) { return '<button type="button" data-act="follow" data-text="' + esc(f[1]) + '">' + esc(f[0]) + "</button>"; }).join("") + "</div>";
      }
    }
    return html + "</div>";
  }
  function nearBottom(box) { return box.scrollHeight - box.scrollTop - box.clientHeight < 90; }
  function updateLast() {
    // While an answer streams in, redraw only that message, and follow it only if you are at the bottom.
    var box = panel.querySelector(".msgs"), c = chat(), els = box.querySelectorAll(".m");
    if (!els.length) return paint();
    var stick = nearBottom(box), m = c.messages[c.messages.length - 1];
    var tmp = document.createElement("div");
    tmp.innerHTML = msgHTML(m, c.messages.length - 1, true, !!abort);
    els[els.length - 1].replaceWith(tmp.firstChild);
    if (stick) box.scrollTop = box.scrollHeight;
  }
  function paint() {
    if (!panel || panel.hidden) return;
    var c = chat(), eng = engine(), box = panel.querySelector(".msgs");
    panel.querySelector("select").value = c.mode || "explain";
    paintFooter();
    panel.querySelector("textarea").placeholder = MODES[c.mode || "explain"].hint + "…";
    var q = panel.querySelector(".quote");
    q.hidden = !pendingQuote;
    if (pendingQuote) q.innerHTML = "<span>“" + esc(pendingQuote.slice(0, 220)) + (pendingQuote.length > 220 ? "…" : "") + '”</span><button type="button" data-act="unquote" aria-label="' + T("Remove quote", "حذفِ نقل‌قول") + '">✕</button>';
    if (!c.messages.length) {
      if (signedIn() && eng.kind !== "anthropic" && !eng.full) {
        // Signed in but no key yet: set it up right here, without leaving the page.
        var prov = (panel.querySelector(".setup select[name=prov]") || {}).value || "anthropic";
        var modelField = prov === "anthropic"
          ? '<select name="model">' + MODELS.anthropic.map(function (m) { return '<option value="' + m.id + '">' + m.name + "</option>"; }).join("") + "</select>"
          : '<input name="model" dir="ltr" placeholder="' + (prov === "openai" ? "gpt-5-mini" : T("model name, e.g. from openrouter.ai/models", "نامِ مدل، مثلاً از openrouter.ai/models")) + '" autocomplete="off">';
        box.innerHTML = '<div class="empty"><p>' + T("Add your own API key once to chat here. It is saved to your Google Drive, so every device you sign in on has it.",
          "یک بار کلیدِ API خودتان را وارد کنید تا همین‌جا گفت‌وگو کنید. کلید در گوگل‌درایوتان ذخیره می‌شود و در هر دستگاهی که با آن وارد شوید در دسترس است.") + "</p>" +
          '<div class="setup"><b>' + T("Your key", "کلیدِ شما") + '</b><div class="row"><select name="prov" aria-label="' + T("Provider", "سرویس‌دهنده") + '">' +
          [["anthropic", "Claude"], ["openai", "ChatGPT"], ["openrouter", "OpenRouter"]].map(function (o) { return '<option value="' + o[0] + '"' + (o[0] === prov ? " selected" : "") + ">" + o[1] + "</option>"; }).join("") +
          '</select>' + modelField + '</div><div class="row"><input name="key" type="password" dir="ltr" autocomplete="off" spellcheck="false" aria-label="' + T("API key", "کلیدِ API") + '" placeholder="' + T("Paste your API key", "کلیدِ API را بچسبانید") + '">' +
          '<button type="button" data-act="setup">' + T("Save", "ذخیره") + '</button></div><p class="msg">' + T("Tip: give the key a monthly spending limit with the provider.", "نکته: نزدِ سرویس‌دهنده برای کلید سقفِ هزینهٔ ماهانه بگذارید.") + "</p></div>" +
          '<p class="fine">' + T("No key? Just ask below and your question is prepared for the free ChatGPT or Claude website.", "کلید ندارید؟ همین پایین بپرسید تا پرسشتان برای وبگاهِ رایگانِ ChatGPT یا Claude آماده شود.") + "</p></div>";
        return;
      }
      box.innerHTML = '<div class="empty"><p>' + (article ? T("Ask anything about this chapter. I have read it, so questions can be as specific as you like.",
            "هر پرسشی دربارهٔ این فصل دارید بپرسید. آن را خوانده‌ام، پس پرسش‌ها می‌توانند هر قدر بخواهید دقیق باشند.")
          : T("Ask anything about this concept.", "هر پرسشی دربارهٔ این مفهوم دارید بپرسید.")) + "</p>" +
        (eng.kind === "handoff" ? '<p class="fine">' + (signedIn() ? T("Add your own Claude or ChatGPT key in ", "کلیدِ Claude یا ChatGPT خودتان را در ")
            : T("Sign in and add your own Claude or ChatGPT key in ", "وارد شوید و کلیدِ Claude یا ChatGPT خودتان را در ")) +
          '<a href="' + HOME + 'account/#ai">' + T("My study", "مطالعهٔ من") + "</a>" +
          T(" to chat here. For now, your question is prepared for the free ChatGPT or Claude website.", " بیفزایید تا همین‌جا گفت‌وگو کنید. فعلاً پرسشتان برای وبگاهِ رایگانِ ChatGPT یا Claude آماده می‌شود.") + "</p>"
          : !eng.full ? '<p class="fine">' + T("You are using the free assistant, which sees the section you are reading. ", "از دستیارِ رایگان استفاده می‌کنید که فقط بخشی را که می‌خوانید می‌بیند. ") +
            '<a href="' + HOME + 'account/#ai">' + T("Sign in and add a key", "وارد شوید و کلید بیفزایید") + "</a>" +
            T(" for answers that draw on the whole chapter.", " تا پاسخ‌ها بر کلِ فصل تکیه کنند.") + "</p>" : "") +
        '<div class="sugg">' + suggestions().map(function (s) { return '<button type="button" data-act="suggest">' + esc(s) + "</button>"; }).join("") + "</div></div>";
      return;
    }
    box.innerHTML = c.messages.map(function (m, i) { return msgHTML(m, i, i === c.messages.length - 1, !!abort); }).join("");
    box.scrollTop = box.scrollHeight;
  }
  function saveToNotes(q, a) {
    if (!window.EpisNotes || !a) return;
    var d = window.EpisNotes.load(), now = Date.now(), id = "ai" + now.toString(36);
    d.items[id] = { id: id, type: "ai", page: pageKey, pageTitle: pageTitle(), pageLabel: article ? T("Chapter", "فصل") : T("Concept", "مفهوم"),
      href: pageKey + ".html", q: q ? q.content : "", a: a.content, created: now, updated: now };
    window.EpisNotes.save(d);
  }
  function handoff(question) {
    var sec = currentSection();
    var prompt = FA
      ? (MODE_RULES[chat().mode] ? MODE_RULES[chat().mode] + "\n\n" : "") +
        "دارم «" + pageTitle() + "» را در کتابِ «تسلط بر معرفت‌شناسی» می‌خوانم (" + location.href.split("#")[0] + ")" +
        (sec.title && article ? "، بخشِ «" + sec.title + "»" : "") + ".\n\n" +
        (pendingQuote ? "متن:\n«" + pendingQuote + "»\n\n" : "متنی که می‌خوانم:\n\"\"\"\n" + sec.text.slice(0, 2500) + "\n\"\"\"\n\n") +
        "پرسشِ من: " + question + "\n\nلطفاً به فارسی پاسخ بده."
      : (MODE_RULES[chat().mode] ? MODE_RULES[chat().mode] + "\n\n" : "") +
      "I'm studying \"" + pageTitle() + "\" in Mastering Epistemology (" + location.href.split("#")[0] + ")" +
      (sec.title && article ? ", section \"" + sec.title + "\"" : "") + ".\n\n" +
      (pendingQuote ? "The passage:\n\"" + pendingQuote + "\"\n\n" : "Here is the text I'm reading:\n\"\"\"\n" + sec.text.slice(0, 2500) + "\n\"\"\"\n\n") +
      "My question: " + question;
    if (navigator.clipboard) navigator.clipboard.writeText(prompt).catch(function () {});
    return prompt.slice(0, 6000);
  }
  function handoffHTML(prompt) {
    var q = encodeURIComponent(prompt);
    return '<div class="handoff"><p>' + T("I copied your question, with the passage, to the clipboard. Open a free assistant and it will be filled in (or just paste):",
        "پرسشتان را همراه با متن رونوشت کردم. یک دستیارِ رایگان را باز کنید تا پرسش در آن نوشته شود (یا خودتان بچسبانید):") + "</p>" +
      '<a class="btn" target="_blank" rel="noopener" href="https://chatgpt.com/?q=' + q + '">' + T("Open in ChatGPT", "باز کردن در ChatGPT") + "</a>" +
      '<a class="btn" target="_blank" rel="noopener" href="https://claude.ai/new?q=' + q + '">' + T("Open in Claude", "باز کردن در Claude") + "</a></div>";
  }
  function submit() {
    var ta = panel.querySelector("textarea"), text = ta.value.trim();
    if (!text || abort) return;
    ta.value = ""; ta.style.height = "auto";
    var c = chat(), eng = engine();
    var content = pendingQuote ? T("About this passage:", "دربارهٔ این متن:") + "\n> " + pendingQuote.replace(/\n+/g, " ") + "\n\n" + text : text;
    c.messages.push({ role: "user", content: content, t: Date.now() });
    if (eng.kind === "handoff") {
      c.messages.push({ role: "assistant", content: "", handoff: handoff(text), t: Date.now() });
      pendingQuote = "";
      saveChat(c); paint();
      return;
    }
    pendingQuote = "";
    var reply = { role: "assistant", content: "", t: Date.now() };
    c.messages.push(reply);
    saveChat(c);
    abort = new AbortController();
    live = c;
    paint();
    var sec = currentSection();
    var context = "Page: " + pageTitle() + " (" + location.href.split("#")[0] + ")\n\n" +
      (eng.full ? fullText() : "Section: " + sec.title + "\n\n" + sec.text);
    var history = c.messages.slice(0, -1).filter(function (m) { return !m.handoff && !m.error; }).slice(-16);
    panel.classList.add("busy");
    var last = 0;
    var onText = function (t) {
      reply.content += t;
      if (Date.now() - last > 80) { last = Date.now(); updateLast(); }
    };
    var ask = eng.kind === "anthropic" ? askAnthropic(eng, systemPrompt(c.mode), context, history, onText, abort.signal, true)
      : askOpenAI(eng, systemPrompt(c.mode), context, history, onText, abort.signal);
    ask.catch(function (e) {
      if (e.name === "AbortError") { var st = "*(" + T("stopped", "متوقف شد") + ")*"; reply.content += reply.content ? "\n\n" + st : st; return; }
      reply.error = true;
      reply.content += (reply.content ? "\n\n" : "") + T("**Couldn't get an answer.** ", "**پاسخی دریافت نشد.** ") +
        (e instanceof TypeError ? T("The service could not be reached (check your connection, or whether the service allows requests from a web page).",
          "به سرویس دسترسی نشد (اتصالتان را بررسی کنید، یا اینکه آیا سرویس درخواست از صفحهٔ وب را می‌پذیرد).") : e.message);
    }).then(function () {
      abort = null;
      live = null;
      panel.classList.remove("busy");
      if (!reply.content) reply.content = "*(" + T("no answer", "بی‌پاسخ") + ")*";
      saveChat(c); updateLast();
    });
  }

  window.EpisAI = {
    open: open,
    explain: function (text) {
      pendingQuote = text.trim();
      open();
      if (abort) return;
      panel.querySelector("textarea").value = T("Explain this in simple terms and say why it matters here.", "این را به زبانِ ساده توضیح بده و بگو چرا اینجا اهمیت دارد.");
      submit();
    }
  };
  if (launcher) launcher.addEventListener("click", function () { if (panel && !panel.hidden) close(); else open(); });
  document.addEventListener("keydown", function (e) {
    if ((e.key === "i" || e.key === "I") && launcher && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); open(); }
  });
  document.addEventListener("epis:account", paint);
  document.addEventListener("epis:ai", paint);

  /* ------------------------------------------------------------ settings on the "My study" page */
  var host = document.getElementById("ai-settings");
  if (!host) return;
  function renderSettings() {
    var s = settings(), inAcc = signedIn();
    if (!inAcc) {
      host.innerHTML = "<p>" + T("Signed out, the chat on every chapter uses the free option: ", "بی‌ورود، گفت‌وگوی هر فصل از گزینهٔ رایگان استفاده می‌کند: ") +
        (CONFIG.freeBase ? "<b>" + esc(CONFIG.freeName || T("the free assistant", "دستیارِ رایگان")) + "</b>" + T(", which sees the section you are reading.", "، که بخشی را که می‌خوانید می‌بیند.")
          : T("your question and the passage are prepared for the free ChatGPT or Claude website.", "پرسش و متنِ شما برای وبگاهِ رایگانِ ChatGPT یا Claude آماده می‌شود.")) +
        "</p><p>" + T("Sign in above to use your own Claude or ChatGPT key. The chat then reads the whole chapter, answers right on the page, and your key is kept in your Google Drive so you only enter it once.",
          "بالاتر وارد شوید تا از کلیدِ Claude یا ChatGPT خودتان استفاده کنید. آن‌وقت گفت‌وگو کلِ فصل را می‌خواند، همین‌جا روی صفحه پاسخ می‌دهد و کلیدتان در گوگل‌درایو نگه داشته می‌شود تا فقط یک بار واردش کنید.") + "</p>";
      return;
    }
    var p = s.provider;
    var models = p === "anthropic"
      ? '<select id="ai-model">' + MODELS.anthropic.map(function (m) { return '<option value="' + m.id + '"' + ((s.models.anthropic || "claude-opus-5") === m.id ? " selected" : "") + ">" + m.name + "</option>"; }).join("") + "</select>"
      : '<input id="ai-model" dir="ltr" list="ai-models" value="' + esc(s.models[p] || (p === "openai" ? "gpt-5-mini" : "")) + '" placeholder="' + (p === "openai" ? "gpt-5-mini" : T("model name", "نامِ مدل")) + '" autocomplete="off">' +
        '<datalist id="ai-models">' + (p === "openai" ? MODELS.openai.map(function (m) { return '<option value="' + m + '">'; }).join("") : "") + "</datalist>";
    var note = p === "anthropic" ? (MODELS.anthropic.filter(function (m) { return m.id === (s.models.anthropic || "claude-opus-5"); })[0] || {}).note
      : p === "openai" ? T("Type any model your OpenAI account can use. Prices are on openai.com/api/pricing.", "نامِ هر مدلی را که حسابِ OpenAI شما به آن دسترسی دارد بنویسید. قیمت‌ها در openai.com/api/pricing آمده است.")
      : T("Any service that speaks the OpenAI chat format and allows requests from web pages: OpenRouter (https://openrouter.ai/api/v1), or Ollama or LM Studio on your own computer (for example http://localhost:11434/v1).",
        "هر سرویسی که قالبِ گفت‌وگوی OpenAI را می‌فهمد و درخواست از صفحهٔ وب را می‌پذیرد: OpenRouter (https://openrouter.ai/api/v1)، یا Ollama یا LM Studio روی رایانهٔ خودتان (برای نمونه http://localhost:11434/v1).");
    host.innerHTML =
      '<div class="seg" role="group" aria-label="' + T("Provider", "سرویس‌دهنده") + '">' +
      [["anthropic", "Claude"], ["openai", "ChatGPT"], ["compat", T("Other", "دیگر")]].map(function (o) {
        return '<button type="button" data-prov="' + o[0] + '" aria-pressed="' + (p === o[0]) + '">' + o[1] + "</button>";
      }).join("") + "</div>" +
      (p === "compat" ? "<label>" + T("Service address", "نشانیِ سرویس") + '<input id="ai-base" dir="ltr" value="' + esc(s.base || "") + '" placeholder="https://openrouter.ai/api/v1"></label>' : "") +
      "<label>" + T("API key", "کلیدِ API") + '<span class="keyrow"><input id="ai-key" type="password" dir="ltr" autocomplete="off" spellcheck="false" value="' + esc(s.keys[p] || "") + '" placeholder="' +
      (p === "anthropic" ? "sk-ant-…" : p === "openai" ? "sk-…" : T("optional for local services", "برای سرویس‌های محلی اختیاری")) + '"><button type="button" data-act="show">' + T("Show", "نمایش") + "</button></span></label>" +
      "<label>" + T("Model", "مدل") + models + "</label>" + '<p class="fine">' + esc(note || "") + "</p>" +
      '<div class="acc-actions"><button type="button" class="btn primary" data-act="save">' + T("Save", "ذخیره") + '</button><button type="button" class="btn" data-act="test">' + T("Test the key", "آزمودنِ کلید") + "</button>" +
      (s.keys[p] ? '<button type="button" class="btn" data-act="remove">' + T("Remove key", "حذفِ کلید") + "</button>" : "") + '</div><p class="ai-msg" aria-live="polite"></p>' +
      '<p class="fine">' + T("Get a key at ", "کلید را از ") + (p === "openai" ? '<a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">platform.openai.com</a>'
        : '<a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener">console.anthropic.com</a>') +
      T(". Give it a monthly spending limit. The key goes only to that provider, straight from your browser, and is stored in your Google Drive's private app folder and in this browser until you sign out.",
        " بگیرید و برایش سقفِ هزینهٔ ماهانه بگذارید. کلید فقط، مستقیم از مرورگرتان، به همان سرویس‌دهنده فرستاده می‌شود و تا وقتی خارج نشده‌اید در پوشهٔ خصوصیِ برنامه در گوگل‌درایو و در همین مرورگر می‌ماند.") + "</p>";
  }
  host.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    var s = settings(), msg = host.querySelector(".ai-msg");
    if (b.hasAttribute("data-prov")) { s.provider = b.getAttribute("data-prov"); saveSettings(s); renderSettings(); return; }
    var act = b.getAttribute("data-act");
    var key = host.querySelector("#ai-key"), model = host.querySelector("#ai-model"), base = host.querySelector("#ai-base");
    if (act === "show") { key.type = key.type === "password" ? "text" : "password"; b.textContent = key.type === "password" ? T("Show", "نمایش") : T("Hide", "پنهان"); }
    else if (act === "save") {
      s.keys[s.provider] = key.value.trim();
      s.models[s.provider] = model.value.trim();
      if (base) s.base = base.value.trim();
      saveSettings(s);
      renderSettings();
      host.querySelector(".ai-msg").textContent = T("Saved.", "ذخیره شد.") + (window.EpisAccount && window.EpisAccount.token() ? T(" It will sync to your Google Drive.", " با گوگل‌درایو همگام می‌شود.") : "");
    } else if (act === "test") {
      msg.textContent = T("Testing…", "در حال آزمودن…");
      testKey(s.provider, key.value.trim(), base ? base.value.trim() : s.base).then(function (m) { msg.textContent = m; },
        function (err) { msg.textContent = err instanceof TypeError ? T("Could not reach the service from this page.", "از این صفحه به سرویس دسترسی نشد.") : err.message; });
    } else if (act === "remove") { delete s.keys[s.provider]; saveSettings(s); renderSettings(); }
  });
  document.addEventListener("epis:account", renderSettings);
  document.addEventListener("epis:ai", function () { if (!host.contains(document.activeElement)) renderSettings(); });
  renderSettings();
})();
