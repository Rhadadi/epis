/* Mastering Epistemology — shared behaviour for every page. No dependencies. */
(function () {
  "use strict";
  var doc = document.documentElement;

  function store(key, value) {
    try {
      if (value === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, value);
    } catch (e) { return null; }
    return null;
  }
  function clock(sec) {
    sec = Math.max(0, Math.round(sec || 0));
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s).padStart(2, "0");
  }

  /* ------------------------------------------------------------ theme */
  var ICON = {
    system: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" stroke="none"/></svg>',
    light: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    dark: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/></svg>'
  };
  var media = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
  function applyTheme(pref, persist) {
    if (["system", "light", "dark"].indexOf(pref) < 0) pref = "system";
    var dark = pref === "dark" || (pref === "system" && media && media.matches);
    doc.dataset.theme = dark ? "dark" : "light";
    doc.dataset.themePreference = pref;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = dark ? "#0A1620" : "#F6F3EC";
    var btn = document.getElementById("theme");
    if (btn) {
      var next = pref === "system" ? "light" : pref === "light" ? "dark" : "system";
      btn.innerHTML = ICON[pref];
      btn.setAttribute("aria-label", "Theme: " + pref + ". Switch to " + next + ".");
      btn.title = "Theme: " + pref;
    }
    if (persist) store("epistemology-theme", pref);
  }
  applyTheme(doc.dataset.themePreference || store("epistemology-theme") || "system", false);
  if (media && media.addEventListener) media.addEventListener("change", function () {
    if ((doc.dataset.themePreference || "system") === "system") applyTheme("system", false);
  });
  var themeBtn = document.getElementById("theme");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var order = ["system", "light", "dark"];
    applyTheme(order[(order.indexOf(doc.dataset.themePreference || "system") + 1) % 3], true);
  });

  /* ------------------------------------------------------------ bar over the hero */
  var bar = document.querySelector(".bar");
  var hero = document.querySelector(".hero");
  function barState() {
    if (!bar) return;
    var over = hero && window.scrollY < 40;
    bar.classList.toggle("clear", !!over);
    bar.classList.toggle("solid", !over);
  }
  barState();
  window.addEventListener("scroll", barState, { passive: true });
  window.addEventListener("resize", barState);

  /* ------------------------------------------------------------ contents rail */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a[href^='#']"));
  if (tocLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[decodeURIComponent(a.getAttribute("href").slice(1))] = a; });
    var visible = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting ? e.boundingClientRect.top : undefined; });
      var heads = Object.keys(byId), current = null;
      for (var i = 0; i < heads.length; i++) {
        var el = document.getElementById(heads[i]);
        if (el && el.getBoundingClientRect().top < window.innerHeight * 0.35) current = heads[i];
      }
      tocLinks.forEach(function (a) { a.classList.toggle("on", byId[current] === a); });
    }, { rootMargin: "0px 0px -60% 0px" });
    Object.keys(byId).forEach(function (id) { var el = document.getElementById(id); if (el) io.observe(el); });
  }

  /* ------------------------------------------------------------ concept language */
  function setLang(lang) {
    if (lang !== "fa") lang = "en";
    doc.dataset.lang = lang;
    store("epistemology-lang", lang);
    document.querySelectorAll("[data-set-lang]").forEach(function (b) {
      var on = b.getAttribute("data-set-lang") === lang;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  if (document.querySelector("[data-set-lang]")) {
    setLang(doc.dataset.lang || "en");
    document.querySelectorAll("[data-set-lang]").forEach(function (b) {
      b.addEventListener("click", function () { setLang(b.getAttribute("data-set-lang")); });
    });
  }

  /* ------------------------------------------------------------ concept filter */
  var filter = document.getElementById("cfilter");
  if (filter) filter.addEventListener("input", function () {
    var q = filter.value.trim().toLowerCase();
    document.querySelectorAll(".clist a, .branch").forEach(function (el) {
      if (el.classList.contains("branch")) return;
      el.hidden = q && el.getAttribute("data-hay").indexOf(q) < 0;
    });
    document.querySelectorAll(".branch").forEach(function (b) {
      var any = b.querySelector(".clist a:not([hidden])");
      b.hidden = q && !any && b.getAttribute("data-hay").indexOf(q) < 0;
    });
  });

  /* ------------------------------------------------------------ audio dock (chapter pages) */
  var card = document.querySelector(".listen[data-audio]");
  var dock = null, audio = null, sections = [], trackKey = "";
  function sectionAt(t) {
    var at = 0;
    for (var i = 0; i < sections.length; i++) if (sections[i].s <= t + 0.5) at = i;
    return at;
  }
  function buildDock() {
    if (dock) return;
    dock = document.createElement("div");
    dock.className = "dock";
    dock.setAttribute("role", "region");
    dock.setAttribute("aria-label", "Audio player");
    dock.innerHTML =
      '<img alt="" src="' + card.getAttribute("data-thumb") + '">' +
      '<div class="t"></div>' +
      '<div class="x"><select class="spd" aria-label="Playback speed">' +
      ["0.8", "0.9", "1", "1.1", "1.25", "1.5", "1.75"].map(function (v) { return "<option>" + v + "</option>"; }).join("") +
      '</select><button type="button" class="close" aria-label="Close player">✕</button></div>' +
      '<div class="s"></div><audio controls preload="metadata"></audio>';
    document.body.appendChild(dock);
    audio = dock.querySelector("audio");
    audio.src = card.getAttribute("data-audio");
    dock.querySelector(".t").textContent = card.getAttribute("data-title");
    var spd = dock.querySelector(".spd");
    spd.value = store("epis-audio-rate") || "1";
    spd.addEventListener("change", function () { audio.playbackRate = parseFloat(spd.value); store("epis-audio-rate", spd.value); });
    dock.querySelector(".close").addEventListener("click", function () {
      audio.pause(); dock.classList.remove("on"); document.body.classList.remove("docked");
    });
    audio.addEventListener("loadedmetadata", function () { audio.playbackRate = parseFloat(spd.value); });
    audio.addEventListener("timeupdate", function () {
      var i = sectionAt(audio.currentTime);
      dock.querySelector(".s").textContent = (sections[i] ? sections[i].t : "") + " · " + clock(audio.currentTime);
      document.querySelectorAll(".listen .chip").forEach(function (c, k) { c.classList.toggle("on", k === i); });
      if (Math.floor(audio.currentTime) % 5 === 0) store(trackKey, String(audio.currentTime));
    });
    audio.addEventListener("ended", function () { store(trackKey, "0"); });
    audio.addEventListener("play", function () { card.classList.add("playing"); card.querySelector(".play").setAttribute("aria-label", "Pause"); });
    audio.addEventListener("pause", function () { card.classList.remove("playing"); card.querySelector(".play").setAttribute("aria-label", "Play the narrated chapter"); });
    window.addEventListener("pagehide", function () { if (audio.currentTime > 5) store(trackKey, String(audio.currentTime)); });
    if ("mediaSession" in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: card.getAttribute("data-title"), artist: "Mastering Epistemology", album: "Audio edition",
          artwork: [{ src: new URL(card.getAttribute("data-thumb"), location.href).href, sizes: "720x720", type: "image/jpeg" }]
        });
        navigator.mediaSession.setActionHandler("seekbackward", function () { audio.currentTime = Math.max(0, audio.currentTime - 15); });
        navigator.mediaSession.setActionHandler("seekforward", function () { audio.currentTime += 30; });
      } catch (e) { /* not supported */ }
    }
  }
  function playFrom(t) {
    buildDock();
    dock.classList.add("on");
    document.body.classList.add("docked");
    var go = function () { if (t !== null) audio.currentTime = t; audio.play(); };
    if (audio.readyState >= 1) go(); else audio.addEventListener("loadedmetadata", go, { once: true });
  }
  if (card) {
    try { sections = JSON.parse(card.getAttribute("data-sections") || "[]"); } catch (e) { sections = []; }
    trackKey = "epis-audio-pos-" + card.getAttribute("data-audio").split("/").pop();
    var play = card.querySelector(".play");
    var saved = parseFloat(store(trackKey) || "0");
    if (saved > 20) card.querySelector(".resume").textContent = "Resume from " + clock(saved);
    play.addEventListener("click", function () {
      if (audio && !audio.paused) { audio.pause(); return; }
      var s = parseFloat(store(trackKey) || "0");
      playFrom(audio ? null : (s > 20 ? s : 0));
    });
    document.querySelectorAll("[data-listen]").forEach(function (b) {
      b.addEventListener("click", function () { play.click(); });
    });
    document.querySelectorAll("[data-at]").forEach(function (b) {
      b.addEventListener("click", function () { playFrom(parseFloat(b.getAttribute("data-at"))); });
    });
  }

  /* ------------------------------------------------------------ full player (audio page) */
  var player = document.getElementById("player");
  if (player && window.TRACKS) {
    var tracks = window.TRACKS, cur = -1;
    var pa = player.querySelector("audio"), rate = player.querySelector("#rate");
    var list = document.getElementById("chapters"), secs = document.getElementById("sections");
    var title = player.querySelector("h2"), secLabel = player.querySelector(".sec"), readLink = document.getElementById("read");
    var art = window.TRACK_ART || {};
    var chapterButtons = tracks.map(function (t, i) {
      var li = document.createElement("li"), b = document.createElement("button");
      b.type = "button";
      b.innerHTML = '<img alt="" loading="lazy"><span><b></b><small></small></span><small class="d"></small>';
      b.querySelector("img").src = art[i] || "";
      b.querySelector("b").textContent = t.title.replace(/^Chapter \d+ — /, "");
      b.querySelector("span small").textContent = "Chapter " + (i + 1);
      b.querySelector(".d").textContent = Math.round(t.duration / 60) + " min";
      b.addEventListener("click", function () { load(i, true); });
      li.appendChild(b); list.appendChild(li);
      return b;
    });
    var secButtons = [];
    function load(i, autoplay) {
      if (i < 0 || i >= tracks.length) return;
      if (cur >= 0) store("epis-audio-pos-" + tracks[cur].file, String(pa.currentTime));
      cur = i;
      var t = tracks[i];
      pa.src = t.file;
      title.textContent = t.title;
      readLink.href = t.page;
      chapterButtons.forEach(function (b, k) { b.setAttribute("aria-current", k === i ? "true" : "false"); });
      secs.innerHTML = "";
      secButtons = t.sections.map(function (s, k) {
        var li = document.createElement("li"), b = document.createElement("button");
        b.type = "button";
        b.innerHTML = "<span><b></b></span><small></small>";
        b.querySelector("b").textContent = k === 0 ? "Opening" : s.title;
        b.querySelector("small").textContent = clock(s.start);
        b.addEventListener("click", function () { pa.currentTime = s.start; pa.play(); });
        li.appendChild(b); secs.appendChild(li);
        return b;
      });
      var saved = parseFloat(store("epis-audio-pos-" + t.file) || "0");
      pa.addEventListener("loadedmetadata", function once() {
        pa.removeEventListener("loadedmetadata", once);
        if (saved > 5 && saved < t.duration - 5) pa.currentTime = saved;
        pa.playbackRate = parseFloat(rate.value);
      });
      try { history.replaceState(null, "", "#" + String(i + 1).padStart(2, "0")); } catch (e) { /* ignore */ }
      store("epis-audio-last", String(i));
      if (autoplay) pa.play();
    }
    pa.addEventListener("timeupdate", function () {
      if (cur < 0) return;
      var ss = tracks[cur].sections, at = 0;
      for (var k = 0; k < ss.length; k++) if (ss[k].start <= pa.currentTime + 0.5) at = k;
      secButtons.forEach(function (b, k) { b.setAttribute("aria-current", k === at ? "true" : "false"); });
      secLabel.textContent = at > 0 ? ss[at].title : "";
      if (Math.floor(pa.currentTime) % 5 === 0) store("epis-audio-pos-" + tracks[cur].file, String(pa.currentTime));
    });
    pa.addEventListener("ended", function () {
      store("epis-audio-pos-" + tracks[cur].file, "0");
      if (cur + 1 < tracks.length) load(cur + 1, true);
    });
    document.getElementById("prev").onclick = function () { load(cur - 1, true); };
    document.getElementById("next").onclick = function () { load(cur + 1, true); };
    document.getElementById("back").onclick = function () { pa.currentTime = Math.max(0, pa.currentTime - 15); };
    document.getElementById("fwd").onclick = function () { pa.currentTime = pa.currentTime + 30; };
    rate.value = store("epis-audio-rate") || "1";
    rate.onchange = function () { pa.playbackRate = parseFloat(rate.value); store("epis-audio-rate", rate.value); };
    document.addEventListener("keydown", function (e) {
      if (/INPUT|SELECT|TEXTAREA|BUTTON/.test(e.target.tagName) || e.metaKey || e.ctrlKey) return;
      if (e.key === "k" || e.key === " ") { e.preventDefault(); if (pa.paused) pa.play(); else pa.pause(); }
      if (e.key === "j") pa.currentTime = Math.max(0, pa.currentTime - 15);
      if (e.key === "l") pa.currentTime = pa.currentTime + 30;
    });
    window.addEventListener("pagehide", function () { if (cur >= 0) store("epis-audio-pos-" + tracks[cur].file, String(pa.currentTime)); });
    var fromHash = parseInt(location.hash.slice(1), 10), last = parseInt(store("epis-audio-last") || "0", 10);
    load(fromHash >= 1 && fromHash <= tracks.length ? fromHash - 1 : (last >= 0 && last < tracks.length ? last : 0), false);
  }
})();
