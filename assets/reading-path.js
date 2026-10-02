/* The interview is local by default. AI can refine a question, never invent a route. */
(function () {
  "use strict";
  var script = document.currentScript;
  var root = new URL("../", script.src).href;
  var KEY = "epis-reading-path", host = document.getElementById("reading-path"), teaser = document.getElementById("rp-home");
  var core = window.EpisReadingPath, data, reply, pending, generation = 0;
  function load() { try { var value = JSON.parse(localStorage.getItem(KEY) || "{}"); return value && value.v === 1 ? value : {}; } catch (_) { return {}; } }
  var state = load();
  function save() {
    state.v = 1;
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (_) { notice("This browser cannot save your path. It will remain available for this visit."); }
  }
  function el(tag, text, className) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function link(text, url, cls) { var a = el("a", text, cls); a.href = new URL(url, root).href; return a; }
  function button(text, fn, cls) { var b = el("button", text, cls || "btn"); b.type = "button"; b.addEventListener("click", fn); return b; }
  function notice(text, error) {
    var n = document.getElementById("rp-notice");
    if (n) { n.textContent = text; n.className = "rp-notice" + (error ? " rp-error" : ""); }
  }
  function topic() { return data.topics.find(function (t) { return t.id === state.answers.topic; }); }
  function relevantCompetencies() {
    var t = topic(), focus = t && (t.focuses.find(function (f) { return f.id === state.answers.focus; }) || t.focuses[0]);
    if (!focus) return data.competencies;
    var ids = new Set(), visited = new Set();
    function visit(sid) {
      if (visited.has(sid)) return; visited.add(sid);
      if (data.foundations[sid]) ids.add(data.foundations[sid]);
      (data.prerequisites[sid] || []).forEach(function (p) { visit(p.id); });
    }
    focus.steps.forEach(function (s) { visit(s.id); });
    return data.competencies.filter(function (c) { return ids.has(c.id); });
  }
  function choices(form, name, values, selected, multiple, cls) {
    var group = el("fieldset"), legend = el("legend", values.title || "Choose an option"); group.append(legend);
    var list = el("div", null, "rp-choices " + (cls || "")); group.append(list);
    values.items.forEach(function (v) {
      var label = el("label", null, "rp-choice"), input = el("input"), copy = el("span");
      input.type = multiple ? "checkbox" : "radio"; input.name = name; input.value = v.id;
      input.checked = multiple ? selected.includes(v.id) : selected === v.id;
      copy.append(el("b", v.label)); if (v.description) copy.append(el("small", v.description));
      label.append(input, copy); list.append(label);
    });
    form.append(group); return group;
  }
  function selected(form, name, multiple) {
    var values = Array.from(form.querySelectorAll('input[name="' + name + '"]:checked')).map(function (i) { return i.value; });
    return multiple ? values : values[0];
  }
  function endpoint() {
    var config = window.EPIS_AI_CONFIG || {};
    return config.readingPathBase || "";
  }
  async function interview() {
    reply = null;
    if (!state.ai || !endpoint() || !state.answers.goal.trim()) return;
    var id = ++generation;
    var controller = new AbortController(); pending = controller;
    var timer = setTimeout(function () { controller.abort(); }, 12000);
    notice("AI is finding a useful follow-up question. You can keep going with the suggested questions.");
    try {
      var res = await fetch(endpoint().replace(/\/+$/, "") + "/reading-path", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: state.answers.goal, mode: state.answers.mode }), signal: controller.signal
      });
      if (!res.ok) throw new Error("unavailable");
      var candidate = core.validInterview(data, await res.json());
      if (!candidate) throw new Error("invalid");
      if (id !== generation || state.step !== 1) return;
      reply = candidate;
      notice("AI suggested a focus. Choose the area that matches your question; you can change it.");
      // Never replace a visitor's selection or interrupt an answer in progress.
      var suggestion = document.getElementById("rp-ai-suggestion");
      if (suggestion) {
        suggestion.textContent = "AI suggests: " + data.topics.find(function (t) { return t.id === reply.topic; }).label + ".";
        suggestion.append(document.createTextNode(" "), button("Use this suggestion", function () {
          var input = host.querySelector('input[name="topic"][value="' + reply.topic + '"]');
          if (input) input.checked = true;
        }, "rp-text-button"));
      }
    } catch (_) {
      if (id === generation) notice("AI is unavailable. The reading guide’s curated questions are ready to use.");
    } finally { clearTimeout(timer); if (id === generation) pending = null; }
  }
  function panel(title, subtitle) {
    host.replaceChildren(); host.setAttribute("aria-busy", "false");
    var form = el("form", null, "rp-panel");
    var short = state.step > 1 && relevantCompetencies().length === 0;
    form.append(el("div", "Question " + (short && state.step === 4 ? 4 : state.step + 1) + (state.step < 2 ? " · a few questions to find your path" : " of " + (short ? 4 : 5)), "rp-step"));
    var heading = el("h2", title); heading.tabIndex = -1; form.append(heading);
    if (subtitle) form.append(el("p", subtitle));
    host.append(form); return form;
  }
  function navigate(step) {
    state.step = step; save(); render();
    var h = host.querySelector("h2"); if (h) h.focus();
  }
  function generate() {
    state.answers.done = state.done;
    state.planProfile = core.normalize(data, state.answers);
    state.step = 5; save(); render();
    var heading = host.querySelector("h2"); if (heading) heading.focus();
  }
  function render() {
    notice("");
    if (state.step === 5 && state.planProfile) { renderPlan(); return; }
    var form;
    if (state.step === 0) {
      form = panel("What would you like to understand?", "A question, a situation, or a topic is enough. You can leave this blank and choose an area next.");
      var label = el("label", "Your question (optional)"); label.htmlFor = "rp-goal";
      var goal = el("textarea"); goal.id = "rp-goal"; goal.name = "goal"; goal.maxLength = 600;
      goal.placeholder = "For example: How can I tell whether a medical study is convincing?"; goal.value = state.answers.goal;
      form.append(label, goal);
      choices(form, "mode", { title: "How would you like to study?", items: Object.keys(core.modes).map(function (id) { return Object.assign({ id: id }, core.modes[id]); }) }, state.answers.mode, false, "rp-modes");
      if (endpoint()) {
        var ai = el("label", null, "rp-ai"), check = el("input"), copy = el("span", "Let AI help with the next question");
        check.type = "checkbox"; check.name = "ai"; check.checked = !!state.ai;
        copy.append(el("small", "Optional. Your question and study mode will be sent to " + ((window.EPIS_AI_CONFIG || {}).readingPathName || "the configured AI service") + ". Recommendations still come from the reviewed chapter routes."));
        ai.append(check, copy); form.append(ai);
      } else form.append(el("p", "This guide uses curated questions. The optional AI interview is not enabled on this site yet.", "rp-ai-info"));
    } else if (state.step === 1) {
      form = panel("Which area fits your question?", "A suggested area is a starting point. You decide whether it fits.");
      var suggestion = state.answers.topic || core.suggest(data, state.answers.goal);
      choices(form, "topic", { title: "Choose the closest area", items: data.topics }, suggestion, false, "rp-topics");
      var aiSuggestion = el("p", "", "rp-ai-info"); aiSuggestion.id = "rp-ai-suggestion"; form.append(aiSuggestion);
    } else if (state.step === 2) {
      var t = topic();
      form = panel(reply && reply.topic === t.id ? reply.question : t.question, "Pick the direction that would help most. These lead to different sections, even within the same chapter.");
      choices(form, "focus", { title: "Your focus", items: t.focuses }, state.answers.focus || t.focuses[0].id, false);
    } else if (state.step === 3) {
      form = panel("What can you already use confidently?", "Select only what feels familiar in practice. Leaving everything unchecked includes the relevant foundations; this is not a test of your education.");
      choices(form, "known", { title: "I can already explain or use…", items: relevantCompetencies() }, state.answers.known, true);
    } else {
      form = panel("How much time for your first path?", "We’ll keep the suggested reading within this total. You can return for the rest or change your time later.");
      choices(form, "minutes", { title: "Total reading time", items: [15,30,60,120,240].map(function (n) { return { id: String(n), label: n < 60 ? n + " minutes" : n / 60 + (n === 60 ? " hour" : " hours") }; }) }, String(state.answers.minutes), false, "rp-topics");
    }
    var actions = el("div", null, "rp-actions"), next = el("button", state.step === 4 ? "Find my reading path →" : "Continue →", "btn primary");
    next.type = "submit"; actions.append(next);
    if (state.step > 0) actions.append(button("Back", function () { navigate(state.step === 4 && !relevantCompetencies().length ? 2 : state.step - 1); }));
    if (state.step === 3) actions.append(button("Skip · include foundations", function () { state.answers.known = []; navigate(4); }, "rp-text-button"));
    form.append(actions);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (state.step === 0) {
        if (pending) pending.abort(); generation++; reply = null;
        state.answers.goal = form.elements.goal.value.trim(); state.answers.mode = selected(form, "mode") || "guided";
        state.ai = !!(form.elements.ai && form.elements.ai.checked);
        state.answers.topic = ""; state.answers.focus = "";
        navigate(1); interview(); return;
      }
      if (state.step === 1) {
        var id = selected(form, "topic");
        if (!id) { notice("Choose an area so we can recommend relevant sections.", true); return; }
        if (state.answers.topic !== id) state.answers.focus = "";
        state.answers.topic = id;
      }
      if (state.step === 2) {
        state.answers.focus = selected(form, "focus");
        if (!relevantCompetencies().length) { navigate(4); return; }
      }
      if (state.step === 3) state.answers.known = selected(form, "known", true);
      if (state.step === 4) { state.answers.minutes = +(selected(form, "minutes") || 30); generate(); return; }
      navigate(state.step + 1);
    });
  }
  function renderPlan() {
    host.replaceChildren(); host.setAttribute("aria-busy", "false");
    var plan = core.recommend(data, state.planProfile);
    if (!plan.topic || !plan.focus) { state.step = 0; render(); return; }
    var box = el("div", null, "rp-panel"); host.append(box);
    var heading = el("h2", plan.focus.label); heading.tabIndex = -1;
    box.append(el("span", "Your reading path", "rp-step"), heading);
    if (plan.profile.goal) box.append(el("p", '“' + plan.profile.goal + '”', "rp-goal"));
    var modeLabel = el("label", "Study mode"); modeLabel.htmlFor = "rp-mode";
    var mode = el("select", null, "rp-mode-select"); mode.id = "rp-mode";
    Object.keys(core.modes).forEach(function (id) { var o = el("option", core.modes[id].label); o.value = id; mode.append(o); });
    mode.value = plan.profile.mode;
    mode.addEventListener("change", function () {
      state.answers.mode = mode.value; generate();
      var nextMode = document.getElementById("rp-mode"); if (nextMode) nextMode.focus();
    }); box.append(modeLabel, mode);
    var done = plan.items.filter(function (s) { return state.done.includes(s.id); }).length;
    var summary = el("p", plan.minutes + " minutes of estimated reading · " + plan.items.length + " steps · budget: " + plan.profile.minutes + " minutes", "rp-summary");
    box.append(summary);
    if (plan.profile.known.length) box.append(el("p", "Foundations adjusted for your stated familiarity: " + data.competencies.filter(function (c) { return plan.profile.known.includes(c.id); }).map(function (c) { return c.label; }).join(", ") + ".", "rp-small"));
    if (plan.profile.excluded.length) box.append(el("p", "You chose to skip " + plan.profile.excluded.length + " section(s). Their prerequisites are treated as familiar; edit your answers to bring them back.", "rp-small"));
    if (plan.items.length) {
      var progress = el("progress"); progress.max = plan.items.length; progress.value = done; progress.setAttribute("aria-label", "Reading path progress");
      box.append(el("div", done + " of " + plan.items.length + " steps completed", "rp-completion"), progress);
      var next = plan.items.find(function (s) { return !state.done.includes(s.id); });
      if (next) { var start = link("", next.url, "rp-next"); start.append(el("span", done ? "Continue your path →" : "Start here →", "rp-step"), el("b", next.title)); box.append(start); }
      else box.append(el("p", "You’ve completed this path. Give yourself time to reflect, or use “Plan the next stretch” to continue.", "rp-empty"));
    } else box.append(el("p", plan.later.length ? "The next useful section needs more time than this budget allows. Edit your time to include it, or browse the suggestions below." : "You’ve reached the end of this route. Try another focus, or browse the full guide.", "rp-empty"));
    var list = el("ol", null, "rp-list");
    plan.items.forEach(function (s) {
      var item = el("li", null, "rp-item"), content = el("div"); item.append(content);
      content.append(el("span", "Chapter " + s.chapter + " · " + s.minutes + " min · " + (s.kind === "deep" ? "Deeper study" : s.prerequisite ? "Foundation" : "Chapter section"), "rp-tag"));
      var title = el("h3"); title.append(link(s.title, s.url)); content.append(title, el("p", s.why));
      var actions = el("div", null, "rp-actions"), completed = state.done.includes(s.id);
      var mark = button(completed ? "Done ✓ · undo" : "Mark done", function () {
        state.done = completed ? state.done.filter(function (id) { return id !== s.id; }) : state.done.concat(s.id);
        save(); renderPlan();
        var toggle = host.querySelector('[data-done="' + s.id + '"]'); if (toggle) toggle.focus();
      });
      mark.dataset.done = s.id; mark.setAttribute("aria-pressed", String(completed)); actions.append(mark);
      if (s.kind !== "deep") actions.append(button("Already familiar · skip", function () {
        state.answers.excluded = state.answers.excluded.concat(s.id); generate();
      }, "rp-text-button"));
      content.append(actions); list.append(item);
    }); box.append(list);
    if (plan.later.length) {
      var details = el("details", null, "rp-later"), later = el("ul");
      details.append(el("summary", "Beyond this first path · " + plan.later.length + " more suggestions"));
      plan.later.forEach(function (s) { var li = el("li"); li.append(link(s.title + (s.kind === "deep" ? " · Deeper" : "") + " · " + s.minutes + " min", s.url)); later.append(li); });
      details.append(el("p", "These readings are outside the current time budget or mode. Foundations listed here should come before sections that depend on them."), later); box.append(details);
    }
    var actions = el("div", null, "rp-actions");
    actions.append(button("Edit my answers", function () { state.answers.excluded = []; navigate(0); }), button("Change my time", function () { navigate(4); }));
    if (done === plan.items.length && plan.later.length) actions.append(button("Plan the next stretch", generate, "btn primary"));
    actions.append(button("Forget this path", function () {
      if (pending) pending.abort(); generation++; reply = null;
      state = { v: 1, answers: core.normalize(data, {}), done: [], step: 0, ai: false }; navigate(0);
    }, "rp-text-button")); box.append(actions);
  }
  if (teaser) {
    var route = state.planProfile;
    if (route) {
      teaser.replaceChildren(link("Continue your reading path →", "reading-path/", "btn primary"), el("p", "Your path and completed steps are saved in this browser."));
    }
  }
  if (!host) return;
  // This page script is loaded after the global AI configuration.
  fetch(new URL("assets/data/reading-path.json", root)).then(function (r) { if (!r.ok) throw new Error("catalogue"); return r.json(); }).then(function (catalogue) {
    data = catalogue;
    state.answers = core.normalize(data, state.answers);
    state.done = core.normalize(data, { done: state.done }).done;
    state.step = Number.isInteger(state.step) && state.step >= 0 && state.step <= 5 ? state.step : 0;
    if (state.step > 1 && !topic()) state.step = 1;
    if (state.step === 5 && !state.planProfile) state.step = 0;
    render();
  }).catch(function () {
    host.replaceChildren(el("p", "The reading guide could not load. Please reload when you are online, or browse the chapter contents."), link("Open the guide →", "guide/"));
    host.setAttribute("aria-busy", "false");
  });
})();
