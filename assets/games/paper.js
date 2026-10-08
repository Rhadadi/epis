/* The bottom bar of the kids' site and Baloney Detector (after ncase.me/trust): the menu panel. Scene decks put their
   progress circles into #tprog and the sound switch into #tsound (assets/scenes/deck.js). */
(function () {
  "use strict";
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
