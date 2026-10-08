/* The small runtime shared by every game page (the kids' site and Baloney Detector).
   Engines register by name (Games.register) and are mounted on every .kgame[data-engine] element, with their data
   read from the embedded <script type="application/json">, so they work offline. Progress lives only in this
   browser, under the key named by <html data-store> ("epis-kids" or "epis-play"): {v, stars: {"<id>": 1}, …}.
   Nothing is ever sent or synced. */
(function () {
  "use strict";
  var FA = document.documentElement.lang === "fa";
  var KEY = document.documentElement.getAttribute("data-store") || "epis-games";
  function T(en, fa) { return FA ? fa : en; }
  function N(x) { return FA ? String(x).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }).replace(/(\S)\.(\S)/g, "$1٫$2") : String(x); }
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
  var Games = window.Games = {
    FA: FA, T: T, N: N, el: el, shuffle: shuffle, say: say, state: state, save: save,
    reduced: function () { return !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches); },
    register: function (name, init) { engines[name] = init; },
    star: function (box) {  // a finished game: one star, kept on this device
      var id = [box.getAttribute("data-unit") || "play", box.getAttribute("data-level") || "all", box.getAttribute("data-game")].join("/");
      state.stars[id] = 1; save();
      document.dispatchEvent(new CustomEvent("games:star", { detail: id }));
    }
  };
  // mount one game box (also used by scene decks, which build their game boxes as they are reached)
  Games.mount = function (box) {
    var init = engines[box.getAttribute("data-engine")], data;
    try { data = JSON.parse(box.querySelector('script[type="application/json"]').textContent); } catch (e) { return; }
    if (!init) return;
    var nojs = box.querySelector(".knojs"); if (nojs) nojs.remove();
    init(box, data, Games);
  };
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".kgame[data-engine]").forEach(function (box) {
      if (!box.closest("[data-deck]")) Games.mount(box);
    });
  });
})();
