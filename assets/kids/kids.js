/* How Do You Know? — the kids' part of the game runtime (assets/games/core.js does the mounting and storage).
   Here: the star counters, the Explorers/Investigators choice and the "ask a grown-up" screen. Progress lives
   only in this browser, in localStorage["epis-kids"] = {v, level, stars: {"<unit>/<level>/<game>": 1}}. */
(function () {
  "use strict";
  var G = window.Games;
  window.Kids = G;  // the old name, kept for anything that still uses it
  var T = G.T, N = G.N, el = G.el, state = G.state, save = G.save;
  document.addEventListener("games:star", function () { updateStars(); });

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
    if (document.querySelector(".kchoose")) setLevel(state.level || "explorers");
    updateStars();
  });
})();
