/* Mastering Epistemology — highlights and notes.

   Select text in a chapter or concept page to highlight it or add a note. Each
   highlight is stored with the words around it, so it finds its place again after
   the text is edited. Everything lives in this browser (localStorage key
   "epis-notes"); the Notebook page (notes/) lists, searches, exports and imports it.
   Other scripts can listen for the "epis:notes" event and use window.EpisNotes. */
(function () {
  "use strict";
  var doc = document.documentElement;
  var SCRIPT = document.currentScript && document.currentScript.src;
  var ROOT = SCRIPT ? new URL("../", SCRIPT).href : new URL("./", location.href).href;
  var FA = doc.lang === "fa";
  var HOME = ROOT + (FA ? "fa/" : "");
  function T(en, fa) { return FA ? fa : en; }
  var COLOR_NAMES = { yellow: T("yellow", "زرد"), green: T("green", "سبز"), blue: T("blue", "آبی"), pink: T("pink", "صورتی") };
  var KEY = "epis-notes";
  var COLORS = ["yellow", "green", "blue", "pink"];
  var CTX = 32;

  /* ------------------------------------------------------------ storage */
  function load() {
    try {
      var d = JSON.parse(localStorage.getItem(KEY) || "null");
      if (d && d.items) return d;
    } catch (e) { /* fall through */ }
    return { v: 1, items: {} };
  }
  function save(d, quiet) {
    d.updated = Date.now();
    try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) { alert(T("Your browser storage is full, so this note could not be saved.", "حافظهٔ مرورگر پر است و این یادداشت ذخیره نشد.")); }
    if (!quiet) document.dispatchEvent(new CustomEvent("epis:notes"));
  }
  function live(d) {
    return Object.keys(d.items).map(function (k) { return d.items[k]; }).filter(function (i) { return !i.deleted; });
  }
  // Merge two note sets item by item, keeping the most recently changed version (used by import and sync).
  function merge(a, b) {
    var out = { v: 1, items: {} };
    [a, b].forEach(function (d) {
      Object.keys((d && d.items) || {}).forEach(function (k) {
        var it = d.items[k], cur = out.items[k];
        if (!cur || (it.updated || 0) > (cur.updated || 0)) out.items[k] = it;
      });
    });
    return out;
  }
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }
  window.EpisNotes = { load: load, save: save, merge: merge, live: live };

  /* ------------------------------------------------------------ which page is this */
  var article = document.querySelector("article[data-slug]");
  var container = article ? article.querySelector(".prose") : document.querySelector(".cpage .entry");
  var pageKey = decodeURIComponent(location.href.split(/[?#]/)[0].slice(ROOT.length)).replace(/\.html$/, "").replace(/(^|\/)index$/, "$1");
  function pageInfo() {
    var h1 = document.querySelector(".focus-head .ftitle") || document.querySelector(".hero h1:not(.l-fa)") || document.querySelector("h1");
    var kicker = document.querySelector(".focus-head .kicker") || document.querySelector(".hero .kicker");
    var label = kicker ? kicker.textContent.replace(/^.*·\s*/, "") : "";
    return { title: h1 ? h1.textContent.trim() : document.title, label: article ? label : T("Concept", "مفهوم") };
  }

  /* ------------------------------------------------------------ text index */
  function indexText(root) {
    var nodes = [], pos = 0;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentElement;
        if (!p || p.closest("button, figure.diagram, script, style, .hl-ui, .mynotes")) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n;
    while ((n = walker.nextNode())) { nodes.push({ n: n, start: pos, end: pos + n.data.length }); pos += n.data.length; }
    return { nodes: nodes, text: nodes.map(function (x) { return x.n.data; }).join("") };
  }
  function rangeOffsets(idx, range) {
    var first = null, last = null;
    for (var i = 0; i < idx.nodes.length; i++) {
      var x = idx.nodes[i];
      if (!range.intersectsNode(x.n)) continue;
      if (!first) first = x;
      last = x;
    }
    if (!first) return null;
    var s = first.start + (first.n === range.startContainer ? range.startOffset : 0);
    var e = last.start + (last.n === range.endContainer ? range.endOffset : last.n.data.length);
    return e > s ? [s, e] : null;
  }
  function common(a, b, fromEnd) {
    var n = 0, la = a.length, lb = b.length;
    while (n < la && n < lb && (fromEnd ? a[la - 1 - n] === b[lb - 1 - n] : a[n] === b[n])) n++;
    return n;
  }
  function locate(idx, q) {
    var t = idx.text, whole = t.indexOf(q.prefix + q.exact + q.suffix);
    if (whole >= 0) return [whole + q.prefix.length, whole + q.prefix.length + q.exact.length];
    var best = -1, score = -1, i = t.indexOf(q.exact);
    while (i >= 0) {
      var sc = common(t.slice(Math.max(0, i - CTX), i), q.prefix, true) + common(t.slice(i + q.exact.length, i + q.exact.length + CTX), q.suffix, false);
      if (sc > score) { score = sc; best = i; }
      i = t.indexOf(q.exact, i + 1);
    }
    return best >= 0 ? [best, best + q.exact.length] : null;
  }
  function wrap(idx, span, item) {
    var parts = [];
    idx.nodes.forEach(function (x) {
      var a = Math.max(span[0], x.start), b = Math.min(span[1], x.end);
      if (b > a && x.n.data.slice(a - x.start, b - x.start).trim()) parts.push([x.n, a - x.start, b - x.start]);
    });
    var marks = [];
    parts.forEach(function (p) {
      var node = p[0], a = p[1], b = p[2];
      if (a > 0) { node = node.splitText(a); b -= a; }
      if (b < node.data.length) node.splitText(b);
      var m = document.createElement("mark");
      m.className = "hl c-" + (item.color || "yellow");
      m.setAttribute("data-hl", item.id);
      node.parentNode.insertBefore(m, node);
      m.appendChild(node);
      marks.push(m);
    });
    if (marks.length) {
      marks[0].id = "hl-" + item.id;
      marks[marks.length - 1].classList.add("hl-end");
      if (item.note) marks[marks.length - 1].classList.add("has-note");
    }
    return marks;
  }
  function unwrap(id) {
    document.querySelectorAll('mark[data-hl="' + id + '"]').forEach(function (m) {
      var p = m.parentNode;
      while (m.firstChild) p.insertBefore(m.firstChild, m);
      p.removeChild(m);
      p.normalize();
    });
  }
  function sectionFor(el) {
    var node = el, h = null;
    var heads = container.querySelectorAll("h2[id]");
    for (var i = 0; i < heads.length; i++) {
      if (heads[i].compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING) h = heads[i]; else break;
    }
    return h ? { id: h.id, title: (h.querySelector(".ht") || h).textContent.trim() } : { id: "", title: "" };
  }

  /* ------------------------------------------------------------ highlights on the page */
  var unplaced = [];
  function paint() {
    if (!container) return;
    var d = load();
    unplaced = [];
    live(d).filter(function (i) { return i.page === pageKey && (i.type || "highlight") === "highlight"; })
      .sort(function (a, b) { return a.created - b.created; })
      .forEach(function (item) {
        var idx = indexText(container), span = locate(idx, item);
        if (span) wrap(idx, span, item); else unplaced.push(item);
      });
    layoutMargin();
  }

  var toolbar = null, pop = null, savedRange = null;
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; }
  function dots(current) {
    return COLORS.map(function (c) {
      return '<button type="button" class="dot c-' + c + '" data-color="' + c + '" aria-label="' + T("Highlight ", "نشانه‌گذاری ") + COLOR_NAMES[c] + '"' +
        (current === c ? ' aria-pressed="true"' : "") + "></button>";
    }).join("");
  }
  var ICON_NOTE = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/></svg>';
  var ICON_COPY = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>';
  var ICON_ASK = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg>';
  var ICON_TRASH = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>';

  function hideToolbar() { if (toolbar) toolbar.hidden = true; }
  function showToolbar(range) {
    if (!toolbar) {
      toolbar = el("div", "hl-ui hl-bar");
      toolbar.setAttribute("role", "toolbar");
      toolbar.setAttribute("aria-label", "Highlight");
      toolbar.innerHTML = dots() + '<span class="sep"></span><button type="button" data-act="note">' + ICON_NOTE + "<span>" + T("Note", "یادداشت") + "</span></button>" +
        '<button type="button" data-act="explain" title="' + T("Ask the study companion", "پرسش از همراهِ مطالعه") + '">' + ICON_ASK + "<span>" + T("Explain", "توضیح") + "</span></button>" +
        '<button type="button" data-act="copy" aria-label="' + T("Copy quote", "رونوشت از نقل‌قول") + '">' + ICON_COPY + "</button>";
      toolbar.addEventListener("mousedown", function (e) { e.preventDefault(); });
      // A tap on the toolbar can clear the selection before the click lands; keep the toolbar up meanwhile.
      toolbar.addEventListener("pointerdown", function () { holdUntil = Date.now() + 900; });
      toolbar.addEventListener("click", function (e) {
        var b = e.target.closest("button");
        if (!b || !savedRange) return;
        if (b.getAttribute("data-act") === "copy") { copyQuote(wholeWords(savedRange)); hideToolbar(); return; }
        if (b.getAttribute("data-act") === "explain") {
          var quote = wholeWords(savedRange);
          window.getSelection().removeAllRanges(); hideToolbar();
          if (window.EpisAI) window.EpisAI.explain(quote);
          return;
        }
        var item = create(savedRange, b.getAttribute("data-color") || "yellow");
        window.getSelection().removeAllRanges();
        hideToolbar();
        if (item && b.getAttribute("data-act") === "note") openPop(item.id, true);
      });
      document.body.appendChild(toolbar);
    }
    savedRange = range.cloneRange();
    toolbar.hidden = false;
    // On phones and tablets the system's own Copy / Look Up menu sits next to the selection,
    // so the toolbar docks at the bottom of the screen instead.
    var touch = matchMedia("(pointer: coarse)").matches;
    toolbar.classList.toggle("docked", touch);
    if (touch) { toolbar.style.top = ""; toolbar.style.left = ""; return; }
    var r = range.getBoundingClientRect(), w = toolbar.offsetWidth, h = toolbar.offsetHeight;
    var top = touch ? r.bottom + 12 : r.top - h - 10;
    if (top < 70) top = r.bottom + 12;
    toolbar.style.top = (top + window.scrollY) + "px";
    toolbar.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + window.scrollX + "px";
  }
  function selectionInContainer() {
    var sel = window.getSelection();
    if (!container || !sel || sel.isCollapsed || !sel.rangeCount) return null;
    var range = sel.getRangeAt(0);
    if (!container.contains(range.commonAncestorContainer)) return null;
    if (!range.toString().trim()) return null;
    return range;
  }
  var selTimer = 0, holdUntil = 0;
  function onSelection() {
    clearTimeout(selTimer);
    selTimer = setTimeout(function () {
      var range = selectionInContainer();
      if (range) showToolbar(range);
      else if (Date.now() > holdUntil && !(toolbar && toolbar.matches(":hover"))) hideToolbar();
    }, 180);
  }

  // Widen a selection to whole words, and drop spaces at either end.
  function snap(t, span) {
    var word = /[\p{L}\p{N}\p{M}\u200c’'\-]/u;
    while (span[0] > 0 && word.test(t[span[0] - 1]) && word.test(t[span[0]])) span[0]--;
    while (span[1] < t.length && word.test(t[span[1]]) && word.test(t[span[1] - 1])) span[1]++;
    while (span[0] < span[1] && /\s/.test(t[span[0]])) span[0]++;
    while (span[1] > span[0] && /\s/.test(t[span[1] - 1])) span[1]--;
    return span[1] > span[0] ? span : null;
  }
  function wholeWords(range) {
    var idx = indexText(container), span = rangeOffsets(idx, range);
    span = span && snap(idx.text, span);
    return span ? idx.text.slice(span[0], span[1]) : range.toString();
  }

  function create(range, color) {
    var idx = indexText(container), span = rangeOffsets(idx, range);
    if (!span) return null;
    var t = idx.text, now = Date.now(), info = pageInfo();
    span = snap(t, span);
    if (!span) return null;
    var node = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
    var sec = sectionFor(node);
    var item = {
      id: uid(), type: "highlight", page: pageKey, pageTitle: info.title, pageLabel: info.label, href: pageKey + (pageKey.indexOf("/") < 0 || /\/$/.test(pageKey) ? "" : ".html"),
      section: sec.id, sectionTitle: sec.title, exact: t.slice(span[0], span[1]),
      prefix: t.slice(Math.max(0, span[0] - CTX), span[0]), suffix: t.slice(span[1], span[1] + CTX),
      color: color, note: "", created: now, updated: now
    };
    var d = load(); d.items[item.id] = item; save(d);
    wrap(idx, span, item);
    layoutMargin();
    return item;
  }
  function update(id, fields) {
    var d = load(), it = d.items[id];
    if (!it) return;
    Object.keys(fields).forEach(function (k) { it[k] = fields[k]; });
    it.updated = Date.now();
    save(d);
    var marks = document.querySelectorAll('mark[data-hl="' + id + '"]');
    marks.forEach(function (m) { COLORS.forEach(function (c) { m.classList.remove("c-" + c); }); m.classList.add("c-" + it.color); });
    if (marks.length) marks[marks.length - 1].classList.toggle("has-note", !!it.note);
    layoutMargin();
  }
  function remove(id) {
    var d = load(), it = d.items[id];
    if (!it) return;
    d.items[id] = { id: id, deleted: true, updated: Date.now() };
    save(d);
    unwrap(id);
    closePop();
    layoutMargin();
  }
  function copyQuote(text) {
    var info = pageInfo();
    var out = FA ? "«" + text.trim().replace(/\s+/g, " ") + "» — " + info.title + "، تسلط بر معرفت‌شناسی (" + location.href.split("#")[0] + ")"
      : "“" + text.trim().replace(/\s+/g, " ") + "” — " + info.title + ", Mastering Epistemology (" + location.href.split("#")[0] + ")";
    if (navigator.clipboard) navigator.clipboard.writeText(out).then(function () { flash(T("Quote copied", "نقل‌قول رونوشت شد")); }, function () { flash(T("Could not copy", "رونوشت انجام نشد")); });
  }
  var flashEl = null;
  function flash(msg) {
    if (!flashEl) { flashEl = el("div", "hl-ui hl-flash"); flashEl.setAttribute("role", "status"); document.body.appendChild(flashEl); }
    flashEl.textContent = msg;
    flashEl.classList.add("on");
    setTimeout(function () { flashEl.classList.remove("on"); }, 1600);
  }

  /* ------------------------------------------------------------ the note popover */
  var popId = null;
  function closePop() { if (pop) { pop.hidden = true; popId = null; } }
  function openPop(id, focusNote) {
    var it = load().items[id];
    var mark = document.getElementById("hl-" + id);
    if (!it || !mark) return;
    if (!pop) {
      pop = el("div", "hl-ui hl-pop");
      pop.setAttribute("role", "dialog");
      pop.setAttribute("aria-label", T("Highlight and note", "نشانه‌گذاری و یادداشت"));
      pop.addEventListener("click", function (e) {
        var b = e.target.closest("button");
        if (!b || !popId) return;
        if (b.hasAttribute("data-color")) {
          update(popId, { color: b.getAttribute("data-color") });
          pop.querySelectorAll(".dot").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        } else if (b.getAttribute("data-act") === "delete") remove(popId);
        else if (b.getAttribute("data-act") === "copy") copyQuote(load().items[popId].exact);
        else if (b.getAttribute("data-act") === "done") closePop();
      });
      document.body.appendChild(pop);
    }
    popId = id;
    pop.innerHTML = '<div class="row">' + dots(it.color) + '<span class="sep"></span>' +
      '<button type="button" data-act="copy" aria-label="' + T("Copy quote", "رونوشت از نقل‌قول") + '" title="' + T("Copy quote", "رونوشت از نقل‌قول") + '">' + ICON_COPY + "</button>" +
      '<button type="button" data-act="delete" aria-label="' + T("Delete highlight", "حذفِ نشانه‌گذاری") + '" title="' + T("Delete highlight", "حذفِ نشانه‌گذاری") + '">' + ICON_TRASH + "</button></div>" +
      '<textarea rows="4" placeholder="' + T("Write a note… (saved as you type)", "یادداشتی بنویسید… (همزمان ذخیره می‌شود)") + '" aria-label="' + T("Note", "یادداشت") + '"></textarea>' +
      '<div class="hl-foot"><a href="' + HOME + 'notes/">' + T("Notebook", "دفترچه") + '</a><button type="button" data-act="done">' + T("Done", "تمام") + '</button></div>';
    var ta = pop.querySelector("textarea");
    ta.value = it.note || "";
    var t = 0;
    ta.addEventListener("input", function () { var id2 = popId; clearTimeout(t); t = setTimeout(function () { update(id2, { note: ta.value }); }, 350); });
    ta.addEventListener("blur", function () { if (popId && (load().items[popId] || {}).note !== ta.value) update(popId, { note: ta.value }); });
    pop.hidden = false;
    var sheet = window.innerWidth < 600;
    pop.classList.toggle("sheet", sheet);
    if (!sheet) {
      var r = mark.getBoundingClientRect(), w = pop.offsetWidth;
      var below = r.bottom + 10;
      var top = below + pop.offsetHeight > window.innerHeight ? r.top - pop.offsetHeight - 10 : below;
      pop.style.top = (Math.max(70, top) + window.scrollY) + "px";
      pop.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left)) + window.scrollX + "px";
    } else { pop.style.top = ""; pop.style.left = ""; }
    if (focusNote) ta.focus({ preventScroll: true });
  }

  /* ------------------------------------------------------------ margin notes (wide screens) */
  var margin = null;
  function layoutMargin() {
    if (!article) return;
    var page = article.closest(".page");
    if (!margin) {
      margin = el("aside", "hl-ui mnotes");
      margin.setAttribute("aria-label", T("Your notes", "یادداشت‌های شما"));
      page.appendChild(margin);
      margin.addEventListener("click", function (e) {
        var c = e.target.closest("[data-open]");
        if (c) openPop(c.getAttribute("data-open"), true);
      });
    }
    margin.innerHTML = "";
    if (getComputedStyle(margin).display === "none") return;
    var base = margin.getBoundingClientRect().top, floor = 0;
    live(load()).filter(function (i) { return i.page === pageKey && i.note && (i.type || "highlight") === "highlight"; })
      .map(function (i) { var m = document.getElementById("hl-" + i.id); return m ? { i: i, top: m.getBoundingClientRect().top - base } : null; })
      .filter(Boolean).sort(function (a, b) { return a.top - b.top; })
      .forEach(function (x) {
        var c = el("button", "mnote c-" + x.i.color);
        c.type = "button";
        c.setAttribute("data-open", x.i.id);
        c.textContent = x.i.note;
        var top = Math.max(x.top, floor);
        c.style.top = top + "px";
        margin.appendChild(c);
        floor = top + c.offsetHeight + 10;
      });
  }

  /* ------------------------------------------------------------ your notes on this chapter */
  function pageNotes() {
    if (!article) return;
    var box = el("section", "mynotes");
    box.innerHTML = '<span class="kicker">' + T("Your notes", "یادداشت‌های شما") + '</span><h2>' + T("In your own words", "به زبانِ خودتان") + '</h2>' +
      '<p>' + T("Summarise the chapter, or write down what you want to remember or question. Saved in this browser as you type.",
        "فصل را خلاصه کنید، یا آنچه را می‌خواهید به یاد بسپارید یا زیرِ سؤال ببرید بنویسید. همزمان در همین مرورگر ذخیره می‌شود.") + '</p>' +
      '<textarea rows="6" aria-label="' + T("Your notes on this chapter", "یادداشت‌های شما دربارهٔ این فصل") + '" placeholder="' +
      T("What is the main idea? What convinced you, and what didn’t?", "ایدهٔ اصلی چیست؟ چه چیزی قانعتان کرد و چه چیزی نه؟") + '"></textarea>' +
      '<p class="hint"><a href="' + HOME + 'notes/">' + T("Open your notebook", "دفترچه‌تان را باز کنید") + '</a>' +
      T(" to see every highlight and note, and to export them.", " تا همهٔ نشانه‌گذاری‌ها و یادداشت‌ها را ببینید و برون‌بری کنید.") + '</p>';
    article.appendChild(box);
    var ta = box.querySelector("textarea"), id = "page:" + pageKey;
    var it = load().items[id];
    ta.value = it && !it.deleted ? it.text || "" : "";
    var t = 0;
    ta.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(function () {
        var d = load(), info = pageInfo(), now = Date.now(), cur = d.items[id];
        d.items[id] = { id: id, type: "page", page: pageKey, pageTitle: info.title, pageLabel: info.label, href: pageKey + ".html",
          text: ta.value, created: cur && cur.created || now, updated: now };
        save(d);
      }, 400);
    });
  }

  /* ------------------------------------------------------------ wiring */
  if (container) {
    paint();
    pageNotes();
    document.addEventListener("selectionchange", onSelection);
    container.addEventListener("click", function (e) {
      var m = e.target.closest("mark[data-hl]");
      if (m && !selectionInContainer()) { e.preventDefault(); openPop(m.getAttribute("data-hl")); }
    });
    document.addEventListener("mousedown", function (e) {
      if (pop && !pop.hidden && !pop.contains(e.target) && !e.target.closest("mark[data-hl], .mnote")) closePop();
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closePop(); hideToolbar(); } });
    var relayout = 0;
    var later = function () { clearTimeout(relayout); relayout = setTimeout(layoutMargin, 150); };
    window.addEventListener("resize", later);
    if ("ResizeObserver" in window) new ResizeObserver(later).observe(container);
    window.addEventListener("load", later);
    var m = location.hash.match(/^#hl-(\w+)/);
    if (m) {
      var target = document.getElementById("hl-" + m[1]);
      if (target) setTimeout(function () {
        target.scrollIntoView({ block: "center" });
        document.querySelectorAll('mark[data-hl="' + m[1] + '"]').forEach(function (x) { x.classList.add("pulse"); });
      }, 300);
    }
    // Keep other open tabs in step.
    window.addEventListener("storage", function (e) {
      if (e.key !== KEY) return;
      document.querySelectorAll("mark[data-hl]").forEach(function (x) { unwrap(x.getAttribute("data-hl")); });
      paint();
    });
  }

  /* ------------------------------------------------------------ the notebook page */
  var book = document.getElementById("notebook");
  if (book) {
    var q = document.getElementById("nb-q"), colorSel = "all";
    function esc(s) { return String(s || "").replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
    function when(t) { try { return new Date(t).toLocaleDateString(FA ? "fa-IR" : undefined, { day: "numeric", month: "short", year: "numeric" }); } catch (e) { return ""; } }
    function N(x) { return FA ? String(x).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }) : String(x); }
    function order(a, b) {
      var ga = /^guide\//.test(a.href) ? 0 : 1, gb = /^guide\//.test(b.href) ? 0 : 1;
      return ga - gb || String(a.href).localeCompare(String(b.href), undefined, { numeric: true });
    }
    function groups(items) {
      var g = {};
      items.forEach(function (i) { (g[i.page] = g[i.page] || []).push(i); });
      return Object.keys(g).map(function (k) { return g[k]; }).sort(function (a, b) { return order(a[0], b[0]); });
    }
    function render() {
      var items = live(load()), term = (q.value || "").trim().toLowerCase();
      var shown = items.filter(function (i) {
        if (colorSel !== "all" && (i.type === "page" || i.color !== colorSel)) return false;
        if (!term) return true;
        return [i.exact, i.note, i.text, i.q, i.a, i.pageTitle, i.sectionTitle].join(" ").toLowerCase().indexOf(term) >= 0;
      });
      document.getElementById("nb-count").textContent = items.length ?
        N(items.filter(function (i) { return (i.type || "highlight") === "highlight"; }).length) + T(" highlights · ", " نشانه‌گذاری · ") +
        N(items.filter(function (i) { return i.note || i.text; }).length) + T(" notes", " یادداشت") : "";
      if (!items.length) {
        book.innerHTML = '<div class="nb-empty"><h2>' + T("Nothing here yet", "هنوز چیزی اینجا نیست") + '</h2><p>' +
          T("Select any sentence in a chapter or concept page and choose a colour to highlight it, or <b>Note</b> to write about it. Your highlights and notes collect here.",
            "هر جمله‌ای را در یک فصل یا صفحهٔ مفهوم انتخاب کنید و رنگی برگزینید تا نشانه‌گذاری شود، یا <b>یادداشت</b> را بزنید تا دربارهٔ آن بنویسید. نشانه‌گذاری‌ها و یادداشت‌هایتان اینجا جمع می‌شوند.") +
          '</p><p><a class="btn primary" href="' + HOME + 'guide/01-what-is-epistemology.html">' + T("Start with chapter 1", "آغاز از فصل ۱") + '</a></p></div>';
        return;
      }
      if (!shown.length) { book.innerHTML = '<p class="nb-none">' + T("No highlights or notes match.", "هیچ نشانه‌گذاری یا یادداشتی پیدا نشد.") + '</p>'; return; }
      book.innerHTML = groups(shown).map(function (list) {
        var head = list[0];
        var page = list.filter(function (i) { return i.type === "page"; })[0];
        var hl = list.filter(function (i) { return i.type !== "page"; }).sort(function (a, b) { return a.created - b.created; });
        var answer = function (i) {
          return '<article class="nb-item nb-ai"><span class="kicker">' + T("Study companion", "همراهِ مطالعه") + '</span>' + (i.q ? '<p class="nb-q">' + esc(i.q).replace(/\n/g, "<br>") + "</p>" : "") +
            '<p class="nb-note">' + esc(i.a).replace(/\n/g, "<br>") + '</p><footer>' + when(i.created) +
            ' · <button type="button" data-del="' + esc(i.id) + '">' + T("Delete", "حذف") + '</button></footer></article>';
        };
        return '<section class="nb-page"><header><span class="kicker">' + esc(head.pageLabel) + '</span><h2><a href="' + ROOT + esc(head.href) + '">' +
          esc(head.pageTitle) + "</a></h2></header>" +
          (page && page.text ? '<div class="nb-mine"><span class="kicker">' + T("In your own words", "به زبانِ خودتان") + '</span><p>' + esc(page.text).replace(/\n/g, "<br>") + "</p></div>" : "") +
          hl.map(function (i) {
            if (i.type === "ai") return answer(i);
            return '<article class="nb-item c-' + esc(i.color) + '"><blockquote>' + esc(i.exact) + "</blockquote>" +
              (i.note ? '<p class="nb-note">' + esc(i.note).replace(/\n/g, "<br>") + "</p>" : "") +
              '<footer>' + (i.sectionTitle ? esc(i.sectionTitle) + " · " : "") + when(i.created) +
              ' · <a href="' + ROOT + esc(i.href) + "#hl-" + esc(i.id) + '">' + T("Open in context", "دیدن در متن") + '</a>' +
              ' · <button type="button" data-del="' + esc(i.id) + '">' + T("Delete", "حذف") + '</button></footer></article>';
          }).join("") + "</section>";
      }).join("");
    }
    function download(name, type, text) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: type }));
      a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    }
    function markdown() {
      var out = [T("# My notes on Mastering Epistemology", "# یادداشت‌های من دربارهٔ «تسلط بر معرفت‌شناسی»"), "",
        T("Exported ", "برون‌بری در ") + new Date().toLocaleString(FA ? "fa-IR" : undefined) + T(" from ", " از ") + ROOT, ""];
      groups(live(load())).forEach(function (list) {
        out.push("## " + list[0].pageTitle + (list[0].pageLabel ? " (" + list[0].pageLabel + ")" : ""), "", ROOT + list[0].href, "");
        list.filter(function (i) { return i.type === "page" && i.text; }).forEach(function (i) { out.push(T("**In my own words:** ", "**به زبانِ خودم:** ") + i.text, ""); });
        var sec = null;
        list.filter(function (i) { return i.type !== "page"; }).sort(function (a, b) { return a.created - b.created; }).forEach(function (i) {
          if (i.type === "ai") { out.push(T("**Asked:** ", "**پرسش:** ") + (i.q || ""), "", i.a || "", ""); return; }
          if (i.sectionTitle && i.sectionTitle !== sec) { sec = i.sectionTitle; out.push("### " + sec, ""); }
          out.push("> " + i.exact.replace(/\s+/g, " "), "");
          if (i.note) out.push(i.note, "");
        });
      });
      return out.join("\n");
    }
    book.addEventListener("click", function (e) {
      var b = e.target.closest("[data-del]");
      if (!b || !confirm(T("Delete this highlight and its note?", "این نشانه‌گذاری و یادداشتش حذف شود؟"))) return;
      var d = load(); d.items[b.getAttribute("data-del")] = { id: b.getAttribute("data-del"), deleted: true, updated: Date.now() }; save(d);
    });
    q.addEventListener("input", render);
    document.querySelectorAll("[data-filter]").forEach(function (b) {
      b.addEventListener("click", function () {
        colorSel = b.getAttribute("data-filter");
        document.querySelectorAll("[data-filter]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        render();
      });
    });
    document.getElementById("nb-md").onclick = function () { download("epistemology-notes.md", "text/markdown", markdown()); };
    document.getElementById("nb-json").onclick = function () { download("epistemology-notes.json", "application/json", JSON.stringify(load(), null, 1)); };
    var file = document.getElementById("nb-file");
    document.getElementById("nb-import").onclick = function () { file.click(); };
    file.onchange = function () {
      var f = file.files[0];
      if (!f) return;
      f.text().then(function (txt) {
        var incoming = JSON.parse(txt);
        if (!incoming || !incoming.items) throw new Error("not a notes file");
        save(merge(load(), incoming));
        alert(T("Imported. Notes you already had were kept; where both copies had a note, the newer one won.", "درون‌بری شد. یادداشت‌های قبلی حفظ شدند؛ هر جا هر دو نسخه یادداشت داشتند، نسخهٔ تازه‌تر ماند."));
      }).catch(function () { alert(T("That file doesn't look like an exported notes file (.json).", "این پرونده به پروندهٔ برون‌بری‌شدهٔ یادداشت‌ها (.json) نمی‌ماند.")); });
      file.value = "";
    };
    document.addEventListener("epis:notes", render);
    window.addEventListener("storage", function (e) { if (e.key === KEY) render(); });
    render();
  }
})();
