/* Story player: plays the narration and lights up each word as it is read (word times from the sync file,
   written into data-b/data-e by the build). Tap a line to hear it from there. requestAnimationFrame only while
   playing, so the highlight keeps up with the voice. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    var box = document.querySelector(".kplayer[data-audio]");
    if (!box) return;
    var story = document.querySelector(".kstory");
    var btn = box.querySelector(".kplay");
    var audio = new Audio(box.getAttribute("data-audio"));
    audio.preload = "none";
    var words = Array.prototype.slice.call(story.querySelectorAll(".w[data-b]"));
    var lines = Array.prototype.slice.call(story.querySelectorAll(".line[data-b]"));
    var wb = words.map(function (w) { return +w.getAttribute("data-b"); });
    var lb = lines.map(function (l) { return +l.getAttribute("data-b"); });
    var curW = -1, curL = -1, raf = 0, userScroll = 0;
    var T = window.Kids ? Kids.T : function (en) { return en; };
    function find(arr, t) { var lo = 0, hi = arr.length - 1, r = -1; while (lo <= hi) { var m = (lo + hi) >> 1; if (arr[m] <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; }
    function tick() {
      var t = audio.currentTime;
      var w = find(wb, t);
      if (w !== curW) {
        if (curW >= 0) words[curW].classList.remove("now");
        if (w >= 0 && t <= +words[w].getAttribute("data-e") + 0.25) words[w].classList.add("now"); else w = -1;
        curW = w;
      }
      var l = find(lb, t);
      if (l !== curL) {
        if (curL >= 0) lines[curL].classList.remove("now");
        if (l >= 0) {
          lines[l].classList.add("now");
          if (Date.now() - userScroll > 4000) {
            var r = lines[l].getBoundingClientRect();
            if (r.top < 90 || r.bottom > window.innerHeight - 40) lines[l].scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
          }
        }
        curL = l;
      }
      if (!audio.paused) raf = requestAnimationFrame(tick);
    }
    function setBtn(on) { btn.setAttribute("aria-pressed", on ? "true" : "false"); btn.textContent = on ? T("Pause", "مکث") : T("Listen to the story", "قصه را گوش کن"); }
    btn.addEventListener("click", function () { if (audio.paused) audio.play(); else audio.pause(); });
    audio.addEventListener("play", function () { setBtn(true); cancelAnimationFrame(raf); raf = requestAnimationFrame(tick); });
    audio.addEventListener("pause", function () { setBtn(false); cancelAnimationFrame(raf); });
    audio.addEventListener("ended", function () { setBtn(false); });
    window.addEventListener("wheel", function () { userScroll = Date.now(); }, { passive: true });
    window.addEventListener("touchmove", function () { userScroll = Date.now(); }, { passive: true });
    lines.forEach(function (ln, i) {
      ln.addEventListener("click", function () { audio.currentTime = lb[i]; if (audio.paused) audio.play(); tick(); });
    });
  });
})();
