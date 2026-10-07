/* How Do You Know? — the small runtime shared by every kids page.
   Games register an engine (Kids.register) and are mounted on every [data-game] element, with their data read
   from the embedded <script type="application/json">, so they work offline. Progress lives only in this browser,
   in localStorage["epis-kids"] = {v, level, stars: {"<unit>/<level>/<game>": 1}}; it is never sent or synced. */
(function () {
  "use strict";
  var FA = document.documentElement.lang === "fa";
  var KEY = "epis-kids";
  function T(en, fa) { return FA ? fa : en; }
  function N(x) { return FA ? String(x).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }) : String(x); }
  function load() {
    try { var s = JSON.parse(localStorage.getItem(KEY) || "{}"); return s && typeof s === "object" ? s : {}; } catch (e) { return {}; }
  }
  var state = load();
  state.v = 1; state.stars = state.stars || {};
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* private mode: keep in memory */ } }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function shuffle(a) {
    a = a.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  var live;
  function say(msg) {  // a polite announcement for screen readers
    if (!live) { live = el("p", "sr-only"); live.setAttribute("aria-live", "polite"); live.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)"; document.body.appendChild(live); }
    live.textContent = ""; setTimeout(function () { live.textContent = msg; }, 30);
  }
  var engines = {};
  var Kids = window.Kids = {
    T: T, N: N, el: el, shuffle: shuffle, say: say,
    register: function (name, init) { engines[name] = init; },
    star: function (box) {  // a finished game: one star, kept on this device
      var id = box.getAttribute("data-unit") + "/" + box.getAttribute("data-level") + "/" + box.getAttribute("data-game");
      state.stars[id] = 1; save(); updateStars();
    }
  };

  function starsFor(unit, level) {
    var n = 0;
    Object.keys(state.stars).forEach(function (k) { var p = k.split("/"); if (p[0] === unit && (!level || p[1] === level)) n++; });
    return n;
  }
  function updateStars() {
    document.querySelectorAll(".kstars[data-unit]").forEach(function (p) {
      var unit = p.getAttribute("data-unit"), level = p.getAttribute("data-level");
      var total = document.querySelectorAll('.kgame[data-unit="' + unit + '"]').length;
      var got = starsFor(unit, level);
      p.innerHTML = "";
      var b = el("b", "", "★ " + N(got) + " / " + N(total));
      p.appendChild(b);
      p.appendChild(document.createTextNode(" " + T("stars on this page", "ستاره در این صفحه")));
    });
    document.querySelectorAll(".kstop-stars[data-unit]").forEach(function (i) {
      var n = starsFor(i.getAttribute("data-unit"));
      i.textContent = n ? "★ " + N(n) : "";
    });
    var total = document.querySelector(".ktotal");
    if (total) {
      var all = Object.keys(state.stars).length;
      total.textContent = all ? T("You have " + all + " stars so far. Keep going!", "تا حالا " + N(all) + " ستاره گرفته‌ای. ادامه بده!") : "";
    }
  }

  // the level a child chose: remembered, and used to send quest-map links to the right page
  function setLevel(level) {
    state.level = level; save();
    document.querySelectorAll(".kchoose [data-set-level]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-set-level") === level ? "true" : "false");
    });
    document.querySelectorAll("a[data-unit-link]").forEach(function (a) {
      a.setAttribute("href", a.getAttribute("data-unit-link") + "/" + (level === "investigators" ? "investigators.html" : ""));
    });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-set-level]");
    if (b) { state.level = b.getAttribute("data-set-level"); save(); if (b.tagName === "BUTTON") setLevel(state.level); }
    var a = e.target.closest && e.target.closest("a[data-leave]");
    if (a) { e.preventDefault(); leave(a.href); }
  });

  // leaving the kids' site: ask first
  function leave(href) {
    var box = el("div", "kleave"), inner = el("div");
    inner.setAttribute("role", "dialog"); inner.setAttribute("aria-modal", "true");
    inner.appendChild(el("p", "", T("This link goes to another website. Ask a grown-up before you go!", "این پیوند به سایتِ دیگری می‌رود. پیش از رفتن از یک بزرگ‌تر بپرس!")));
    var stay = el("button", "", T("Stay here", "همین‌جا می‌مانم")), go = el("button", "go", T("A grown-up says OK", "یک بزرگ‌تر اجازه داد"));
    stay.type = go.type = "button";
    stay.onclick = function () { box.remove(); };
    go.onclick = function () { box.remove(); window.open(href, "_blank", "noopener"); };
    inner.appendChild(stay); inner.appendChild(go); box.appendChild(inner);
    document.body.appendChild(box); stay.focus();
    box.addEventListener("keydown", function (e) { if (e.key === "Escape") box.remove(); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".kgame[data-game]").forEach(function (box) {
      var init = engines[box.getAttribute("data-engine")], data;
      try { data = JSON.parse(box.querySelector('script[type="application/json"]').textContent); } catch (e) { return; }
      if (!init) return;
      var nojs = box.querySelector(".knojs"); if (nojs) nojs.remove();
      init(box, data, Kids);
    });
    if (document.querySelector(".kchoose")) setLevel(state.level || "explorers");
    updateStars();
  });
})();
