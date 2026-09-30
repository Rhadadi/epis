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
  // Where the site starts, worked out from this script's own address (it lives in assets/).
  var SCRIPT = document.currentScript && document.currentScript.src;
  var ROOT = SCRIPT ? new URL("../", SCRIPT).href : new URL("./", location.href).href;
  // Persian pages live under fa/ and read right to left; T() picks the text for the page's language.
  var FA = doc.lang === "fa";
  var HOME = ROOT + (FA ? "fa/" : "");
  function T(en, fa) { return FA ? fa : en; }
  function N(x) { return FA ? String(x).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }) : String(x); }
  window.EPIS_LANG = { fa: FA, T: T, N: N, home: HOME, root: ROOT };
  var THEME_NAMES = { system: T("system", "خودکار"), light: T("light", "روشن"), dark: T("dark", "تیره"), sepia: T("sepia", "کاغذی"), black: T("black", "سیاه") };
  var ICON = {
    system: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" stroke="none"/></svg>',
    light: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    dark: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/></svg>'
  };
  // A "shade" is a variant of light (sepia) or dark (black) chosen in the reading settings.
  var SHADE_BASE = { sepia: "light", black: "dark" };
  var THEME_COLOR = { light: "#F6F3EC", dark: "#0A1620", sepia: "#F3EAD6", black: "#000000" };
  var media = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
  function applyTheme(pref, persist, shade) {
    if (["system", "light", "dark"].indexOf(pref) < 0) pref = "system";
    if (shade === undefined) shade = store("epis-shade") || "";
    if (!SHADE_BASE[shade]) shade = "";
    var dark = shade ? SHADE_BASE[shade] === "dark" : pref === "dark" || (pref === "system" && media && media.matches);
    doc.dataset.theme = dark ? "dark" : "light";
    doc.dataset.themePreference = pref;
    if (shade) doc.dataset.shade = shade; else delete doc.dataset.shade;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = THEME_COLOR[shade || (dark ? "dark" : "light")];
    var btn = document.getElementById("theme");
    if (btn) {
      var next = pref === "system" ? "light" : pref === "light" ? "dark" : "system";
      btn.innerHTML = ICON[pref];
      btn.setAttribute("aria-label", T("Theme: ", "پوسته: ") + THEME_NAMES[shade || pref] + T(". Switch to ", ". رفتن به ") + THEME_NAMES[next] + ".");
      btn.title = T("Theme: ", "پوسته: ") + THEME_NAMES[shade || pref];
    }
    if (persist) { store("epistemology-theme", pref); store("epis-shade", shade); store("epis-prefs-ts", String(Date.now())); document.dispatchEvent(new Event("epis:prefs")); }
    document.dispatchEvent(new Event("epis:theme"));
  }
  applyTheme(doc.dataset.themePreference || store("epistemology-theme") || "system", false);
  if (media && media.addEventListener) media.addEventListener("change", function () {
    if ((doc.dataset.themePreference || "system") === "system") applyTheme("system", false);
  });
  var themeBtn = document.getElementById("theme");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var order = ["system", "light", "dark"];
    applyTheme(order[(order.indexOf(doc.dataset.themePreference || "system") + 1) % 3], true, "");
  });

  /* ------------------------------------------------------------ bar over the hero */
  var bar = document.querySelector(".bar");
  var hero = document.querySelector(".hero");
  var lastY = window.scrollY;
  function focused() { return doc.hasAttribute("data-focus"); }
  function barState() {
    if (!bar) return;
    var y = window.scrollY;
    var over = hero && !focused() && y < 40;
    bar.classList.toggle("clear", !!over);
    bar.classList.toggle("solid", !over);
    // In focus mode the bar slides away while you read and comes back when you scroll up.
    if (focused()) {
      var panelOpen = document.getElementById("rpanel") && !document.getElementById("rpanel").hidden;
      if (y < 80 || y < lastY - 6 || panelOpen) bar.classList.add("peek");
      else if (y > lastY + 6) bar.classList.remove("peek");
    }
    lastY = y;
  }
  barState();
  window.addEventListener("scroll", barState, { passive: true });
  window.addEventListener("resize", barState);

  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("[data-set-site-lang]");
    if (a) store("epistemology-lang", a.getAttribute("data-set-site-lang"));
  });
  if (FA) store("epistemology-lang", "fa");

  /* ------------------------------------------------------------ phone menu */
  var menuBtn = document.getElementById("menu"), mnav = document.getElementById("mnav");
  if (menuBtn && mnav) {
    var setMenu = function (open) {
      mnav.hidden = !open;
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open && bar) bar.classList.add("peek");
    };
    menuBtn.addEventListener("click", function (e) { e.stopPropagation(); setMenu(mnav.hidden); });
    document.addEventListener("click", function (e) { if (!mnav.hidden && !mnav.contains(e.target)) setMenu(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !mnav.hidden) { setMenu(false); menuBtn.focus(); } });
  }

  /* ------------------------------------------------------------ contents rail */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a[href^='#']"));
  if (tocLinks.length) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[decodeURIComponent(a.getAttribute("href").slice(1))] = a; });
    var heads = Object.keys(byId).map(function (id) { return document.getElementById(id); }).filter(Boolean);
    var spyQueued = false;
    var spy = function () {
      spyQueued = false;
      var current = null;
      for (var i = 0; i < heads.length; i++) if (heads[i].getBoundingClientRect().top < window.innerHeight * 0.35) current = heads[i].id;
      tocLinks.forEach(function (a) { a.classList.toggle("on", byId[current] === a); });
    };
    window.addEventListener("scroll", function () { if (!spyQueued) { spyQueued = true; requestAnimationFrame(spy); } }, { passive: true });
    spy();
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
    var requestedLang = new URLSearchParams(location.search).get("lang");
    setLang(requestedLang === "fa" ? "fa" : (doc.dataset.lang || "en"));
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

  /* ------------------------------------------------------------ audio for offline listening */
  // A chapter's MP3 can be saved on this device, one chapter at a time: the page puts the whole
  // file into the "epis-audio-v1" cache, and sw.js plays it from there (seeking included).
  var AUDIO_CACHE = "epis-audio-v1";
  var canSaveAudio = "caches" in window && "serviceWorker" in navigator && window.isSecureContext;
  var SAVE_ICON = {
    save: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>',
    saved: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>'
  };
  function absUrl(f) { return new URL(f, location.href).href.split(/[?#]/)[0]; }
  function megabytes(bytes) { return N(Math.max(1, Math.round(bytes / 1048576))) + T(" MB", " مگابایت"); }
  // The Persian and the English narration of a chapter share a file name; each keeps its own place.
  function posKey(f) { return "epis-audio-pos-" + (/\/fa\/audio\//.test(f) ? "fa-" : "") + String(f).split("/").pop(); }
  function audioSaved(f) {
    if (!canSaveAudio) return Promise.resolve(false);
    return caches.open(AUDIO_CACHE).then(function (c) { return c.match(absUrl(f)); })
      .then(function (r) { return !!r; }, function () { return false; });
  }
  function saveAudio(f, progress) {
    var url = absUrl(f);
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () { /* best effort */ });
    return fetch(url, { cache: "no-cache" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      if (!res.body || !res.body.getReader) return res.blob();
      var total = parseInt(res.headers.get("Content-Length") || "0", 10), got = 0, chunks = [], reader = res.body.getReader();
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) return new Blob(chunks, { type: "audio/mpeg" });
          chunks.push(r.value);
          got += r.value.length;
          if (progress && total) progress(got / total);
          return pump();
        });
      }
      return pump();
    }).then(function (blob) {
      return caches.open(AUDIO_CACHE).then(function (c) {
        return c.put(url, new Response(blob, { headers: { "Content-Type": "audio/mpeg", "Content-Length": String(blob.size) } }));
      });
    });
  }
  function removeAudio(f) { return caches.open(AUDIO_CACHE).then(function (c) { return c.delete(absUrl(f)); }); }
  // A button that saves one chapter's audio for offline listening, or removes it again. A compact
  // button shows only its icon (and the percentage while saving); its label goes to screen readers.
  function saveButton(btn, file, size, compact, onChange) {
    var state = "save";
    function show(st, pct) {
      state = st;
      btn.setAttribute("data-state", st);
      btn.disabled = st === "busy";
      var label = st === "saved" ? T("Saved for offline listening · remove", "ذخیره‌شده برای شنیدنِ بی‌اینترنت · حذف")
        : st === "busy" ? T("Saving… ", "در حالِ ذخیره… ") + N(Math.round((pct || 0) * 100)) + T("%", "٪")
        : st === "error" ? T("Couldn't save; try again", "ذخیره نشد؛ دوباره امتحان کنید")
        : T("Save for offline listening", "ذخیره برای شنیدنِ بی‌اینترنت") + (size ? " (" + megabytes(size) + ")" : "");
      var icon = SAVE_ICON[st === "saved" ? "saved" : "save"];
      if (compact) {
        btn.innerHTML = st === "busy" ? "<small>" + N(Math.round((pct || 0) * 100)) + T("%", "٪") + "</small>" : icon;
        btn.setAttribute("aria-label", label);
        btn.title = label;
      } else btn.innerHTML = icon + "<span>" + label + "</span>";
      if (onChange) onChange(st);
    }
    btn.save = function () {
      if (state === "saved" || state === "busy") return Promise.resolve();
      show("busy", 0);
      return saveAudio(file, function (p) { show("busy", p); })
        .then(function () { show("saved"); }, function () { show("error"); });
    };
    btn.addEventListener("click", function () {
      if (state === "saved") removeAudio(file).then(function () { show("save"); });
      else btn.save();
    });
    show("save");
    audioSaved(file).then(function (yes) { if (yes) show("saved"); });
    return btn;
  }
  function offlineNote() {
    return navigator.onLine ? "" : T("This chapter isn't saved on this device, and there's no connection.",
                                     "این فصل روی این دستگاه ذخیره نشده است و اینترنت هم وصل نیست.");
  }

  /* ------------------------------------------------------------ the audiobook as a ZIP download */
  // Built here in the browser from the chapter MP3s (saved ones come from the cache), so the site
  // does not have to host a second copy of the audio. Stored, not compressed: MP3s don't shrink.
  function audioFileName(i, t) {
    var name = String(t.title).replace(/^(Chapter \d+|فصل [۰-۹]+)\s*[—:]\s*/, "").replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim();
    return String(i + 1).padStart(2, "0") + " - " + name + ".mp3";
  }
  var CRC_TABLE = null;
  function crc32(bytes) {
    if (!CRC_TABLE) {
      CRC_TABLE = new Uint32Array(256);
      for (var n = 0; n < 256; n++) { var c = n; for (var k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; CRC_TABLE[n] = c >>> 0; }
    }
    var crc = 0xFFFFFFFF;
    for (var i = 0; i < bytes.length; i++) crc = CRC_TABLE[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }
  function zipBlob(files) {  // files: [{name, blob, crc}]
    var enc = new TextEncoder(), parts = [], central = [], offset = 0, now = new Date();
    var time = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    var date = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    files.forEach(function (f) {
      var name = enc.encode(f.name), size = f.blob.size, h = new DataView(new ArrayBuffer(30)), c = new DataView(new ArrayBuffer(46));
      [[0, 0x04034b50, 4], [4, 20, 2], [6, 0x0800, 2], [8, 0, 2], [10, time, 2], [12, date, 2], [14, f.crc, 4], [18, size, 4], [22, size, 4],
       [26, name.length, 2], [28, 0, 2]].forEach(function (x) { if (x[2] === 4) h.setUint32(x[0], x[1], true); else h.setUint16(x[0], x[1], true); });
      [[0, 0x02014b50, 4], [4, 20, 2], [6, 20, 2], [8, 0x0800, 2], [10, 0, 2], [12, time, 2], [14, date, 2], [16, f.crc, 4], [20, size, 4],
       [24, size, 4], [28, name.length, 2], [30, 0, 2], [32, 0, 2], [34, 0, 2], [36, 0, 2], [38, 0, 4], [42, offset, 4]]
        .forEach(function (x) { if (x[2] === 4) c.setUint32(x[0], x[1], true); else c.setUint16(x[0], x[1], true); });
      parts.push(h.buffer, name, f.blob);
      central.push(c.buffer, name);
      offset += 30 + name.length + size;
    });
    var cd = central.reduce(function (a, p) { return a + p.byteLength; }, 0), e = new DataView(new ArrayBuffer(22));
    e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true);
    e.setUint32(12, cd, true); e.setUint32(16, offset, true);
    return new Blob(parts.concat(central, [e.buffer]), { type: "application/zip" });
  }
  function chapterBlob(f, progress) {
    var fromCache = canSaveAudio ? caches.open(AUDIO_CACHE).then(function (c) { return c.match(absUrl(f)); }) : Promise.resolve(null);
    return fromCache.then(function (hit) {
      if (hit) return hit.blob();
      return fetch(absUrl(f)).then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        if (!res.body || !res.body.getReader) return res.blob();
        var total = parseInt(res.headers.get("Content-Length") || "0", 10), got = 0, chunks = [], reader = res.body.getReader();
        function pump() {
          return reader.read().then(function (r) {
            if (r.done) return new Blob(chunks, { type: "audio/mpeg" });
            chunks.push(r.value); got += r.value.length;
            if (total) progress(got / total);
            return pump();
          });
        }
        return pump();
      });
    });
  }
  function downloadAudiobook(tracks, say) {
    var folder = T("Mastering Epistemology - audiobook", "تسلط بر معرفت‌شناسی - کتاب صوتی") + "/", files = [], playlist = ["#EXTM3U"];
    return tracks.reduce(function (p, t, i) {
      return p.then(function () {
        var head = T("Collecting chapter ", "در حالِ آماده کردنِ فصلِ ") + N(i + 1) + T(" of ", " از ") + N(tracks.length);
        say(head + T("…", "…"));
        return chapterBlob(t.file, function (x) { say(head + " · " + N(Math.round(x * 100)) + T("%", "٪")); })
          .then(function (blob) { return blob.arrayBuffer().then(function (buf) { return { blob: blob, crc: crc32(new Uint8Array(buf)) }; }); })
          .then(function (f) {
            var name = audioFileName(i, t);
            files.push({ name: folder + name, blob: f.blob, crc: f.crc });
            playlist.push("#EXTINF:" + Math.round(t.duration) + "," + t.title, name);
          });
      });
    }, Promise.resolve()).then(function () {
      var m3u = new Blob([playlist.join("\r\n") + "\r\n"], { type: "application/vnd.apple.mpegurl" });
      return m3u.arrayBuffer().then(function (buf) {
        files.push({ name: folder + "playlist.m3u8", blob: m3u, crc: crc32(new Uint8Array(buf)) });
        var url = URL.createObjectURL(zipBlob(files)), a = document.createElement("a");
        a.href = url;
        a.download = T("mastering-epistemology-audiobook.zip", "mastering-epistemology-audiobook-fa.zip");
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 120000);
      });
    });
  }

  // A chapter as an EPUB 3 with Media Overlays: its text, the SMIL timing and the rest are small files the
  // site builds (listed in files.json); the MP3 is the chapter's own, from the cache when it is saved.
  function downloadEpub(listUrl, say) {
    var base = absUrl(listUrl);
    return fetch(base).then(function (r) { return r.json(); }).then(function (spec) {
      var entries = [{ name: "mimetype", blob: new Blob(["application/epub+zip"]) }];
      return spec.files.reduce(function (p, f) {
        return p.then(function () {
          var url = new URL(f[1], base).href;
          var get = /\.mp3$/i.test(url)
            ? chapterBlob(url, function (x) { say(T("Collecting the audio… ", "در حالِ آماده کردنِ صدا… ") + N(Math.round(x * 100)) + T("%", "٪")); })
            : fetch(url).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.blob(); });
          return get.then(function (blob) { entries.push({ name: f[0], blob: blob }); });
        });
      }, Promise.resolve()).then(function () {
        say(T("Packing…", "در حالِ بسته‌بندی…"));
        return Promise.all(entries.map(function (e) {
          return e.blob.arrayBuffer().then(function (buf) { return { name: e.name, blob: e.blob, crc: crc32(new Uint8Array(buf)) }; });
        }));
      }).then(function (files) {
        var zip = zipBlob(files), url = URL.createObjectURL(new Blob([zip], { type: "application/epub+zip" })), a = document.createElement("a");
        a.href = url;
        a.download = spec.name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 120000);
      });
    });
  }
  function epubButton(btn, listUrl, note) {
    btn.addEventListener("click", function () {
      btn.disabled = true;
      if (note) note.hidden = false;
      var say = function (m) { if (note) note.textContent = m; };
      downloadEpub(listUrl, say).then(function () { say(T("Your download has started.", "دریافت شروع شد.")); },
                                      function () { say(T("The download failed; try again.", "دریافت انجام نشد؛ دوباره امتحان کنید.")); })
        .then(function () { btn.disabled = false; });
    });
  }
  document.querySelectorAll("button[data-epub]").forEach(function (b) {
    epubButton(b, b.getAttribute("data-epub"), document.querySelector("[data-epub-note]"));
  });

  /* ------------------------------------------------------------ read-along page */
  // The narration's text, one element per spoken line with its times; the line being read is marked
  // and kept in view (unless the reader has just scrolled), and a tap on a line plays from there.
  var raText = document.querySelector(".ra-text");
  if (raText) {
    var ra = document.querySelector(".ra-bar audio"), raRate = document.querySelector(".ra-rate");
    var raLines = Array.prototype.slice.call(raText.querySelectorAll(".line")), raNow = -1, lastScroll = 0;
    var raKey = posKey(ra.getAttribute("src"));
    raRate.value = store("epis-audio-rate") || "1";
    raRate.addEventListener("change", function () { ra.playbackRate = parseFloat(raRate.value); store("epis-audio-rate", raRate.value); });
    ra.addEventListener("loadedmetadata", function () {
      ra.playbackRate = parseFloat(raRate.value);
      var saved = parseFloat(store(raKey) || "0");
      if (saved > 5 && saved < ra.duration - 5 && !ra.currentTime) ra.currentTime = saved;
    });
    window.addEventListener("wheel", function () { lastScroll = Date.now(); }, { passive: true });
    window.addEventListener("touchmove", function () { lastScroll = Date.now(); }, { passive: true });
    ra.addEventListener("timeupdate", function () {
      var t = ra.currentTime, lo = 0, hi = raLines.length - 1, at = -1;
      while (lo <= hi) {  // the last line that has begun
        var mid = (lo + hi) >> 1;
        if (parseFloat(raLines[mid].getAttribute("data-b")) <= t + 0.05) { at = mid; lo = mid + 1; } else hi = mid - 1;
      }
      if (at !== raNow) {
        if (raNow >= 0) raLines[raNow].classList.remove("now");
        raNow = at;
        if (at >= 0) {
          raLines[at].classList.add("now");
          if (!ra.paused && Date.now() - lastScroll > 4000) raLines[at].scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }
      if (Math.floor(t) % 5 === 0) store(raKey, String(t));
    });
    ra.addEventListener("ended", function () { store(raKey, "0"); });
    ra.addEventListener("error", function () { var m = offlineNote(); if (m) { var n = document.querySelector("[data-epub-note]"); n.hidden = false; n.textContent = m; } });
    window.addEventListener("pagehide", function () { if (ra.currentTime > 5) store(raKey, String(ra.currentTime)); });
    raText.addEventListener("click", function (e) {
      var line = e.target.closest(".line");
      if (!line || (window.getSelection && String(window.getSelection()).length)) return;
      ra.currentTime = parseFloat(line.getAttribute("data-b"));
      ra.play();
    });
  }

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
    dock.setAttribute("aria-label", T("Audio player", "پخش‌کنندهٔ صوتی"));
    dock.innerHTML =
      '<img alt="" src="' + card.getAttribute("data-thumb") + '">' +
      '<div class="t"></div>' +
      '<div class="x"><select class="spd" aria-label="' + T("Playback speed", "سرعتِ پخش") + '">' +
      ["0.8", "0.9", "1", "1.1", "1.25", "1.5", "1.75"].map(function (v) { return "<option>" + v + "</option>"; }).join("") +
      '</select><button type="button" class="close" aria-label="' + T("Close player", "بستنِ پخش‌کننده") + '">✕</button></div>' +
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
      document.querySelectorAll(".listen .lsecs button").forEach(function (c, k) { c.classList.toggle("on", k === i); });
      if (Math.floor(audio.currentTime) % 5 === 0) store(trackKey, String(audio.currentTime));
    });
    audio.addEventListener("ended", function () { store(trackKey, "0"); });
    audio.addEventListener("error", function () { var m = offlineNote(); if (m) dock.querySelector(".s").textContent = m; });
    audio.addEventListener("play", function () { card.classList.add("playing"); card.querySelector(".play").setAttribute("aria-label", T("Pause", "توقف")); });
    audio.addEventListener("pause", function () { card.classList.remove("playing"); card.querySelector(".play").setAttribute("aria-label", T("Play the narrated chapter", "پخش روایت صوتی فصل")); });
    window.addEventListener("pagehide", function () { if (audio.currentTime > 5) store(trackKey, String(audio.currentTime)); });
    if ("mediaSession" in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: card.getAttribute("data-title"), artist: T("Mastering Epistemology", "تسلط بر معرفت‌شناسی"), album: T("Audio edition", "نسخهٔ صوتی"),
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
    trackKey = posKey(card.getAttribute("data-audio"));
    // the small menu: saving and downloading the chapter, reading along, its sections
    var acts = card.querySelector(".lacts"), more = card.querySelector(".more"), menu = card.querySelector(".lmenu");
    var openMenu = function (on) { menu.hidden = !on; more.setAttribute("aria-expanded", String(on)); };
    more.addEventListener("click", function (e) { e.stopPropagation(); openMenu(menu.hidden); });
    document.addEventListener("click", function (e) { if (!menu.hidden && !menu.contains(e.target)) openMenu(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !menu.hidden) { openMenu(false); more.focus(); } });
    if (canSaveAudio) {
      var sb = document.createElement("button");
      sb.type = "button";
      sb.className = "save-audio";
      acts.appendChild(sb);
      saveButton(sb, card.getAttribute("data-audio"), parseInt(card.getAttribute("data-size") || "0", 10), false);
    }
    var mp3 = document.createElement("a");
    mp3.className = "save-audio mp3";
    mp3.href = card.getAttribute("data-audio");
    mp3.setAttribute("download", card.getAttribute("data-title").replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim() + ".mp3");
    mp3.innerHTML = SAVE_ICON.save + "<span>" + T("Download MP3", "دریافتِ MP3") + "</span>";
    acts.appendChild(mp3);
    if (card.hasAttribute("data-readalong")) {
      var ral = document.createElement("a");
      ral.className = "save-audio";
      ral.href = card.getAttribute("data-readalong");
      ral.innerHTML = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h13"/></svg><span>' + T("Read along", "خواندن همراه با صدا") + "</span>";
      acts.appendChild(ral);
      var eb = document.createElement("button");
      eb.type = "button";
      eb.className = "save-audio";
      eb.innerHTML = SAVE_ICON.save + "<span>" + T("EPUB with audio", "EPUB همراه با صدا") + "</span>";
      acts.appendChild(eb);
      var en = document.createElement("p");
      en.className = "note epub-note";
      en.hidden = true;
      acts.appendChild(en);
      epubButton(eb, card.getAttribute("data-epub"), en);
    }
    var play = card.querySelector(".play");
    var saved = parseFloat(store(trackKey) || "0");
    if (saved > 20) card.querySelector(".resume").textContent = T("Resume from ", "ادامه از ") + clock(saved);
    play.addEventListener("click", function () {
      if (audio && !audio.paused) { audio.pause(); return; }
      var s = parseFloat(store(trackKey) || "0");
      playFrom(audio ? null : (s > 20 ? s : 0));
    });
    document.querySelectorAll("[data-listen]").forEach(function (b) {
      b.addEventListener("click", function () { play.click(); });
    });
    document.querySelectorAll("[data-at]").forEach(function (b) {
      b.addEventListener("click", function () { openMenu(false); playFrom(parseFloat(b.getAttribute("data-at"))); });
    });
  }

  /* ------------------------------------------------------------ the chapters list at the top of a chapter */
  document.querySelectorAll("details.chlist").forEach(function (d) {
    document.addEventListener("click", function (e) { if (d.open && !d.contains(e.target)) d.open = false; });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && d.open) { d.open = false; d.querySelector("summary").focus(); }
    });
    d.addEventListener("toggle", function () {  // the current chapter in view
      var cur = d.open && d.querySelector("[aria-current]");
      if (cur) cur.scrollIntoView({ block: "center" });
    });
  });

  /* ------------------------------------------------------------ the audiobook section (audio and download pages) */
  // save every chapter here, download them all as a ZIP, copy the podcast feed
  function audiobookTools(tracks, saveButtons) {
    var saveAll = document.querySelector("[data-save-all]");
    if (saveAll && canSaveAudio) {
      var saveNote = document.querySelector("[data-save-all-note]");
      saveAll.hidden = false;
      saveAll.addEventListener("click", function () {
        saveAll.disabled = true;
        saveNote.hidden = false;
        saveButtons.reduce(function (p, sb, k) {
          return p.then(function () {
            saveNote.textContent = T("Saving chapter ", "در حالِ ذخیرهٔ فصلِ ") + N(k + 1) + T(" of ", " از ") + N(saveButtons.length) + T("…", "…");
            return sb.save();
          });
        }, Promise.resolve()).then(function () {
          saveAll.disabled = false;
          var missing = saveButtons.filter(function (sb) { return sb.getAttribute("data-state") !== "saved"; }).length;
          saveNote.textContent = missing ? T("Some chapters couldn't be saved; try again.", "چند فصل ذخیره نشد؛ دوباره امتحان کنید.")
            : T("All chapters are saved on this device.", "همهٔ فصل‌ها روی این دستگاه ذخیره شده‌اند.");
        });
      });
    }
    var zipBtn = document.querySelector("[data-zip]");
    if (zipBtn) zipBtn.addEventListener("click", function () {
      var note = document.querySelector("[data-zip-note]");
      zipBtn.disabled = true;
      note.hidden = false;
      downloadAudiobook(tracks, function (msg) { note.textContent = msg; })
        .then(function () { note.textContent = T("Your download has started.", "دریافت شروع شد."); },
              function () { note.textContent = T("The download failed; check the connection and try again.", "دریافت انجام نشد؛ اتصال را بررسی کنید و دوباره امتحان کنید."); })
        .then(function () { zipBtn.disabled = false; });
    });
    document.querySelectorAll("[data-copy]").forEach(function (b) {
      b.addEventListener("click", function () {
        var done = function () { var t = b.textContent; b.textContent = T("Copied", "کپی شد"); setTimeout(function () { b.textContent = t; }, 1600); };
        if (navigator.clipboard) navigator.clipboard.writeText(b.getAttribute("data-copy")).then(done, function () { /* ignore */ });
      });
    });
  }

  /* ------------------------------------------------------------ download page: every chapter's files */
  var dlList = document.getElementById("dl-list");
  if (dlList && window.TRACKS) {
    var dlSave = [];
    window.TRACKS.forEach(function (t, i) {
      var li = document.createElement("li");
      li.innerHTML = '<span class="n"></span><span class="t"><a></a><small></small></span><span class="a"></span>';
      li.querySelector(".n").textContent = N(i + 1);
      var a = li.querySelector(".t a");
      a.textContent = t.title.replace(/^(Chapter \d+|فصل [۰-۹]+|پیوست) — /, "");
      a.href = t.page;
      li.querySelector(".t small").textContent = N(Math.round(t.duration / 60)) + T(" min · ", " دقیقه · ") + N(Math.round((t.size || 0) / 1e6)) + T(" MB", " مگابایت");
      var acts = li.querySelector(".a");
      if (canSaveAudio) {
        var sb = document.createElement("button");
        sb.type = "button";
        sb.className = "save-audio compact";
        acts.appendChild(sb);
        dlSave.push(saveButton(sb, t.file, t.size || 0, true, function (st) { li.toggleAttribute("data-saved", st === "saved"); }));
      }
      var mp3 = document.createElement("a");
      mp3.className = "save-audio compact";
      mp3.href = t.file;
      mp3.setAttribute("download", audioFileName(i, t));
      mp3.textContent = "MP3";
      acts.appendChild(mp3);
      if (t.epub) {
        var eb = document.createElement("button");
        eb.type = "button";
        eb.className = "save-audio compact";
        eb.textContent = "EPUB";
        eb.title = T("EPUB with the narration, read along", "EPUB همراه با روایت، خواندن همراه با صدا");
        acts.appendChild(eb);
        epubButton(eb, t.epub, document.querySelector("[data-epub-note]"));
      }
      dlList.appendChild(li);
    });
    audiobookTools(window.TRACKS, dlSave);
  }

  /* ------------------------------------------------------------ full player (audio page) */
  var player = document.getElementById("player");
  if (player && window.TRACKS) {
    var tracks = window.TRACKS, cur = -1;
    var pa = player.querySelector("audio"), rate = player.querySelector("#rate");
    var list = document.getElementById("chapters"), secs = document.getElementById("sections");
    var title = player.querySelector("h2"), secLabel = player.querySelector(".sec"), readLink = document.getElementById("read");
    var art = window.TRACK_ART || {};
    var saveButtons = [];
    var chapterButtons = tracks.map(function (t, i) {
      var li = document.createElement("li"), b = document.createElement("button");
      b.type = "button";
      b.innerHTML = '<img alt="" loading="lazy"><span><b></b><small></small></span><small class="d"></small>';
      b.querySelector("img").src = art[i] || "";
      b.querySelector("b").textContent = t.title.replace(/^(Chapter \d+|فصل [۰-۹]+|پیوست) — /, "");
      b.querySelector("span small").textContent = T("Chapter ", "فصل ") + N(i + 1);
      b.querySelector(".d").textContent = N(Math.round(t.duration / 60)) + T(" min", " دقیقه");
      b.addEventListener("click", function () { load(i, true); });
      li.appendChild(b); list.appendChild(li);
      if (canSaveAudio) {
        var sb = document.createElement("button");
        sb.type = "button";
        sb.className = "save-audio compact";
        li.appendChild(sb);
        saveButtons.push(saveButton(sb, t.file, t.size || 0, true, function (st) { li.toggleAttribute("data-saved", st === "saved"); }));
      }
      return b;
    });
    audiobookTools(tracks, saveButtons);
    function markOffline() { list.classList.toggle("offline", !navigator.onLine); }
    window.addEventListener("online", markOffline);
    window.addEventListener("offline", markOffline);
    markOffline();
    pa.addEventListener("error", function () { var m = offlineNote(); if (m) secLabel.textContent = m; });
    var secButtons = [];
    function load(i, autoplay) {
      if (i < 0 || i >= tracks.length) return;
      if (cur >= 0) store(posKey(tracks[cur].file), String(pa.currentTime));
      cur = i;
      var t = tracks[i];
      pa.src = t.file;
      var dl = document.getElementById("dl");
      if (dl) { dl.href = t.file; dl.setAttribute("download", audioFileName(i, t)); }
      var raLink = document.getElementById("ra");
      if (raLink) { raLink.hidden = !t.readalong; if (t.readalong) raLink.href = t.readalong; }
      title.textContent = t.title;
      readLink.href = t.page;
      chapterButtons.forEach(function (b, k) { b.setAttribute("aria-current", k === i ? "true" : "false"); });
      secs.innerHTML = "";
      secButtons = t.sections.map(function (s, k) {
        var li = document.createElement("li"), b = document.createElement("button");
        b.type = "button";
        b.innerHTML = "<span><b></b></span><small></small>";
        b.querySelector("b").textContent = k === 0 ? T("Opening", "آغاز") : s.title;
        b.querySelector("small").textContent = clock(s.start);
        b.addEventListener("click", function () { pa.currentTime = s.start; pa.play(); });
        li.appendChild(b); secs.appendChild(li);
        return b;
      });
      var saved = parseFloat(store(posKey(t.file)) || "0");
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
      if (Math.floor(pa.currentTime) % 5 === 0) store(posKey(tracks[cur].file), String(pa.currentTime));
    });
    pa.addEventListener("ended", function () {
      store(posKey(tracks[cur].file), "0");
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
    window.addEventListener("pagehide", function () { if (cur >= 0) store(posKey(tracks[cur].file), String(pa.currentTime)); });
    var fromHash = parseInt(location.hash.slice(1), 10), last = parseInt(store("epis-audio-last") || "0", 10);
    load(fromHash >= 1 && fromHash <= tracks.length ? fromHash - 1 : (last >= 0 && last < tracks.length ? last : 0), false);
  }
  /* ------------------------------------------------------------ reading settings */
  var SIZES = [0.85, 0.92, 1, 1.08, 1.16, 1.25, 1.35];
  // line spacing is kept by name; the CSS gives each language its own values (Persian script needs more room)
  function leadName(v) {
    return typeof v === "number" ? (v < 1.7 ? "compact" : v > 1.8 ? "airy" : "normal") : (v || "normal");
  }
  function readerPrefs() {
    try { return JSON.parse(store("epis-reader") || "{}") || {}; } catch (e) { return {}; }
  }
  function applyReader(r) {
    if (r.scale && r.scale !== 1) doc.style.setProperty("--read-scale", r.scale); else doc.style.removeProperty("--read-scale");
    doc.style.removeProperty("--read-lead");
    if (leadName(r.lead) !== "normal") doc.dataset.lead = leadName(r.lead); else delete doc.dataset.lead;
    if (r.width) doc.dataset.width = r.width; else delete doc.dataset.width;
    if (r.font) doc.dataset.font = r.font; else delete doc.dataset.font;
    store("epis-reader", JSON.stringify(r));
    store("epis-prefs-ts", String(Date.now()));
    document.dispatchEvent(new Event("epis:prefs"));
  }
  var article = document.querySelector("article[data-slug]");
  var readerBtn = document.getElementById("reader");
  var panel = null;
  function seg(name, options, current) {
    return '<div class="row"><span>' + name + '</span><div class="seg" role="group" aria-label="' + name + '">' +
      options.map(function (o) {
        return '<button type="button" data-' + o[0] + '="' + o[1] + '" aria-pressed="' + (o[1] === current) + '"' +
          (o[3] ? ' style="' + o[3] + '"' : "") + ">" + o[2] + "</button>";
      }).join("") + "</div></div>";
  }
  function themeChoice() {
    if (doc.dataset.shade) return doc.dataset.shade;
    var pref = doc.dataset.themePreference || "system";
    return pref === "system" ? "auto" : pref;
  }
  function buildPanel() {
    var r = readerPrefs();
    var lead = leadName(r.lead);
    var scale = r.scale || 1;
    panel = document.createElement("div");
    panel.className = "rpanel";
    panel.id = "rpanel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", T("Reading settings", "تنظیمات خواندن"));
    panel.hidden = true;
    var swatch = function (key, label, bg, fg) {
      return '<button type="button" data-shade-choice="' + key + '" aria-pressed="' + (themeChoice() === key) + '"><i style="background:' + bg +
        ";color:" + fg + '">' + (key === "auto" ? "◐" : T("A", "آ")) + "</i>" + label + "</button>";
    };
    panel.innerHTML = '<h2>' + T("Reading settings", "تنظیمات خواندن") + '</h2>' +
      '<div class="row"><span>' + T("Text size", "اندازهٔ متن") + '</span><div class="seg"><button type="button" class="sz" data-size="-1" aria-label="' + T("Smaller text", "متن کوچک‌تر") + '">A−</button>' +
      '<output aria-live="polite"></output><button type="button" class="sz" data-size="1" aria-label="' + T("Larger text", "متن بزرگ‌تر") + '">A+</button></div></div>' +
      seg(T("Line spacing", "فاصلهٔ سطرها"), [["lead", "compact", T("Compact", "فشرده")], ["lead", "normal", T("Normal", "معمولی")], ["lead", "airy", T("Airy", "باز")]], lead) +
      seg(T("Line length", "پهنای سطر"), [["width", "narrow", T("Narrow", "باریک")], ["width", "", T("Normal", "معمولی")], ["width", "wide", T("Wide", "پهن")]], r.width || "") +
      (FA ? seg("قلم", [["font", "", "وزیرمتن", "font-family:'Vazirmatn',sans-serif"], ["font", "naskh", "نسخ", "font-family:'Noto Naskh Arabic',serif"],
          ["font", "sans", "قلمِ دستگاه", "font-family:system-ui,-apple-system,'Segoe UI',Tahoma,sans-serif"]], r.font === "naskh" || r.font === "sans" ? r.font : "")
        : seg("Typeface", [["font", "", "Serif", "font-family:var(--serif)"], ["font", "sans", "Sans", "font-family:system-ui,sans-serif"],
          ["font", "readable", "Readable", "font-family:'Atkinson Hyperlegible',sans-serif"]], r.font || "")) +
      '<div class="row"><span>' + T("Theme", "پوسته") + '</span><div class="swatches">' +
      swatch("auto", T("Auto", "خودکار"), "linear-gradient(135deg,#F6F3EC 50%,#0A1620 50%)", "transparent") +
      swatch("light", T("Light", "روشن"), "#F6F3EC", "#1B2730") + swatch("sepia", T("Sepia", "کاغذی"), "#F3EAD6", "#3A2E22") +
      swatch("dark", T("Dark", "تیره"), "#0A1620", "#E8EEF1") + swatch("black", T("Black", "سیاه"), "#000", "#E6E8E9") + "</div></div>" +
      (article ? '<button type="button" class="wide-btn primary" data-focus-toggle></button>' : "") +
      '<div class="links"><button type="button" data-reset>' + T("Reset to defaults", "بازگشت به پیش‌فرض") + '</button>' +
      '<a href="' + HOME + 'guide/mastering-epistemology' + T("", "-fa") + '.epub" download>' + T("Download the guide as an EPUB for e-readers", "دریافتِ راهنما به صورت EPUB برای کتاب‌خوان") + '</a>' +
      ("serviceWorker" in navigator ? '<button type="button" data-offline>' + T("Save the whole guide for offline reading", "ذخیرهٔ کلِ راهنما برای خواندنِ بی‌اینترنت") + '</button>' : "") +
      '</div><p class="note" data-offline-note hidden></p>';
    document.body.appendChild(panel);
    var out = panel.querySelector("output");
    var showSize = function () { out.textContent = N(Math.round((readerPrefs().scale || 1) * 100)) + T("%", "٪"); };
    showSize();
    panel.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      var r = readerPrefs();
      if (b.hasAttribute("data-size")) {
        var i = SIZES.indexOf(r.scale || 1); if (i < 0) i = 2;
        r.scale = SIZES[Math.max(0, Math.min(SIZES.length - 1, i + parseInt(b.getAttribute("data-size"), 10)))];
        applyReader(r); showSize();
      } else if (b.hasAttribute("data-lead")) {
        r.lead = b.getAttribute("data-lead"); applyReader(r);
      } else if (b.hasAttribute("data-width")) {
        r.width = b.getAttribute("data-width"); applyReader(r);
      } else if (b.hasAttribute("data-font")) {
        r.font = b.getAttribute("data-font"); applyReader(r);
      } else if (b.hasAttribute("data-shade-choice")) {
        var c = b.getAttribute("data-shade-choice");
        applyTheme({ auto: "system", light: "light", sepia: "light", dark: "dark", black: "dark" }[c], true, SHADE_BASE[c] ? c : "");
      } else if (b.hasAttribute("data-reset")) {
        applyReader({}); applyTheme("system", true, ""); showSize();
      } else if (b.hasAttribute("data-offline")) {
        saveOffline(b);
      } else return;
      syncPanel();
    });
  }
  function syncPanel() {
    if (!panel) return;
    var r = readerPrefs();
    var lead = leadName(r.lead);
    var mark = function (attr, value) {
      panel.querySelectorAll("[data-" + attr + "]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-" + attr) === value); });
    };
    mark("lead", lead); mark("width", r.width || ""); mark("shade-choice", themeChoice());
    // each language offers its own typefaces; one chosen in the other language shows as the default here
    mark("font", FA ? (r.font === "naskh" || r.font === "sans" ? r.font : "") : (r.font === "naskh" ? "" : r.font || ""));
    var f = panel.querySelector(".wide-btn[data-focus-toggle]");
    if (f) f.textContent = focused() ? T("Leave focus mode", "خروج از حالت تمرکز") : T("Read in focus mode", "خواندن در حالت تمرکز");
  }
  document.addEventListener("epis:theme", syncPanel);
  function togglePanel(open) {
    if (!panel) buildPanel();
    if (open === undefined) open = panel.hidden;
    panel.hidden = !open;
    if (readerBtn) readerBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) { syncPanel(); barState(); var first = panel.querySelector("button"); if (first) first.focus({ preventScroll: true }); }
  }
  if (readerBtn) {
    readerBtn.addEventListener("click", function (e) { e.stopPropagation(); togglePanel(); });
    document.addEventListener("click", function (e) {
      if (panel && !panel.hidden && !panel.contains(e.target) && e.target !== readerBtn) togglePanel(false);
    });
  }

  /* ------------------------------------------------------------ offline copy */
  function saveOffline(btn, note) {
    note = note || panel.querySelector("[data-offline-note]");
    note.hidden = false;
    note.textContent = T("Preparing…", "در حال آماده‌سازی…");
    btn.disabled = true;
    navigator.serviceWorker.ready.then(function (reg) {
      var ch = new MessageChannel();
      ch.port1.onmessage = function (e) {
        var d = e.data || {};
        if (d.done) { note.textContent = T("Saved. The guide, the concepts and the map now open without a connection. To listen offline too, save chapters from the audio page or a chapter's Listen card.", "ذخیره شد. راهنما، مفاهیم و نقشه اکنون بدون اینترنت هم باز می‌شوند. برای شنیدنِ بی‌اینترنت، فصل‌ها را از صفحهٔ صوت یا کادرِ «شنیدن» در هر فصل ذخیره کنید."); btn.disabled = false; }
        else if (d.error) { note.textContent = T("Could not save everything: ", "همه‌چیز ذخیره نشد: ") + d.error; btn.disabled = false; }
        else note.textContent = T("Saving… ", "در حال ذخیره… ") + N(d.n) + T(" of ", " از ") + N(d.of);
      };
      reg.active.postMessage({ type: "save-offline" }, [ch.port2]);
    }).catch(function () { note.textContent = T("Offline reading isn't available in this browser.", "خواندنِ بی‌اینترنت در این مرورگر در دسترس نیست."); btn.disabled = false; });
  }
  // the same, from a button on a page (the download page)
  document.querySelectorAll("[data-offline-page]").forEach(function (b) {
    if (!("serviceWorker" in navigator)) { b.hidden = true; return; }
    b.addEventListener("click", function () { saveOffline(b, document.querySelector("[data-offline-page-note]")); });
  });
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register(ROOT + "sw.js", { scope: ROOT }).catch(function () { /* offline support is optional */ });
    });
  }

  /* ------------------------------------------------------------ focus mode */
  var focusBtn = document.getElementById("focus");
  function anchorInView() {
    // The first heading or paragraph at the top of the screen, to keep your place when the layout changes.
    var els = document.querySelectorAll(".prose > *");
    for (var i = 0; i < els.length; i++) if (els[i].getBoundingClientRect().bottom > 90) return els[i];
    return null;
  }
  function setFocus(on) {
    if (!article) return;
    var keep = window.scrollY > 200 ? anchorInView() : null;
    if (on) doc.setAttribute("data-focus", ""); else doc.removeAttribute("data-focus");
    store("epis-focus", on ? "1" : "0");
    if (focusBtn) focusBtn.setAttribute("aria-pressed", on ? "true" : "false");
    if (keep) keep.scrollIntoView({ block: "start" }); else if (on) window.scrollTo(0, 0);
    if (bar) bar.classList.add("peek");
    barState(); syncPanel(); progress();
  }
  if (article) {
    if (focusBtn) {
      focusBtn.setAttribute("aria-pressed", focused() ? "true" : "false");
      focusBtn.addEventListener("click", function () { setFocus(!focused()); });
    }
    document.addEventListener("click", function (e) {
      if (e.target.closest("[data-focus-toggle]")) { setFocus(!focused()); if (panel) togglePanel(false); }
    });
  }
  document.addEventListener("keydown", function (e) {
    if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "Escape") {
      if (panel && !panel.hidden) { togglePanel(false); if (readerBtn) readerBtn.focus(); }
      else if (focused()) setFocus(false);
    } else if ((e.key === "f" || e.key === "F") && article && !document.getElementById("player")) {
      e.preventDefault(); setFocus(!focused());
    } else if ((e.key === "a" || e.key === "A") && readerBtn) {
      e.preventDefault(); togglePanel();
    }
  });

  /* ------------------------------------------------------------ reading progress */
  function readProgress() {
    try { return JSON.parse(store("epis-progress") || "{}") || {}; } catch (e) { return {}; }
  }
  var readbar = null, leftEls = [], chip = null, chipTimer = 0, saveTimer = 0, lastP = 0;
  function articleFraction() {
    var r = article.getBoundingClientRect(), h = article.offsetHeight - window.innerHeight * 0.5;
    return Math.max(0, Math.min(1, (window.innerHeight * 0.3 - r.top) / Math.max(1, h)));
  }
  function currentHeading() {
    var hs = article.querySelectorAll(".prose h2[id]"), cur = null;
    for (var i = 0; i < hs.length; i++) if (hs[i].getBoundingClientRect().top < window.innerHeight * 0.35) cur = hs[i];
    return cur;
  }
  function saveProgress() {
    var all = readProgress(), slug = article.getAttribute("data-slug"), prev = all[slug] || {};
    var h = currentHeading();
    var thumb = (card && card.getAttribute("data-thumb")) || (hero && hero.querySelector("img") && hero.querySelector("img").getAttribute("src")) || "";
    var title = article.querySelector(".ftitle");
    var titles = prev.titles || {};
    if (title) titles[FA ? "fa" : "en"] = title.textContent;
    all[slug] = {
      titles: titles, htLang: FA ? "fa" : "en",
      p: Math.max(prev.p || 0, lastP), at: lastP, h: h ? h.id : "", ht: h ? (h.querySelector(".ht") || h).textContent : "",
      t: Date.now(), title: title ? title.textContent : document.title, label: (article.querySelector(".focus-head .kicker") || {}).textContent || "",
      img: thumb ? new URL(thumb, location.href).href : ""
    };
    store("epis-progress", JSON.stringify(all));
    document.dispatchEvent(new Event("epis:progress"));
  }
  function progress(e) {
    if (!article) return;
    lastP = articleFraction();
    if (readbar) readbar.firstChild.style.transform = "scaleX(" + lastP.toFixed(4) + ")";
    var mins = Math.ceil(parseInt(article.getAttribute("data-read-min"), 10) * (1 - lastP));
    var text = lastP > 0.97 ? T("Finished", "تمام شد") : N(mins) + T(" min left", " دقیقه مانده");
    leftEls.forEach(function (el) { el.textContent = text; });
    if (chip && focused() && lastP > 0.01) {
      chip.textContent = text; chip.classList.add("on");
      clearTimeout(chipTimer); chipTimer = setTimeout(function () { chip.classList.remove("on"); }, 1600);
    }
    // Only a real scroll counts as reading; opening a page at the top must not erase where you were.
    if (e && e.type === "scroll" && lastP > 0.01) { clearTimeout(saveTimer); saveTimer = setTimeout(saveProgress, 1500); }
  }
  if (article) {
    readbar = document.createElement("div"); readbar.className = "readbar"; readbar.innerHTML = "<i></i>";
    document.body.appendChild(readbar);
    var side = document.querySelector(".side");
    if (side) { var l = document.createElement("p"); l.className = "left"; side.appendChild(l); leftEls.push(l); }
    chip = document.createElement("div"); chip.className = "leftchip"; chip.setAttribute("aria-hidden", "true");
    document.body.appendChild(chip);
    window.addEventListener("scroll", progress, { passive: true });
    window.addEventListener("resize", progress);
    var scrolled = false;
    window.addEventListener("scroll", function () { scrolled = true; }, { passive: true, once: true });
    window.addEventListener("pagehide", function () { if (scrolled && lastP > 0.01) saveProgress(); });
    progress();
    // Offer to continue where you stopped last time.
    var mine = readProgress()[article.getAttribute("data-slug")];
    if (mine && !location.hash && mine.at > 0.03 && mine.at < 0.97) {
      setTimeout(function () {
        if (window.scrollY > 300) return;
        var toast = document.createElement("div");
        toast.className = "toast"; toast.setAttribute("role", "status");
        var span = document.createElement("span");
        span.textContent = mine.ht ? T("Continue from “", "ادامه از «") + mine.ht + T("”?", "»؟") : T("Continue where you stopped?", "از همان‌جا که ماندید ادامه می‌دهید؟");
        var go = document.createElement("button"); go.type = "button"; go.className = "go"; go.textContent = T("Continue", "ادامه");
        var x = document.createElement("button"); x.type = "button"; x.className = "x"; x.setAttribute("aria-label", T("Dismiss", "بستن")); x.textContent = "✕";
        toast.appendChild(span); toast.appendChild(go); toast.appendChild(x);
        document.body.appendChild(toast);
        requestAnimationFrame(function () { toast.classList.add("on"); });
        var close = function () { toast.classList.remove("on"); setTimeout(function () { toast.remove(); }, 400); };
        go.onclick = function () {
          var top = article.getBoundingClientRect().top + window.scrollY;
          var h = article.offsetHeight - window.innerHeight * 0.5;
          window.scrollTo({ top: top + mine.at * h - window.innerHeight * 0.3 });
          close();
        };
        x.onclick = close;
        setTimeout(close, 15000);
      }, 700);
    }
  }

  /* ------------------------------------------------------------ progress on the start and contents pages */
  var progressAll = readProgress();
  document.querySelectorAll(".card[data-slug]").forEach(function (c) {
    var e = progressAll[c.getAttribute("data-slug")], pic = c.querySelector(".pic");
    if (!e || !pic || e.p < 0.02) return;
    if (e.p >= 0.97) { var d = document.createElement("span"); d.className = "done"; d.textContent = T("Read", "خوانده شد"); pic.appendChild(d); }
    else { var b = document.createElement("span"); b.className = "prog"; b.innerHTML = "<i></i>"; b.firstChild.style.width = Math.round(e.p * 100) + "%"; pic.appendChild(b); }
  });
  var resume = document.getElementById("resume");
  if (resume) {
    var latest = null;
    Object.keys(progressAll).forEach(function (slug) {
      var e = progressAll[slug];
      if (e.at < 0.97 && e.at > 0.01 && (!latest || e.t > latest.t)) latest = Object.assign({ slug: slug }, e);
    });
    if (latest) {
      var a = document.createElement("a");
      a.className = "resume-card"; a.href = HOME + "guide/" + latest.slug + ".html";
      a.innerHTML = '<img alt=""><div><span class="kicker">' + T("Continue reading", "ادامهٔ خواندن") + '</span><b></b><small></small><span class="bar2"><i></i></span></div>' +
        '<span class="go"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>';
      if (latest.img) a.querySelector("img").src = latest.img; else a.querySelector("img").remove();
      var titles = latest.titles || {};
      var chNum = parseInt(latest.slug, 10);
      a.querySelector("b").textContent = titles[FA ? "fa" : "en"] || latest.title;
      a.querySelector("small").textContent = (chNum ? (chNum <= 16 ? T("Chapter ", "فصل ") + N(chNum) : T("Appendix", "پیوست")) + " · " : "") +
        N(Math.round(latest.at * 100)) + T("% read", "٪ خوانده‌شده") +
        (latest.ht && (latest.htLang || "en") === (FA ? "fa" : "en") ? T(" · at “", " · در «") + latest.ht + T("”", "»") : "");
      a.querySelector(".bar2 i").style.width = Math.round(latest.at * 100) + "%";
      resume.appendChild(a);
    }
  }
})();
