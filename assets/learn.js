/* Mastering Epistemology — learning aids.

   - Term cards: hover (or focus) a dotted term in a chapter to see its definition.
   - Search: the search button or "/" searches chapters, glossary and concepts.
   - Self-checks: after opening an answer, mark it "Got it" or "Not yet".
   - Review (review/): brings questions back on a spaced schedule.
   Progress is kept in this browser under the localStorage key "epis-review". */
(function () {
  "use strict";
  var SCRIPT = document.currentScript && document.currentScript.src;
  var ROOT = SCRIPT ? new URL("../", SCRIPT).href : new URL("./", location.href).href;
  var FA = document.documentElement.lang === "fa";
  var HOME = ROOT + (FA ? "fa/" : "");
  var SFX = FA ? "-fa" : "";
  var OTHER = FA ? "en" : "fa";
  function T(en, fa) { return FA ? fa : en; }
  function N(x) { return FA ? String(x).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }) : String(x); }
  function ascii(x) { return String(x).replace(/[۰-۹]/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹".indexOf(d); }); }
  var DAY = 86400000;
  var INTERVALS = [1, 3, 7, 16, 35, 90]; // days before a question returns, by box

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  var cache = {};
  function getJSON(name) {
    if (!cache[name]) cache[name] = fetch(ROOT + "assets/data/" + name).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
    return cache[name];
  }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; }

  /* ------------------------------------------------------------ term cards */
  var card = null, cardFor = null, showT = 0, hideT = 0;
  function hideCard() { clearTimeout(showT); hideT = setTimeout(function () { if (card) card.hidden = true; cardFor = null; }, 180); }
  function showCard(a) {
    clearTimeout(hideT);
    if (cardFor === a) return;
    clearTimeout(showT);
    showT = setTimeout(function () {
      getJSON("terms" + SFX + ".json").then(function (terms) {
        var t = terms[a.getAttribute("data-term")];
        if (!t) return;
        if (!card) {
          card = el("div", "termcard");
          card.setAttribute("role", "tooltip");
          card.addEventListener("mouseenter", function () { clearTimeout(hideT); });
          card.addEventListener("mouseleave", hideCard);
          document.body.appendChild(card);
        }
        cardFor = a;
        var links = [];
        if (t.c) links.push('<a href="' + HOME + "concepts/" + esc(t.c) + '.html">' + T("Concept page →", "صفحهٔ مفهوم ←") + '</a>');
        if (t.s && location.href.split("#")[0] !== ROOT + t.s.split("#")[0]) links.push('<a href="' + ROOT + esc(t.s) + '">' + T("Explained in ", "توضیح در ") + esc(t.sl || T("the guide", "راهنما")) + "</a>");
        if (t.g) links.push('<a href="' + ROOT + esc(t.g) + '">' + T("Glossary", "واژه‌نامه") + '</a>');
        if (t.c) links.push('<a href="' + ROOT + "map/#" + esc(t.c) + '">' + T("On the map", "روی نقشه") + '</a>');
        var other = t.f || t.e;
        card.innerHTML = '<div class="tt"><b>' + esc(t.t) + "</b>" + (other ? '<span lang="' + OTHER + '" dir="auto">' + esc(other) + "</span>" : "") + "</div>" +
          '<p>' + (t.d || "") + "</p>" + (links.length ? '<div class="tl">' + links.join("") + "</div>" : "");
        card.hidden = false;
        var r = a.getBoundingClientRect(), w = card.offsetWidth, h = card.offsetHeight;
        var top = r.bottom + 8 + h > window.innerHeight ? r.top - h - 8 : r.bottom + 8;
        card.style.top = top + window.scrollY + "px";
        card.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left)) + window.scrollX + "px";
      }).catch(function () { /* no card */ });
    }, 260);
  }
  if (matchMedia("(hover: hover)").matches) {
    document.addEventListener("mouseover", function (e) {
      var a = e.target.closest && e.target.closest("a[data-term]");
      if (a && a.getAttribute("data-term")) showCard(a);
    });
    document.addEventListener("mouseout", function (e) {
      var a = e.target.closest && e.target.closest("a[data-term]");
      if (a && !(e.relatedTarget && a.contains(e.relatedTarget))) hideCard();
    });
  }
  document.addEventListener("focusin", function (e) { if (e.target.matches && e.target.matches("a[data-term]") && e.target.getAttribute("data-term")) showCard(e.target); });
  document.addEventListener("focusout", function (e) { if (e.target.matches && e.target.matches("a[data-term]")) hideCard(); });

  /* ------------------------------------------------------------ search */
  var modal = null, input = null, list = null, results = [], active = 0;
  var KIND = { c: T("Concept", "مفهوم"), g: T("Glossary", "واژه‌نامه"), s: T("Section", "بخش"), ch: T("Chapter", "فصل") };
  var WEIGHT = { c: 3, g: 2.6, ch: 2.4, s: 1 };
  function fold(s) { return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[’']/g, "'"); }
  function score(item, q, words) {
    var t = fold(item.t) + " " + fold(item.f), x = fold(item.x) + " " + fold(item.y), sc = 0;
    for (var i = 0; i < words.length; i++) if (t.indexOf(words[i]) < 0 && x.indexOf(words[i]) < 0) return 0;
    if (fold(item.t) === q) sc += 30; else if (fold(item.t).indexOf(q) === 0) sc += 14; else if (t.indexOf(q) >= 0) sc += 8;
    words.forEach(function (w) {
      if (t.indexOf(w) >= 0) sc += 4;
      var n = 0, at = x.indexOf(w);
      while (at >= 0 && n < 8) { n++; at = x.indexOf(w, at + w.length); }
      sc += n;
    });
    if (x.indexOf(q) >= 0) sc += 3;
    return sc * WEIGHT[item.k];
  }
  function snippet(item, words) {
    var x = item.x || "", fx = fold(x), at = -1;
    for (var i = 0; i < words.length && at < 0; i++) at = fx.indexOf(words[i]);
    if (at < 0) return esc(x.slice(0, 150)) + (x.length > 150 ? "…" : "");
    var start = Math.max(0, at - 60), end = Math.min(x.length, at + 110);
    var out = esc(x.slice(start, end));
    words.forEach(function (w) {
      if (w.length < 2) return;
      out = out.replace(new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"), "<mark>$1</mark>");
    });
    return (start ? "…" : "") + out + (end < x.length ? "…" : "");
  }
  function run() {
    var q = fold(input.value.trim());
    if (q.length < 2) { list.innerHTML = '<p class="sx-hint">' + T("Search the chapters, the 197 glossary terms and the 135 concepts. Persian works for concepts.",
      "جست‌وجو در فصل‌ها، ۱۹۷ اصطلاحِ واژه‌نامه و ۱۳۵ مفهوم. نامِ انگلیسیِ مفاهیم را هم می‌توانید جست‌وجو کنید.") + '</p>'; results = []; return; }
    getJSON("search" + SFX + ".json").then(function (all) {
      var words = q.split(/\s+/).filter(Boolean);
      results = all.map(function (it) { return { it: it, s: score(it, q, words) }; }).filter(function (r) { return r.s > 0; })
        .sort(function (a, b) { return b.s - a.s; }).slice(0, 40);
      active = 0;
      if (!results.length) { list.innerHTML = '<p class="sx-hint">' + T("Nothing found for “", "چیزی برای «") + esc(input.value) + T("”.", "» پیدا نشد.") + "</p>"; return; }
      list.innerHTML = results.map(function (r, i) {
        var it = r.it;
        return '<a class="sx-item" role="option" id="sx-' + i + '" href="' + ROOT + esc(it.u) + '"' + (i === 0 ? ' aria-selected="true"' : "") + ">" +
          '<span class="sx-k">' + KIND[it.k] + (it.c ? " · " + esc(it.c) : "") + "</span>" +
          "<b>" + esc(it.t) + (it.f ? ' <span lang="' + OTHER + '" dir="auto">' + esc(it.f) + "</span>" : "") + "</b>" +
          '<span class="sx-x">' + snippet(it, words) + "</span></a>";
      }).join("");
    }).catch(function () { list.innerHTML = '<p class="sx-hint">' + T("Search is not available offline until the guide has been saved for offline reading.", "تا راهنما برای خواندنِ بی‌اینترنت ذخیره نشده، جست‌وجو بدون اینترنت کار نمی‌کند.") + '</p>'; });
  }
  function move(d) {
    if (!results.length) return;
    var items = list.querySelectorAll(".sx-item");
    items[active].removeAttribute("aria-selected");
    active = (active + d + items.length) % items.length;
    items[active].setAttribute("aria-selected", "true");
    items[active].scrollIntoView({ block: "nearest" });
    input.setAttribute("aria-activedescendant", "sx-" + active);
  }
  function openSearch() {
    if (!modal) {
      modal = el("div", "sx");
      modal.innerHTML = '<div class="sx-box" role="dialog" aria-label="' + T("Search", "جست‌وجو") + '"><div class="sx-in">' +
        '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>' +
        '<input type="search" placeholder="' + T("Search the guide…", "جست‌وجو در راهنما…") + '" aria-label="' + T("Search the guide", "جست‌وجو در راهنما") + '" role="combobox" aria-expanded="true" aria-controls="sx-list" autocomplete="off">' +
        '<kbd>Esc</kbd></div><div class="sx-list" id="sx-list" role="listbox"></div></div>';
      document.body.appendChild(modal);
      input = modal.querySelector("input");
      list = modal.querySelector(".sx-list");
      var t = 0;
      input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(run, 120); });
      input.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
        else if (e.key === "Enter" && results.length) { e.preventDefault(); location.href = list.querySelectorAll(".sx-item")[active].href; closeSearch(); }
        else if (e.key === "Escape") { e.preventDefault(); closeSearch(); }
      });
      modal.addEventListener("mousedown", function (e) { if (e.target === modal) closeSearch(); });
      list.addEventListener("click", function () { setTimeout(closeSearch, 0); });
      getJSON("search" + SFX + ".json").catch(function () {});
    }
    lastFocus = document.activeElement;
    modal.hidden = false;
    document.body.classList.add("sx-open");
    input.focus();
    input.select();
    run();
  }
  var lastFocus = null;
  function closeSearch() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.body.classList.remove("sx-open");
    input.blur();
    if (lastFocus && lastFocus !== document.body && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }
  var sbtn = document.getElementById("search");
  if (sbtn) sbtn.addEventListener("click", openSearch);
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) && !e.target.isContentEditable && !e.metaKey && !e.ctrlKey) {
      e.preventDefault(); openSearch();
    }
  });

  /* ------------------------------------------------------------ review schedule */
  function loadReview() { try { return JSON.parse(localStorage.getItem("epis-review") || "{}") || {}; } catch (e) { return {}; } }
  function saveReview(r) {
    try { localStorage.setItem("epis-review", JSON.stringify(r)); } catch (e) { /* storage full */ }
    document.dispatchEvent(new CustomEvent("epis:review"));
  }
  function grade(id, ok) {
    var r = loadReview(), c = r[id] || { box: 0, n: 0 };
    // Right answers move a question up a box (first time straight to box 2); a miss sends it back to box 1.
    c.box = ok ? (c.box ? Math.min(INTERVALS.length, c.box + 1) : 2) : 1;
    c.due = Date.now() + INTERVALS[c.box - 1] * DAY - 3600000;
    c.n += 1;
    c.last = Date.now();
    c.ok = ok;
    r[id] = c;
    saveReview(r);
    return c;
  }
  function dueCount(r) {
    var now = Date.now();
    return Object.keys(r).filter(function (k) { return r[k].due <= now; }).length;
  }
  function when(c) {
    var d = Math.round((c.due - Date.now()) / DAY);
    return d <= 0 ? T("later today", "امروز") : d === 1 ? T("tomorrow", "فردا") : T("in " + d + " days", N(d) + " روز دیگر");
  }

  /* self-checks inside chapters */
  var article = document.querySelector("article[data-slug]");
  if (article) {
    var slug = article.getAttribute("data-slug");
    article.querySelectorAll(".prose p.q").forEach(function (p) {
      var n = p.querySelector(".n"), det = p.nextElementSibling;
      while (det && det.tagName !== "DETAILS" && !(det.matches && det.matches("p.q, h2"))) det = det.nextElementSibling;
      if (!n || !det || det.tagName !== "DETAILS") return;
      var id = slug + "-q" + ascii(n.textContent.trim());
      var box = el("div", "selfcheck");
      var paint = function () {
        var c = loadReview()[id];
        box.innerHTML = '<span>' + T("How did you do?", "چطور پاسخ دادید؟") + '</span><button type="button" data-ok="1">' + T("Got it", "بلد بودم") +
          '</button><button type="button" data-ok="0">' + T("Not yet", "هنوز نه") + '</button>' +
          (c ? '<small>' + T("Last time: ", "دفعهٔ پیش: ") + (c.ok ? T("Got it", "بلد بودم") : T("Not yet", "هنوز نه")) + T(" · back for review ", " · بازگشت برای مرور: ") + when(c) + "</small>" : "");
      };
      paint();
      box.addEventListener("click", function (e) {
        var b = e.target.closest("button[data-ok]");
        if (!b) return;
        grade(id, b.getAttribute("data-ok") === "1");
        paint();
      });
      det.appendChild(box);
    });
  }

  /* reminder on the start page */
  var resume = document.getElementById("resume");
  if (resume) {
    var due = dueCount(loadReview());
    if (due) {
      var a = el("a", "review-due");
      a.href = HOME + "review/";
      a.innerHTML = FA ? "<b>" + N(due) + "</b> پرسش آمادهٔ مرور است ←" : "<b>" + due + "</b> question" + (due === 1 ? " is" : "s are") + " ready for review →";
      resume.appendChild(a);
    }
  }

  /* the review page */
  var host = document.getElementById("review");
  if (host) {
    var state = { queue: [], i: 0, shown: false, qs: [], mode: "due" };
    var byId = {};
    function chapters() {
      var seen = {}, out = [];
      state.qs.forEach(function (q) { if (!seen[q.ch]) { seen[q.ch] = 1; out.push(q); } });
      return out;
    }
    function startQueue(filterCh) {
      var r = loadReview(), now = Date.now();
      if (filterCh) {
        state.queue = state.qs.filter(function (q) { return q.u.split("#")[0] === filterCh; }).map(function (q) { return q.id; });
        state.mode = "chapter";
      } else {
        state.queue = Object.keys(r).filter(function (k) { return byId[k] && r[k].due <= now; }).sort(function (a, b) { return r[a].due - r[b].due; });
        state.mode = "due";
      }
      state.i = 0; state.shown = false;
      render();
    }
    function stats() {
      var r = loadReview(), keys = Object.keys(r).filter(function (k) { return byId[k]; });
      var learned = keys.filter(function (k) { return r[k].box >= 3; }).length;
      return '<div class="rv-stats"><div><b>' + N(dueCount(r)) + "</b><span>" + T("due now", "آمادهٔ مرور") + "</span></div><div><b>" + N(keys.length) +
        "</b><span>" + T("in your deck", "در دستهٔ شما") + "</span></div><div><b>" + N(learned) + "</b><span>" + T("well learned", "خوب آموخته") + "</span></div><div><b>" + N(state.qs.length) +
        "</b><span>" + T("questions in the guide", "پرسش در راهنما") + "</span></div></div>";
    }
    function picker() {
      return '<div class="rv-pick"><label for="rv-ch">' + T("Practise a chapter", "تمرینِ یک فصل") + '</label><select id="rv-ch"><option value="">' + T("Choose a chapter…", "یک فصل انتخاب کنید…") + '</option>' +
        chapters().map(function (q) { return '<option value="' + esc(q.u.split("#")[0]) + '">' + esc(q.label + ": " + q.title) + "</option>"; }).join("") +
        "</select></div>";
    }
    function render() {
      var q = byId[state.queue[state.i]];
      var html = stats();
      if (!q) {
        var none = state.mode === "due"
          ? T("<h2>Nothing due right now</h2><p>Open an answer in any chapter’s “Check your understanding” section and mark how you did; the question joins your deck and comes back here when it is due. Or practise a chapter now:</p>",
              "<h2>فعلاً چیزی برای مرور نیست</h2><p>در بخشِ «فهمِ خود را بسنجید» هر فصل، پاسخی را باز کنید و مشخص کنید چطور پاسخ داده‌اید؛ پرسش به دستهٔ شما می‌پیوندد و به موقع اینجا برمی‌گردد. یا همین حالا یک فصل را تمرین کنید:</p>")
          : T("<h2>Chapter done</h2><p>Every question from that chapter has been through once. The ones you missed will come back tomorrow.</p>",
              "<h2>فصل تمام شد</h2><p>همهٔ پرسش‌های آن فصل یک بار مرور شدند. آن‌هایی که از دست دادید فردا برمی‌گردند.</p>");
        host.innerHTML = html + '<div class="rv-card rv-empty">' + none + picker() + "</div>";
      } else {
        html += '<div class="rv-card"><div class="rv-meta"><span class="kicker">' + esc(q.label) + " · " + esc(q.title) + "</span><span>" +
          N(state.i + 1) + T(" of ", " از ") + N(state.queue.length) + '</span></div><div class="rv-q prose">' + q.q + "</div>" +
          (state.shown
            ? '<div class="rv-a prose">' + q.a + '</div><div class="rv-grade"><span>' + T("How did you do?", "چطور پاسخ دادید؟") + '</span><button type="button" data-ok="1" class="ok">' + T("Got it", "بلد بودم") + '</button>' +
              '<button type="button" data-ok="0">' + T("Not yet", "هنوز نه") + '</button></div>'
            : '<button type="button" class="rv-show">' + T("Show the answer", "نمایشِ پاسخ") + '</button>') +
          '<p class="rv-src"><a href="' + ROOT + esc(q.u) + '">' + T("Read the chapter section", "خواندنِ بخشِ مربوط در فصل") + '</a></p></div>' + picker();
        host.innerHTML = html;
      }
      var sel = host.querySelector("#rv-ch");
      if (sel) sel.addEventListener("change", function () { if (sel.value) startQueue(sel.value); });
    }
    host.addEventListener("click", function (e) {
      if (e.target.closest(".rv-show")) { state.shown = true; render(); return; }
      var b = e.target.closest("button[data-ok]");
      if (b) { grade(state.queue[state.i], b.getAttribute("data-ok") === "1"); state.i++; state.shown = false; render(); window.scrollTo({ top: host.offsetTop - 90 }); }
    });
    document.addEventListener("keydown", function (e) {
      if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
      if (e.key === " " && host.querySelector(".rv-show")) { e.preventDefault(); state.shown = true; render(); }
      else if ((e.key === "1" || e.key === "2") && host.querySelector(".rv-grade")) { grade(state.queue[state.i], e.key === "1"); state.i++; state.shown = false; render(); }
    });
    getJSON("questions" + SFX + ".json").then(function (qs) {
      state.qs = qs;
      qs.forEach(function (q) { byId[q.id] = q; });
      var fromHash = location.hash.slice(1);
      startQueue(fromHash ? (FA ? "fa/" : "") + "guide/" + fromHash + ".html" : "");
    }).catch(function () { host.innerHTML = '<p class="nb-none">' + T("The questions could not be loaded.", "پرسش‌ها بارگذاری نشدند.") + '</p>'; });
  }
})();
