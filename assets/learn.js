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
  var DAY = 86400000;
  var INTERVALS = [1, 3, 7, 16, 35, 90]; // days before a question returns, by box
  var FA = document.documentElement.lang === "fa";
  var SEARCH_TEXT = FA ? {
    label: "جست‌وجو", input: "جست‌وجوی راهنما…",
    hint: "در فصل‌ها، ۱۹۷ اصطلاح واژه‌نامه و ۱۳۵ مفهوم جست‌وجو کنید. مفاهیم را می‌توانید به فارسی نیز بیابید.",
    none: "نتیجه‌ای یافت نشد", offline: "جست‌وجو تا زمانی که راهنما را برای مطالعهٔ آفلاین ذخیره نکنید، بدون اینترنت در دسترس نیست."
  } : {
    label: "Search", input: "Search the guide…",
    hint: "Search the chapters, the 197 glossary terms and the 135 concepts. Persian works for concepts.",
    none: "Nothing found for", offline: "Search is not available offline until the guide has been saved for offline reading."
  };

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
      getJSON("terms.json").then(function (terms) {
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
        if (t.c) links.push('<a href="' + ROOT + "concepts/" + esc(t.c) + '.html">Concept page →</a>');
        if (t.s && location.href.split("#")[0] !== ROOT + t.s.split("#")[0]) links.push('<a href="' + ROOT + esc(t.s) + '">Explained in ' + esc(t.sl || "the guide") + "</a>");
        if (t.g) links.push('<a href="' + ROOT + esc(t.g) + '">Glossary</a>');
        if (t.c) links.push('<a href="' + ROOT + "map/#" + esc(t.c) + '">On the map</a>');
        card.innerHTML = '<div class="tt"><b>' + esc(t.t) + "</b>" + (t.f ? '<span lang="fa">' + esc(t.f) + "</span>" : "") + "</div>" +
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
  var KIND = FA ? { c: "مفهوم", g: "واژه‌نامه", s: "بخش", ch: "فصل" }
                : { c: "Concept", g: "Glossary", s: "Section", ch: "Chapter" };
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
    if (q.length < 2) { list.innerHTML = '<p class="sx-hint">' + SEARCH_TEXT.hint + "</p>"; results = []; return; }
    getJSON("search.json").then(function (all) {
      var words = q.split(/\s+/).filter(Boolean);
      results = all.map(function (it) { return { it: it, s: score(it, q, words) }; }).filter(function (r) { return r.s > 0; })
        .sort(function (a, b) { return b.s - a.s; }).slice(0, 40);
      active = 0;
      if (!results.length) { list.innerHTML = '<p class="sx-hint">' + SEARCH_TEXT.none + ' «' + esc(input.value) + "».</p>"; return; }
      list.innerHTML = results.map(function (r, i) {
        var it = r.it;
        return '<a class="sx-item" role="option" id="sx-' + i + '" href="' + ROOT + esc(it.u) + '"' + (i === 0 ? ' aria-selected="true"' : "") + ">" +
          '<span class="sx-k">' + KIND[it.k] + (it.c ? " · " + esc(it.c) : "") + "</span>" +
          "<b>" + esc(it.t) + (it.f ? ' <span lang="fa">' + esc(it.f) + "</span>" : "") + "</b>" +
          '<span class="sx-x">' + snippet(it, words) + "</span></a>";
      }).join("");
    }).catch(function () { list.innerHTML = '<p class="sx-hint">' + SEARCH_TEXT.offline + "</p>"; });
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
      modal.innerHTML = '<div class="sx-box" role="dialog" aria-label="' + SEARCH_TEXT.label + '"><div class="sx-in">' +
        '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>' +
        '<input type="search" name="site-search" placeholder="' + SEARCH_TEXT.input + '" aria-label="' + SEARCH_TEXT.input + '" role="combobox" aria-expanded="true" aria-controls="sx-list" autocomplete="off">' +
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
      getJSON("search.json").catch(function () {});
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
    return d <= 0 ? "later today" : d === 1 ? "tomorrow" : "in " + d + " days";
  }

  /* self-checks inside chapters */
  var article = document.querySelector("article[data-slug]");
  if (article) {
    var slug = article.getAttribute("data-slug");
    article.querySelectorAll(".prose p.q").forEach(function (p) {
      var n = p.querySelector(".n"), det = p.nextElementSibling;
      while (det && det.tagName !== "DETAILS" && !(det.matches && det.matches("p.q, h2"))) det = det.nextElementSibling;
      if (!n || !det || det.tagName !== "DETAILS") return;
      var id = slug + "-q" + n.textContent.trim();
      var box = el("div", "selfcheck");
      var paint = function () {
        var c = loadReview()[id];
        box.innerHTML = '<span>How did you do?</span><button type="button" data-ok="1">Got it</button><button type="button" data-ok="0">Not yet</button>' +
          (c ? '<small>' + (c.ok ? "Got it" : "Not yet") + " last time · back for review " + when(c) + "</small>" : "");
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
      a.href = ROOT + "review/";
      a.innerHTML = "<b>" + due + "</b> question" + (due === 1 ? " is" : "s are") + " ready for review →";
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
      return '<div class="rv-stats"><div><b>' + dueCount(r) + "</b><span>due now</span></div><div><b>" + keys.length +
        "</b><span>in your deck</span></div><div><b>" + learned + "</b><span>well learned</span></div><div><b>" + state.qs.length +
        "</b><span>questions in the guide</span></div></div>";
    }
    function picker() {
      return '<div class="rv-pick"><label for="rv-ch">Practise a chapter</label><select id="rv-ch"><option value="">Choose a chapter…</option>' +
        chapters().map(function (q) { return '<option value="' + esc(q.u.split("#")[0]) + '">' + esc(q.label + ": " + q.title) + "</option>"; }).join("") +
        "</select></div>";
    }
    function render() {
      var q = byId[state.queue[state.i]];
      var html = stats();
      if (!q) {
        var none = state.mode === "due"
          ? "<h2>Nothing due right now</h2><p>Open an answer in any chapter’s “Check your understanding” section and mark how you did; the question joins your deck and comes back here when it is due. Or practise a chapter now:</p>"
          : "<h2>Chapter done</h2><p>Every question from that chapter has been through once. The ones you missed will come back tomorrow.</p>";
        host.innerHTML = html + '<div class="rv-card rv-empty">' + none + picker() + "</div>";
      } else {
        html += '<div class="rv-card"><div class="rv-meta"><span class="kicker">' + esc(q.label) + " · " + esc(q.title) + "</span><span>" +
          (state.i + 1) + " of " + state.queue.length + '</span></div><div class="rv-q prose">' + q.q + "</div>" +
          (state.shown
            ? '<div class="rv-a prose">' + q.a + '</div><div class="rv-grade"><span>How did you do?</span><button type="button" data-ok="1" class="ok">Got it</button>' +
              '<button type="button" data-ok="0">Not yet</button></div>'
            : '<button type="button" class="rv-show">Show the answer</button>') +
          '<p class="rv-src"><a href="' + ROOT + esc(q.u) + '">Read the chapter section</a></p></div>' + picker();
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
    getJSON("questions.json").then(function (qs) {
      state.qs = qs;
      qs.forEach(function (q) { byId[q.id] = q; });
      var fromHash = location.hash.slice(1);
      startQueue(fromHash ? "guide/" + fromHash + ".html" : "");
    }).catch(function () { host.innerHTML = '<p class="nb-none">The questions could not be loaded.</p>'; });
  }
})();
