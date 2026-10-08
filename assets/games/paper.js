/* The bottom bar of the kids' site and Baloney Detector (after ncase.me/trust): the menu panel. Scene decks put their
   progress circles into #tprog and the sound switch into #tsound (assets/scenes/deck.js). */
(function () {
  "use strict";
  // these pages are always white paper: if anything flips the theme (the system's dark mode), flip it straight back
  var d = document.documentElement;
  function light() { if (d.getAttribute("data-theme") !== "light") d.setAttribute("data-theme", "light"); }
  light();
  if (window.MutationObserver) new MutationObserver(light).observe(d, { attributes: true, attributeFilter: ["data-theme"] });
  var b = document.getElementById("tmenu"), p = document.getElementById("tpanel");
  if (!b || !p) return;
  function set(open) {
    p.hidden = !open; b.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("tmenu-open", open);
    if (open) { var a = p.querySelector("a"); if (a) a.focus(); }
  }
  b.addEventListener("click", function () { set(p.hidden); });
  p.addEventListener("click", function (e) { if (e.target.closest("a")) set(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !p.hidden) { set(false); b.focus(); } });
  window.addEventListener("hashchange", function () { set(false); });
})();
