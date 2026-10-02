/* The map of the guide (map/index.html, fa/map/index.html), drawn as a planisphere.
   The guide's own question sits at the centre. Its sixteen chapters ride the inner orbit as medallions with their
   paintings, coloured by the guide's five parts; every section of every chapter is a star on the outer orbit, and the
   arcs through the interior are the guide's cross-references between chapters, gathered through the hub of each part.
   Choosing a chapter turns the wheel to it and widens it so its sections can be read; choosing a section shows where it
   leads and what leads to it. The learning paths of the contents page are drawn as routes, and the reader's progress
   (kept by site.js in localStorage) rings each medallion. Data: the page's #mapdata, written by tools/site/build.py. */
(function () {
  "use strict";
  var dataEl = document.getElementById("mapdata"), chart = document.querySelector("#chart .chart");
  if (!dataEl || !chart) return;
  var D = JSON.parse(dataEl.textContent);
  var U = D.ui, FA = D.lang === "fa", CH = D.chapters, S = D.sections, PARTS = D.parts, CON = D.concepts, PATHS = D.paths;
  var svg = chart.querySelector("svg.wheel"), panel = chart.querySelector(".chart-panel");
  var TAU = Math.PI * 2;
  var reduce = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var digits = function (n) { return FA ? String(n).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }) : String(n); };
  var fmt = function (s, o) { return s.replace(/\{(\w+)\}/g, function (_, k) { return o[k] === undefined ? "" : digits(o[k]); }); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var P = function (r, a) { return [r * Math.cos(a), r * Math.sin(a)]; };
  var f1 = function (x) { return Math.round(x * 10) / 10; };
  var pt = function (p) { return f1(p[0]) + " " + f1(p[1]); };
  var lerp = function (a, b, t) { return a + (b - a) * t; };
  var clamp = function (x, a, b) { return Math.max(a, Math.min(b, x)); };
  var ease = function (t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
  var ARROW = FA ? "←" : "→";

  /* ------------------------------------------------------------ the guide as data */
  var chOf = function (n) { return CH[n - 1]; };
  CH.forEach(function (c) { c.secs = []; c.cons = []; });
  var secByKey = {};
  S.forEach(function (s, i) {
    s.i = i; s.key = "ch" + s.c + "/" + s.id;
    var c = chOf(s.c); s.ord = c.secs.length; c.secs.push(i);
    secByKey[s.key] = i;
  });
  Object.keys(CON).forEach(function (id) { var c = CON[id]; if (c.s < 0 && c.c && id !== "root") chOf(c.c).cons.push(id); });
  var out = S.map(function () { return []; }), inn = S.map(function () { return []; });
  var chw = {};
  D.links.forEach(function (l) {
    var a = l[0], b = l[1], ca = S[a].c, cb = b >= 0 ? S[b].c : -b;
    out[a].push(b);
    if (b >= 0) inn[b].push(a);
    if (ca !== cb) { var key = Math.min(ca, cb) + "|" + Math.max(ca, cb); chw[key] = (chw[key] || 0) + l[2]; }
  });
  var REFS = D.links.reduce(function (s, l) { return s + l[2]; }, 0);
  var chords = Object.keys(chw).map(function (k) { var p = k.split("|"); return { a: +p[0], b: +p[1], w: chw[k] }; });
  var partners = function (n) {
    return chords.filter(function (c) { return c.a === n || c.b === n; })
      .map(function (c) { return { n: c.a === n ? c.b : c.a, w: c.w }; }).sort(function (x, y) { return y.w - x.w; });
  };

  // how far the reader has got in each chapter (site.js keeps it by chapter file name)
  var prog = {};
  try { prog = JSON.parse(localStorage.getItem("epis-progress") || "{}") || {}; } catch (e) { prog = {}; }
  var latest = null;
  CH.forEach(function (c) {
    var p = prog[c.slug];
    c.pr = p && p.p > 0.01 ? Math.min(1, p.p) : 0;
    if (p && p.p > 0.01 && (!latest || (p.t || 0) > latest.t)) {
      latest = { n: c.n, t: p.t || 0, i: p.h ? secByKey["ch" + c.n + "/" + p.h] : undefined, h: p.h || "", done: p.at > 0.97 };
    }
  });

  var short = function (t, max) {
    if (t.length <= max) return t;
    var c = t.indexOf(":");
    if (c > 8 && c <= max) return t.slice(0, c);
    return t.slice(0, max - 1).replace(/[\s,;:–—-]+\S*$/, "") + "…";
  };
  S.forEach(function (s) { s.lab = short(s.t, FA ? 30 : 34); });

  /* ------------------------------------------------------------ geometry (world units, centred on 0,0) */
  var R_ROOT = 42, R_Q = 56, R_HUB = 106, R_CH = 180, R_MED = 22, R_BAND = 250, R2 = 262, LBL = 8;
  var GAP_CH = 1.5, GAP_PART = 3.8, FS_MAX = 12, FS_CH = 12.5, CW = FA ? 0.52 : 0.56;
  var FOCUS_A = FA ? Math.PI : 0;
  var nS = S.length;
  var partOf = function (n) { return chOf(n).p; };
  var gapBefore = function (n) { var m = n === 1 ? 16 : n - 1; return partOf(m) !== partOf(n) ? GAP_PART : GAP_CH; };
  var st = { k: [], mk: [], rot: 0, intro: 1 };
  for (var z = 0; z <= 16; z++) { st.k.push(1); st.mk.push(1); }
  var ang = [], cA = [], cA0 = [], cA1 = [], mA = [], pA = [], unit = 0;
  function layout() {
    var pos = 0, u = [], starts = [], ends = [], n;
    for (n = 1; n <= 16; n++) {
      pos += gapBefore(n) / 2;
      starts[n] = pos;
      for (var j = 0; j < chOf(n).secs.length; j++) { u[chOf(n).secs[j]] = pos + st.k[n] / 2; pos += st.k[n]; }
      ends[n] = pos;
      pos += gapBefore(n === 16 ? 1 : n + 1) / 2;
    }
    unit = TAU / pos;
    var a0 = -Math.PI / 2 + st.rot;
    for (var i = 0; i < nS; i++) ang[i] = a0 + u[i] * unit;
    for (n = 1; n <= 16; n++) { cA0[n] = a0 + starts[n] * unit; cA1[n] = a0 + ends[n] * unit; cA[n] = (cA0[n] + cA1[n]) / 2; mA[n] = cA[n]; }
    // medallions sit at the middle of their chapter, pushed apart until none crowds its neighbour
    for (var it = 0; it < 60; it++) {
      for (n = 1; n <= 16; n++) {
        var m = n === 16 ? 1 : n + 1, need = (R_MED * (st.mk[n] + st.mk[m]) + 7) / R_CH;
        var d = (((mA[m] - mA[n]) % TAU) + TAU) % TAU;
        if (d < need) { var push = (need - d) / 2; mA[n] -= push; mA[m] += push; }
      }
    }
    PARTS.forEach(function (p, j) { pA[j] = (cA0[p.ch[0]] + cA1[p.ch[p.ch.length - 1]]) / 2; });
  }

  /* ------------------------------------------------------------ drawing, once */
  var h = [];
  h.push("<defs>");
  h.push('<clipPath id="mclip" clipPathUnits="userSpaceOnUse"><circle r="' + R_MED + '"/></clipPath>');
  h.push('<clipPath id="rclip" clipPathUnits="userSpaceOnUse"><circle r="' + R_ROOT + '"/></clipPath>');
  h.push('<path id="qpath"/>');
  chords.forEach(function (c, j) {
    h.push('<linearGradient id="cg' + j + '" gradientUnits="userSpaceOnUse"><stop offset="0" style="stop-color:var(--p' + partOf(c.a) +
           ')"/><stop offset="1" style="stop-color:var(--p' + partOf(c.b) + ')"/></linearGradient>');
  });
  h.push("</defs>");
  h.push('<g class="w-world">');
  var deco = '<g class="w-deco" aria-hidden="true">';
  for (var r = 0; r < 120; r++) {
    var ra = r * TAU / 120;
    deco += '<path d="M' + pt(P(R_Q + 12, ra)) + "L" + pt(P(r % 5 ? R_HUB - 16 : R_CH - R_MED - 16, ra)) + '"/>';
  }
  [R_HUB, R_CH, R2].forEach(function (rr, k) { deco += '<circle class="orb' + (k ? " main" : "") + '" r="' + rr + '"/>'; });
  h.push(deco + "</g>");
  h.push('<g class="w-chords">' + chords.map(function (c, j) {
    return '<path class="chord" data-j="' + j + '" stroke="url(#cg' + j + ')" stroke-width="' + f1(0.7 + 1.25 * Math.sqrt(c.w)) + '"/>';
  }).join("") + "</g>");
  h.push('<g class="w-route"><path class="route"/></g>');
  h.push('<g class="w-fans">' + S.map(function (s) { return '<path class="fan p' + partOf(s.c) + '"/>'; }).join("") + "</g>");
  h.push('<g class="w-band">' + CH.map(function (c) { return '<path class="arc p' + c.p + '" data-sel="ch' + c.n + '"/>'; }).join("") + "</g>");
  h.push('<g class="w-hubs">' + PARTS.map(function (p, j) {
    return '<g class="hub p' + j + '" data-sel="part-' + (j + 1) + '"><circle r="12"/><text dy=".35em">' + esc(FA ? digits(j + 1) : p.r) + "</text><title>" +
           esc(p.l + " · " + p.t) + "</title></g>";
  }).join("") + "</g>");
  h.push('<g class="w-secs">' + S.map(function (s) {
    var con = s.k.length > 0;
    return '<g class="sn p' + partOf(s.c) + (con ? " con" : "") + '" data-sel="' + esc(s.key) + '" tabindex="-1" role="button" aria-label="' +
           esc(s.t + " · " + chOf(s.c).l) + '"><rect class="hit" y="-7" height="14" rx="7"/><circle r="' + (con ? 3.6 : 2.3) + '"/>' +
           '<text dy=".34em"' + (FA ? ' direction="rtl"' : "") + ">" + esc(s.lab) + "</text>" + (s.lab !== s.t ? "<title>" + esc(s.t) + "</title>" : "") + "</g>";
  }).join("") + "</g>");
  h.push('<g class="w-titles" aria-hidden="true">' + CH.map(function (c) {
    return '<g class="ct p' + c.p + '"><text dy=".34em"' + (FA ? ' direction="rtl"' : "") + '><tspan class="ctn">' + digits(c.n) + "</tspan> " + esc(c.sh) + "</text></g>";
  }).join("") + "</g>");
  h.push('<g class="w-meds">' + CH.map(function (c) {
    var circ = TAU * (R_MED + 4.5);
    return '<g class="med p' + c.p + '" data-sel="ch' + c.n + '" tabindex="0" role="button" aria-label="' + esc(c.l + ": " + c.t) + '">' +
           '<circle class="halo" r="' + (R_MED + 7) + '"/>' +
           '<image href="' + esc(c.img) + '" x="' + -R_MED + '" y="' + -R_MED + '" width="' + 2 * R_MED + '" height="' + 2 * R_MED +
           '" clip-path="url(#mclip)" preserveAspectRatio="xMidYMid slice"/>' +
           '<circle class="ring" r="' + R_MED + '"/>' +
           (c.pr ? '<circle class="prog" r="' + (R_MED + 4.5) + '" transform="rotate(-90)" stroke-dasharray="' + f1(circ * c.pr) + " " + f1(circ) + '"/>' : "") +
           '<g class="badge"><circle r="8.5"/><text dy=".35em">' + digits(c.n) + "</text></g>" +
           '<g class="step"><circle r="9.5"/><text dy=".35em"></text></g><title>' + esc(c.l + ": " + c.t) + "</title></g>";
  }).join("") + "</g>");
  var rt = D.root.t;
  h.push('<g class="rootn" data-sel="root" tabindex="0" role="button" aria-label="' + esc(rt) + '">' +
         '<circle class="halo" r="' + (R_Q + 9) + '"/>' +
         '<image href="' + esc(D.root.img) + '" x="' + -R_ROOT + '" y="' + -R_ROOT + '" width="' + 2 * R_ROOT + '" height="' + 2 * R_ROOT +
         '" clip-path="url(#rclip)" preserveAspectRatio="xMidYMid slice"/>' +
         '<circle class="ring" r="' + R_ROOT + '"/>' +
         (D.q ? '<text class="qtext"' + (FA ? ' direction="rtl"' : "") + '><textPath href="#qpath" startOffset="50%">' + esc(D.q) + "</textPath></text>" : "") +
         '<rect class="cart" x="' + -(rt.length * (FA ? 5.2 : 4.7) + 11) + '" y="17" width="' + 2 * (rt.length * (FA ? 5.2 : 4.7) + 11) + '" height="22" rx="11"/>' +
         '<text class="rt" y="32"' + (FA ? ' direction="rtl"' : "") + ">" + esc(rt) + "</text></g>");
  h.push("</g>");
  svg.innerHTML = h.join("");
  var world = svg.querySelector(".w-world");
  (function fitQuestion() {
    var t = svg.querySelector(".qtext"), path = svg.querySelector("#qpath");
    if (!t) return;
    if (FA) {
      // Persian letters join, and a browser that sets text along a curve breaks the joins: so each word is set upright
      // by itself and placed on the arc, the first word at the right
      var NS = "http://www.w3.org/2000/svg", words = D.q.split(/\s+/), el = [], widths = [], total = 0, GAP = 3.5;
      var fsz = 9.5;
      words.forEach(function (w) {
        var x = document.createElementNS(NS, "text");
        x.setAttribute("class", "qtext qw"); x.setAttribute("direction", "rtl"); x.textContent = w;
        t.parentNode.insertBefore(x, t); el.push(x);
        var len = 0; try { len = x.getComputedTextLength(); } catch (e) { len = w.length * 5; }
        widths.push(len); total += len;
      });
      total += GAP * (words.length - 1);
      var MAXS = 3.55, k = Math.min(1, R_Q * MAXS * 0.95 / total);
      total *= k;
      var off = -total / 2;
      el.forEach(function (x, i) {
        var wl = widths[i] * k, mid = off + wl / 2, a = -Math.PI / 2 + (-mid / R_Q), pp = P(R_Q, a);
        x.style.fontSize = (fsz * k).toFixed(2) + "px";
        x.setAttribute("transform", "translate(" + pt(pp).replace(" ", ",") + ") rotate(" + f1((a + Math.PI / 2) * 180 / Math.PI) + ")");
        x.setAttribute("text-anchor", "middle");
        off += wl + GAP * k;
      });
      t.parentNode.removeChild(t);
      return;
    }
    var arc = function (span) {
      var a0 = -Math.PI / 2 - span / 2, a1 = -Math.PI / 2 + span / 2;
      path.setAttribute("d", "M" + pt(P(R_Q, a0)) + "A" + R_Q + " " + R_Q + " 0 " + (span > Math.PI ? 1 : 0) + " 1 " + pt(P(R_Q, a1)));
    };
    var MAXSPAN = 3.55;  // the ends stay above the cartouche
    arc(MAXSPAN);
    var len = 0;
    try { len = t.getComputedTextLength(); } catch (e) { len = 0; }
    if (!len) return;
    if (len > R_Q * MAXSPAN * 0.97) {
      var fs = parseFloat(getComputedStyle(t).fontSize) || 11;
      t.style.fontSize = (fs * R_Q * MAXSPAN * 0.97 / len).toFixed(2) + "px";
      len = R_Q * MAXSPAN * 0.97;
    }
    arc(Math.min(MAXSPAN, len / R_Q + 0.16));
  })();
  var $ = function (sel) { return Array.prototype.slice.call(svg.querySelectorAll(sel)); };
  var E = { chord: $(".chord"), grad: $("linearGradient"), fan: $(".fan"), arc: $(".arc"), hub: $(".hub"), sn: $(".sn"),
            ct: $(".ct"), med: $(".med"), route: svg.querySelector(".route"), root: svg.querySelector(".rootn"),
            gChords: svg.querySelector(".w-chords"), gFans: svg.querySelector(".w-fans"), gBand: svg.querySelector(".w-band"),
            gSecs: svg.querySelector(".w-secs"), gTitles: svg.querySelector(".w-titles"), gHubs: svg.querySelector(".w-hubs") };
  E.snText = E.sn.map(function (g) { return g.querySelector("text"); });
  E.snDot = E.sn.map(function (g) { return g.querySelector("circle"); });
  E.snHit = E.sn.map(function (g) { return g.querySelector(".hit"); });
  E.ctText = E.ct.map(function (g) { return g.querySelector("text"); });
  E.badge = E.med.map(function (g) { return g.querySelector(".badge"); });
  E.step = E.med.map(function (g) { return g.querySelector(".step"); });

  /* ------------------------------------------------------------ drawing, every frame */
  var medAt = [], roomFor = {};
  function slotFs(n) { return Math.min(FS_MAX, st.k[n] * unit * R2 * 0.86); }
  function renderLayout() {
    var n, i;
    for (n = 1; n <= 16; n++) medAt[n] = P(R_CH, mA[n]);
    var intro = st.intro, introing = intro < 1;
    // medallions
    for (n = 1; n <= 16; n++) {
      var g = E.med[n - 1], m = medAt[n];
      var pop = introing ? ease(clamp(intro * 1.8 - (n - 1) / 16 * 0.8, 0, 1)) : 1;
      g.setAttribute("transform", "translate(" + f1(m[0]) + "," + f1(m[1]) + ") scale(" + (st.mk[n] * pop).toFixed(3) + ")");
      var b = P(R_MED + 1, mA[n] + Math.PI);
      E.badge[n - 1].setAttribute("transform", "translate(" + f1(b[0]) + "," + f1(b[1]) + ")");
      var sp = P(R_MED + 2, mA[n]);
      E.step[n - 1].setAttribute("transform", "translate(" + f1(sp[0]) + "," + f1(sp[1]) + ")");
    }
    // band arcs
    for (n = 1; n <= 16; n++) {
      var p0 = P(R_BAND, cA0[n] - 0.004), p1 = P(R_BAND, cA1[n] + 0.004), large = cA1[n] - cA0[n] > Math.PI ? 1 : 0;
      E.arc[n - 1].setAttribute("d", "M" + pt(p0) + "A" + R_BAND + " " + R_BAND + " 0 " + large + " 1 " + pt(p1));
    }
    // sections and the fans that tie them to their chapter
    for (i = 0; i < nS; i++) {
      var s = S[i], a = ang[i], right = Math.cos(a) >= -1e-9, deg = a * 180 / Math.PI;
      E.sn[i].setAttribute("transform", "rotate(" + f1(right ? deg : deg + 180) + ")");
      if (s._r !== right) {
        s._r = right; s._fs = -1;
        E.snDot[i].setAttribute("cx", right ? R2 : -R2);
        E.snText[i].setAttribute("x", right ? R2 + LBL : -(R2 + LBL));
        E.snText[i].setAttribute("text-anchor", right !== FA ? "start" : "end");
      }
      var mm = medAt[s.c], dx = Math.cos(a), dy = Math.sin(a), q = P(R2 - 4, a);
      var tx0 = q[0] - mm[0], ty0 = q[1] - mm[1], tl = Math.hypot(tx0, ty0) || 1, rr = R_MED * st.mk[s.c] + 1;
      var s0 = [mm[0] + tx0 / tl * rr, mm[1] + ty0 / tl * rr], c1 = P(R_CH + 36, mA[s.c]), c2 = [(R_BAND - 28) * dx, (R_BAND - 28) * dy];
      E.fan[i].setAttribute("d", "M" + pt(s0) + "C" + pt(c1) + " " + pt(c2) + " " + pt(q));
      if (introing) E.sn[i].style.opacity = clamp(intro * 2.4 - i / nS * 1.3, 0, 1);
    }
    // chapter titles, where a chapter's sections are too small to read
    for (n = 1; n <= 16; n++) {
      var ca = cA[n], cr = Math.cos(ca) >= -1e-9, cd = ca * 180 / Math.PI;
      E.ct[n - 1].setAttribute("transform", "rotate(" + f1(cr ? cd : cd + 180) + ")");
      var c = chOf(n);
      if (c._r !== cr) {
        c._r = cr;
        E.ctText[n - 1].setAttribute("x", cr ? R2 + LBL + 2 : -(R2 + LBL + 2));
        E.ctText[n - 1].setAttribute("text-anchor", cr !== FA ? "start" : "end");
      }
    }
    // the cross-references between chapters, gathered through the hub of each part
    PARTS.forEach(function (p, j) { var hp = P(R_HUB, pA[j]); E.hub[j].setAttribute("transform", "translate(" + f1(hp[0]) + "," + f1(hp[1]) + ")"); });
    chords.forEach(function (c, j) {
      var A = medAt[c.a], B = medAt[c.b], pa = partOf(c.a), pb = partOf(c.b), beta = pa === pb ? 0.55 : 0.84;
      var ha = P(R_HUB, pA[pa]), hb = P(R_HUB, pA[pb]);
      var k1 = [lerp(A[0], ha[0], beta), lerp(A[1], ha[1], beta)], k2 = [lerp(B[0], hb[0], beta), lerp(B[1], hb[1], beta)];
      E.chord[j].setAttribute("d", "M" + pt(A) + "C" + pt(k1) + " " + pt(k2) + " " + pt(B));
      var gr = E.grad[j];
      gr.setAttribute("x1", f1(A[0])); gr.setAttribute("y1", f1(A[1])); gr.setAttribute("x2", f1(B[0])); gr.setAttribute("y2", f1(B[1]));
    });
    if (pathIdx >= 0) drawRoute();
    if (introing) {
      var o = clamp(intro * 2 - 0.9, 0, 1);
      E.gChords.style.opacity = o; E.gHubs.style.opacity = o;
      E.gFans.style.opacity = E.gBand.style.opacity = clamp(intro * 1.7 - 0.35, 0, 1);
      E.gTitles.style.opacity = clamp(intro * 2 - 1, 0, 1);
      E.root.setAttribute("transform", "scale(" + ease(clamp(intro * 2.5, 0, 1)).toFixed(3) + ")");
    }
  }
  function endIntro() {
    st.intro = 1;
    E.sn.forEach(function (g) { g.style.opacity = ""; });
    [E.gChords, E.gHubs, E.gFans, E.gBand, E.gTitles].forEach(function (g) { g.style.opacity = ""; });
    E.root.removeAttribute("transform");
  }
  // label sizes follow the room a section has on the wheel and the zoom; too small to read means hidden
  function renderLabels() {
    var shown = [], popped = [];
    for (var n = 1; n <= 16; n++) shown[n] = slotFs(n) * sc >= 7 && !roomFor[n];
    S.forEach(function (x) { if (x._pop) popped[x.c] = 1; });
    for (var i = 0; i < nS; i++) {
      var s = S[i], fs = slotFs(s.c), vis = shown[s.c] || s._pop;
      if (s._pop && !shown[s.c]) fs = Math.max(fs, Math.min(FS_MAX, 10.5 / sc));
      if (vis !== s._vis) { s._vis = vis; s._fs = -1; E.sn[i].classList.toggle("lv", vis); }
      if (!vis && s._fs === -1) {
        s._fs = 0;
        E.snHit[i].setAttribute("x", s._r ? R2 - 7 : -(R2 + 7)); E.snHit[i].setAttribute("width", 14);
        E.snHit[i].setAttribute("y", -7); E.snHit[i].setAttribute("height", 14);
      } else if (vis && Math.abs(fs - s._fs) > 0.15) {
        s._fs = fs;
        E.snText[i].style.fontSize = fs.toFixed(2) + "px";
        var w = s.lab.length * fs * CW + LBL + 10, hh = Math.max(fs + 3, 9);
        E.snHit[i].setAttribute("x", f1(s._r ? R2 - 6 : -(R2 + w))); E.snHit[i].setAttribute("width", f1(w + 6));
        E.snHit[i].setAttribute("y", f1(-hh / 2)); E.snHit[i].setAttribute("height", f1(hh));
      }
    }
    for (n = 1; n <= 16; n++) {
      var showT = !shown[n] && !popped[n] && FS_CH * sc >= 6.5;
      if (showT !== chOf(n)._tv) { chOf(n)._tv = showT; E.ct[n - 1].classList.toggle("lv", showT); }
    }
  }
  function render() { layout(); renderLayout(); renderLabels(); }

  /* ------------------------------------------------------------ the camera: pan and zoom */
  var tx = 0, ty = 0, sc = 1, W = 0, H = 0;
  var narrow = function () { return W < 640; };
  function size() {
    var b = svg.getBoundingClientRect();
    W = b.width; H = b.height;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }
  function sheetH() { return !narrow() ? 0 : panel.classList.contains("open") ? panel.getBoundingClientRect().height : 86; }
  function apply() {
    world.setAttribute("transform", "translate(" + f1(tx) + "," + f1(ty) + ") scale(" + sc.toFixed(4) + ")");
  }
  var MINS = 0.2, MAXS = 3;
  function fitCam(box, maxScale) {
    var pad = narrow() ? 10 : 18, top = narrow() ? 64 : 12, avH = H - sheetH() - top - (narrow() ? 6 : 12);
    var s = Math.min((W - 2 * pad) / (box[2] - box[0]), (avH - pad) / (box[3] - box[1]), maxScale || 1.4);
    s = clamp(s, MINS, MAXS);
    return { tx: W / 2 - (box[0] + box[2]) / 2 * s, ty: top + avH / 2 - (box[1] + box[3]) / 2 * s, sc: s };
  }
  // the extent of the drawing for the current layout, labels included, as they would be at scale s
  function extent(s, onlyCh) {
    var b = [1e9, 1e9, -1e9, -1e9];
    var add = function (p) { b[0] = Math.min(b[0], p[0]); b[1] = Math.min(b[1], p[1]); b[2] = Math.max(b[2], p[0]); b[3] = Math.max(b[3], p[1]); };
    var shown = [], popped = [];
    for (var n = 1; n <= 16; n++) shown[n] = slotFs(n) * s >= 7 && !roomFor[n];
    S.forEach(function (x) { if (x._pop) popped[x.c] = 1; });
    if (!onlyCh) { add([-R2 - 8, -R2 - 8]); add([R2 + 8, R2 + 8]); }
    else { add(P(R_CH, mA[onlyCh])); var mr = R_MED * st.mk[onlyCh] + 10; add([medAt[onlyCh][0] - mr, medAt[onlyCh][1] - mr]); add([medAt[onlyCh][0] + mr, medAt[onlyCh][1] + mr]); }
    for (var i = 0; i < nS; i++) {
      var sc_ = S[i];
      if (onlyCh && sc_.c !== onlyCh) continue;
      add(P(R2 + 4, ang[i]));
      if (shown[sc_.c] || sc_._pop) add(P(R2 + LBL + sc_.lab.length * Math.max(slotFs(sc_.c), sc_._pop ? 10.5 / s : 0) * CW + 4, ang[i]));
    }
    if (!onlyCh) for (n = 1; n <= 16; n++) if (!shown[n] && !popped[n] && FS_CH * s >= 6.5) add(P(R2 + LBL + 4 + (chOf(n).sh.length + 3) * FS_CH * CW, cA[n]));
    return b;
  }
  function camFor(s) {
    if (narrow()) {
      var f = focusChapter(s), fi = focusSection(s), b = [1e9, 1e9, -1e9, -1e9];
      var add = function (p) { b[0] = Math.min(b[0], p[0]); b[1] = Math.min(b[1], p[1]); b[2] = Math.max(b[2], p[0]); b[3] = Math.max(b[3], p[1]); };
      if (fi >= 0 && s.kind !== "path") {
        var a = ang[fi], len = S[fi].lab.length * Math.max(slotFs(f), 10) * CW, mid = P(R2, a);
        add(P(R2 - 46, a)); add(P(R2 + LBL + len + 6, a)); add([mid[0], mid[1] - 80]); add([mid[0], mid[1] + 80]);
        return fitCam(b, 1.3);
      }
      if (f && s.kind !== "path") {
        var mr = R_MED * st.mk[f] + 8;
        add([medAt[f][0] - mr, medAt[f][1] - mr]); add([medAt[f][0] + mr, medAt[f][1] + mr]);
        chOf(f).secs.forEach(function (i) { add(P(R2 + 4, ang[i])); add(P(R2 + 120, ang[i])); });
        return fitCam(b, 1.2);
      }
      var R = R2 + 8;
      return fitCam([-R, -R, R, R], 1.2);
    }
    // a wide window shows the whole wheel; the chosen chapter is widened, not zoomed into
    var guess = 0.8;
    for (var k = 0; k < 2; k++) guess = fitCam(extent(guess), 1.15).sc;
    return fitCam(extent(guess), 1.15);
  }
  function zoomAt(f, cx, cy) {
    var ns = clamp(sc * f, MINS, MAXS);
    if (cx === undefined) { cx = W / 2; cy = H / 2; }
    animate(null, { tx: cx - (cx - tx) * ns / sc, ty: cy - (cy - ty) * ns / sc, sc: ns }, 300);
  }

  /* ------------------------------------------------------------ animation: the wheel turns, the camera follows */
  var raf = 0, target = null, camTarget = null;
  function animate(lay, cam, dur) {
    cancelAnimationFrame(raf);
    if (st.intro < 1 && !(lay && lay.intro !== undefined)) endIntro();
    var from = { k: st.k.slice(), mk: st.mk.slice(), rot: st.rot, intro: st.intro, tx: tx, ty: ty, sc: sc };
    target = lay; camTarget = cam;
    var t0 = performance.now();
    if (reduce || !dur) dur = 1;
    (function frame(now) {
      var t = Math.min(1, (now - t0) / dur), e = ease(t);
      if (lay) {
        for (var n = 1; n <= 16; n++) { st.k[n] = lerp(from.k[n], lay.k[n], e); st.mk[n] = lerp(from.mk[n], lay.mk[n], e); }
        st.rot = lerp(from.rot, lay.rot, e);
        if (lay.intro !== undefined) st.intro = lerp(from.intro, lay.intro, t);
      }
      if (cam) { tx = lerp(from.tx, cam.tx, e); ty = lerp(from.ty, cam.ty, e); sc = lerp(from.sc, cam.sc, e); }
      if (lay) render(); else renderLabels();
      apply();
      if (t < 1) raf = requestAnimationFrame(frame);
      else { target = camTarget = null; if (st.intro >= 1 && lay && lay.intro !== undefined) endIntro(); }
    })(t0);
  }
  function settle() {  // jump to the end of a running turn (when the reader takes the camera)
    if (!target && !camTarget) return;
    cancelAnimationFrame(raf);
    if (target) {
      st.k = target.k.slice(); st.mk = target.mk.slice(); st.rot = target.rot;
      if (target.intro !== undefined) endIntro();
    }
    if (camTarget) { tx = camTarget.tx; ty = camTarget.ty; sc = camTarget.sc; }
    target = camTarget = null; render(); apply();
  }

  /* ------------------------------------------------------------ what is chosen */
  var sel = { kind: "root" }, selId = "root", hover = null, pathIdx = -1;
  function parse(id) {
    var m;
    if (!id || id === "root") return { kind: "root" };
    if ((m = /^part-(\d)$/.exec(id)) && PARTS[+m[1] - 1]) return { kind: "part", j: +m[1] - 1 };
    if ((m = /^ch(\d+)$/.exec(id)) && +m[1] >= 1 && +m[1] <= 16) return { kind: "ch", n: +m[1] };
    if (secByKey[id] !== undefined) return { kind: "sec", i: secByKey[id] };
    if ((m = /^path-(\d+)$/.exec(id)) && PATHS[+m[1]]) return { kind: "path", j: +m[1] };
    if (CON[id]) return id === "root" ? { kind: "root" } : { kind: "con", id: id };
    return null;
  }
  function focusChapter(s) {
    if (s.kind === "ch") return s.n;
    if (s.kind === "sec") return S[s.i].c;
    if (s.kind === "con") { var c = CON[s.id]; return c.s >= 0 ? S[c.s].c : c.c; }
    return 0;
  }
  function focusSection(s) {
    if (s.kind === "sec") return s.i;
    if (s.kind === "con" && CON[s.id].s >= 0) return CON[s.id].s;
    return -1;
  }
  function layoutFor(s) {
    var lay = { k: [], mk: [], rot: 0, lw: {} }, n;
    for (n = 0; n <= 16; n++) { lay.k.push(1); lay.mk.push(1); }
    var f = focusChapter(s), fi = focusSection(s), group = f ? [f] : s.kind === "part" ? PARTS[s.j].ch : [];
    if (fi >= 0) {
      var many = {};
      Object.keys(linked(fi).secs).forEach(function (j) { var c = S[j].c; if (c !== f) many[c] = (many[c] || 0) + 1; });
      Object.keys(many).forEach(function (c) { lay.k[c] = Math.min(3, 1.7 + 0.6 * many[c]); lay.lw[c] = 1; });
    }
    if (group.length) {
      var uf = 0, total = 0;
      group.forEach(function (g) { uf += chOf(g).secs.length; });
      for (n = 1; n <= 16; n++) total += (group.indexOf(n) >= 0 ? 1 : lay.k[n]) * chOf(n).secs.length + gapBefore(n);
      var share = f ? (narrow() ? 0.22 : 0.3) : 0.45, maxSlot = f ? 27 : 16;
      var span = Math.min(share * TAU, uf * maxSlot / R2), uo = total - uf;
      var k = Math.max(1, span * uo / (uf * (TAU - span)));
      group.forEach(function (g) { lay.k[g] = k; });
      for (n = 1; n <= 16; n++) lay.mk[n] = group.indexOf(n) >= 0 ? (f ? 1.32 : 1.1) : (f ? 0.8 : 0.9);
      // turn the wheel so that the chapter (or part) faces the reader
      var keep = { k: st.k, mk: st.mk, rot: st.rot };
      st.k = lay.k; st.mk = lay.mk; st.rot = 0; layout();
      var centre = f ? cA[f] : (cA0[group[0]] + cA1[group[group.length - 1]]) / 2;
      st.k = keep.k; st.mk = keep.mk; st.rot = keep.rot;
      var rot = FOCUS_A - centre;
      while (rot - st.rot > Math.PI) rot -= TAU;
      while (rot - st.rot < -Math.PI) rot += TAU;
      lay.rot = rot;
    } else {
      var r0 = 0;
      while (r0 - st.rot > Math.PI) r0 -= TAU;
      while (r0 - st.rot < -Math.PI) r0 += TAU;
      lay.rot = r0;
    }
    return lay;
  }
  function camAfter(lay, s) {  // the camera for a layout, worked out on the layout as it will be
    var keep = { k: st.k, mk: st.mk, rot: st.rot };
    st.k = lay.k; st.mk = lay.mk; st.rot = lay.rot; layout();
    for (var n = 1; n <= 16; n++) medAt[n] = P(R_CH, mA[n]);
    var cam = camFor(s);
    st.k = keep.k; st.mk = keep.mk; st.rot = keep.rot; layout();
    for (n = 1; n <= 16; n++) medAt[n] = P(R_CH, mA[n]);
    return cam;
  }
  function select(id, opts) {
    opts = opts || {};
    var s = parse(id);
    if (!s) return;
    if (s.kind === "path") pathIdx = s.j;
    else if (s.kind === "root" && !opts.keepPath) pathIdx = -1;
    sel = s; selId = id; hover = null;
    E.route.classList.toggle("on", pathIdx >= 0);
    if (pathIdx >= 0) drawRoute(true);
    markPops();
    paint();
    renderPanel();
    if (opts.hash !== false) {
      try { history.replaceState(null, "", id === "root" ? location.pathname + location.search : "#" + id); } catch (_) { /* file: URLs */ }
    }
    if (opts.move === false) { renderLabels(); return; }
    var lay = layoutFor(s);
    roomFor = lay.lw;
    animate(lay, camAfter(lay, s), opts.dur === undefined ? 760 : opts.dur);
  }

  // which sections stay labelled whatever their size: the chosen one and the ones it is linked with
  var linked = function (i) {
    var o = { secs: {}, chs: {} };
    out[i].concat(inn[i]).forEach(function (j) { if (j >= 0) { o.secs[j] = 1; o.chs[S[j].c] = 1; } else o.chs[-j] = 1; });
    return o;
  };
  function markPops() {
    S.forEach(function (s) { s._pop = false; });
    var v = hover || sel, fi = focusSection(v);
    if (fi >= 0) {
      S[fi]._pop = true;
      var L = linked(fi);
      Object.keys(L.secs).forEach(function (j) { S[j]._pop = true; });
    }
  }
  function paint() {
    var v = hover || sel, f = focusChapter(v), fi = focusSection(v), hiCh = {}, lnkCh = {}, lnkSec = {}, chordOn = {}, fanOn = {};
    if (f) hiCh[f] = 1;
    if (v.kind === "part") PARTS[v.j].ch.forEach(function (n) { hiCh[n] = 1; });
    if (fi >= 0) {
      var L = linked(fi);
      lnkSec = L.secs; lnkCh = L.chs; fanOn[fi] = 1;
      Object.keys(L.secs).forEach(function (j) { fanOn[j] = 1; });
      chords.forEach(function (c, j) { if ((c.a === f && L.chs[c.b]) || (c.b === f && L.chs[c.a])) chordOn[j] = 1; });
    } else {
      chords.forEach(function (c, j) {
        if (hiCh[c.a] || hiCh[c.b]) { chordOn[j] = 1; if (f) lnkCh[c.a === f ? c.b : c.a] = 1; }
      });
    }
    var onPath = {}, steps = {};
    if (pathIdx >= 0) PATHS[pathIdx].st.forEach(function (x, k) { onPath[x[0]] = 1; if (!steps[x[0]]) steps[x[0]] = k + 1; });
    var focused = v.kind !== "root" && v.kind !== "path";
    svg.classList.toggle("focused", focused);
    svg.classList.toggle("pathing", pathIdx >= 0);
    var selCh = sel.kind === "ch" ? sel.n : 0;
    E.med.forEach(function (g, k) {
      var n = k + 1;
      g.classList.toggle("in", !!hiCh[n]);
      g.classList.toggle("sel", n === selCh);
      g.classList.toggle("lnk", !!lnkCh[n] && !hiCh[n]);
      g.classList.toggle("off", pathIdx >= 0 && !onPath[n]);
      E.step[k].querySelector("text").textContent = steps[n] ? digits(steps[n]) : "";
      g.classList.toggle("stepped", !!steps[n]);
    });
    var focusCh = focusChapter(sel);
    E.sn.forEach(function (g, i) {
      var s = S[i];
      g.classList.toggle("in", !!hiCh[s.c]);
      g.classList.toggle("sel", i === fi);
      g.classList.toggle("lnk", !!lnkSec[i]);
      g.classList.toggle("here", !!latest && latest.i === i);
      g.setAttribute("tabindex", s.c === focusCh ? "0" : "-1");
    });
    E.fan.forEach(function (p, i) { p.classList.toggle("in", !!hiCh[S[i].c]); p.classList.toggle("on", !!fanOn[i]); });
    E.arc.forEach(function (p, k) { p.classList.toggle("in", !!hiCh[k + 1]); });
    E.chord.forEach(function (p, j) { p.classList.toggle("on", !!chordOn[j]); });
    E.hub.forEach(function (g, j) { g.classList.toggle("in", v.kind === "part" && v.j === j); });
    E.root.classList.toggle("sel", sel.kind === "root");
  }
  function drawRoute(fresh) {
    var st_ = PATHS[pathIdx].st, d = "";
    for (var k = 0; k < st_.length; k++) {
      var m = P(R_CH, mA[st_[k][0]]);
      if (!k) { d = "M" + pt(m); continue; }
      var a = P(R_CH, mA[st_[k - 1][0]]), gap = Math.abs((((mA[st_[k][0]] - mA[st_[k - 1][0]]) % TAU) + TAU) % TAU);
      var pull = gap < 0.5 || gap > TAU - 0.5 ? 0.86 : 0.58;
      d += "C" + pt([a[0] * pull, a[1] * pull]) + " " + pt([m[0] * pull, m[1] * pull]) + " " + pt(m);
    }
    E.route.setAttribute("d", d);
    if (fresh && !reduce) {
      var len = E.route.getTotalLength();
      E.route.style.transition = "none";
      E.route.style.strokeDasharray = len + " " + len;
      E.route.style.strokeDashoffset = len;
      E.route.getBoundingClientRect();
      E.route.style.transition = "stroke-dashoffset 1.6s cubic-bezier(.4,0,.2,1) .35s";
      E.route.style.strokeDashoffset = "0";
      clearTimeout(drawRoute.t);
      drawRoute.t = setTimeout(function () { E.route.style.strokeDasharray = ""; E.route.style.transition = ""; }, 2100);
    }
  }

  /* ------------------------------------------------------------ the panel */
  var dot = function (p) { return '<i class="pdot p' + p + '" aria-hidden="true"></i>'; };
  var btn = function (id, inner, cls) { return '<button type="button" data-sel="' + esc(id) + '"' + (cls ? ' class="' + cls + '"' : "") + ">" + inner + "</button>"; };
  var sec3 = function (title, inner) { return '<section class="p-sec"><h3>' + title + "</h3>" + inner + "</section>"; };
  var head = function (crumbs, kicker, title, p) {
    return '<div class="p-head">' + (crumbs.length ? '<nav class="p-crumbs" aria-label="' + esc(U.back) + '">' +
           crumbs.map(function (c) { return btn(c[0], esc(c[1])); }).join('<span aria-hidden="true">' + (FA ? "‹" : "›") + "</span>") + "</nav>" : "") +
           '<div class="kicker">' + (p === undefined ? "" : dot(p)) + esc(kicker) + "</div><h2>" + esc(title) + "</h2>" +
           '<button type="button" class="p-toggle" aria-expanded="true" aria-label="' + esc(U.close) + '"></button></div>';
  };
  var chBtn = function (n, extra) {
    var c = chOf(n);
    return "<li>" + btn("ch" + n, '<img src="' + esc(c.img) + '" alt="" loading="lazy"><span><small>' + esc(c.l) + "</small><b>" + esc(c.t) + "</b>" +
           (extra ? "<em>" + extra + "</em>" : "") + "</span>", "chb p" + c.p) + "</li>";
  };
  var secBtn = function (i, pre) {
    var s = S[i];
    return "<li>" + btn(s.key, dot(chOf(s.c).p) + "<span>" + (pre ? "<small>" + esc(pre) + "</small>" : "") + "<b>" + esc(s.t) + "</b></span>" +
           (s.k.length ? '<i class="mk con" title="' + esc(U.entries) + '"></i>' : "") + (s.d ? '<i class="mk dp" title="' + esc(U.deeper) + '"></i>' : "")) + "</li>";
  };
  var conBtn = function (id) {
    var c = CON[id];
    return "<li>" + btn(id, '<span><b>' + esc(c.t) + "</b>" + (c.l ? "<small class=\"ln\">" + esc(c.l) + "</small>" : "") + "</span>", "conb") + "</li>";
  };
  var shortCh = function (n) { return FA ? chOf(n).l : "Ch. " + n; };
  function progressBox(c) {
    if (!c.pr) return "";
    var pc = Math.round(c.pr * 100), here = latest && latest.n === c.n && latest.i !== undefined ? S[latest.i] : null;
    return '<div class="p-prog"><div class="bar"><i style="width:' + pc + '%"></i></div><p>' + esc(fmt(U.read_p, { n: pc })) +
           (here ? " · " + esc(U.stopped) + " " + btn(here.key, "§ " + esc(here.t), "lnkbtn") : "") + "</p></div>";
  }
  function renderPanel() {
    var s = sel, html = "";
    if (s.kind === "root") {
      html = head([], U.kmap, D.root.t);
      html += '<div class="p-body">';
      if (D.q) html += '<p class="p-line">' + esc(D.q) + "</p>";
      html += '<p class="p-stats">' + esc(fmt(U.stats, { c: 16, s: nS, l: REFS, e: Object.keys(CON).length })) + "</p>";
      html += '<p class="p-how">' + esc(U.how) + "</p>";
      if (latest) {
        var lc = chOf(latest.n), ls = latest.i !== undefined ? S[latest.i] : null;
        html += '<a class="p-cont" href="' + esc(lc.h + (latest.h ? "#" + latest.h : "")) + '"><img src="' + esc(lc.img) + '" alt=""><span><small>' + esc(U.continue) +
                "</small><b>" + esc(lc.l + " · " + lc.t) + "</b>" + (ls ? "<em>§ " + esc(ls.t) + "</em>" : "") + "</span></a>";
      }
      html += sec3(esc(U.parts), PARTS.map(function (p, j) {
        return '<div class="p-part">' + btn("part-" + (j + 1), dot(j) + "<span><small>" + esc(p.l) + "</small><b>" + esc(p.t) + "</b></span>", "partb") +
               '<ul class="p-chips">' + p.ch.map(function (n) {
                 return "<li>" + btn("ch" + n, '<img src="' + esc(chOf(n).img) + '" alt=""><span>' + digits(n) + "</span>", "chip") + "</li>";
               }).join("") + "</ul></div>";
      }).join(""));
      html += sec3(esc(U.paths), '<ul class="p-list">' + PATHS.map(function (p, j) {
        return "<li>" + btn("path-" + j, '<i class="pdot route" aria-hidden="true"></i><span><b>' + esc(p.t) + "</b><small>" + esc(fmt(U.steps, { n: p.st.length })) + "</small></span>") + "</li>";
      }).join("") + "</ul>");
      html += '<p class="p-foot"><a href="' + esc(D.root.u) + '">' + esc(U.entry) + " · " + esc(D.root.t) + " " + ARROW + "</a></p>";
    } else if (s.kind === "part") {
      var p = PARTS[s.j];
      html = head([["root", D.root.t]], p.l, p.t, s.j) + '<div class="p-body"><ul class="p-list chl">' +
             p.ch.map(function (n) { return chBtn(n, esc(chOf(n).b)); }).join("") + "</ul></div>";
    } else if (s.kind === "ch" || (s.kind === "con" && CON[s.id].s < 0)) {
      var n = focusChapter(s), c = chOf(n), cid = s.kind === "con" ? s.id : null;
      if (cid) {
        var cc = CON[cid];
        html = head([["root", D.root.t], ["ch" + n, shortCh(n)]], U.concept + " · " + c.l, cc.t, c.p) + '<div class="p-body">';
        if (cc.l) html += '<p class="p-line">' + esc(cc.l) + "</p>";
        html += '<div class="p-acts"><a class="btn primary" href="../concepts/' + esc(cid) + '.html">' + esc(U.entry) + " " + ARROW + "</a></div>";
        html += sec3(esc(U.where), '<a class="guidebox" href="' + esc(c.h) + '"><img src="' + esc(c.im) + '" alt="" loading="lazy"><span><small>' + esc(c.l) +
                "</small><b>" + esc(c.t) + '</b><small class="sec">' + esc(U.read) + "</small></span></a>");
        html += relatedConcepts(cid);
        html += "</div>";
      } else {
        html = head([["root", D.root.t], ["part-" + (c.p + 1), PARTS[c.p].l]], c.l + " · " + PARTS[c.p].t, c.t, c.p) + '<div class="p-body">';
        if (c.b) html += '<p class="p-line">' + esc(c.b) + "</p>";
        html += progressBox(c);
        html += '<div class="p-acts"><a class="btn primary" href="' + esc(c.h) + '">' + esc(U.read) + " " + ARROW + "</a>" +
                (c.a ? '<a class="btn" href="../guide/audio/#' + c.n + '">' + esc(fmt(U.listen, { n: c.a })) + "</a>" : "") + "</div>";
        var extras = (c.dp ? '<a href="' + esc(c.dp) + '">' + esc(U.deeper) + " " + ARROW + "</a>" : "") + (c.rv ? '<a href="' + esc(c.rv) + '">' + esc(U.practise) + " " + ARROW + "</a>" : "");
        if (extras) html += '<p class="p-more">' + extras + "</p>";
        html += sec3(esc(U.sections) + " · " + digits(c.secs.length), '<ol class="p-list secl">' + c.secs.map(function (i) { return secBtn(i); }).join("") + "</ol>");
        var cons = c.cons.concat(c.secs.reduce(function (a, i) { return a.concat(S[i].k); }, []));
        if (cons.length) html += sec3(esc(U.entries) + " · " + digits(cons.length), '<ul class="p-tags">' + cons.map(function (id) { return "<li>" + btn(id, esc(CON[id].t)) + "</li>"; }).join("") + "</ul>");
        var pr = partners(n).slice(0, 5);
        if (pr.length) html += sec3(esc(U.connected), '<ul class="p-list chl">' + pr.map(function (x) { return chBtn(x.n, esc(fmt(U.linksn, { n: x.w }))); }).join("") + "</ul>");
        var ons = PATHS.map(function (p, j) { return { p: p, j: j }; }).filter(function (x) { return x.j > 0 && x.p.st.some(function (y) { return y[0] === n; }); });
        if (ons.length) html += sec3(esc(U.onpaths), '<ul class="p-list">' + ons.map(function (x) {
          return "<li>" + btn("path-" + x.j, '<i class="pdot route" aria-hidden="true"></i><span><b>' + esc(x.p.t) + "</b></span>") + "</li>";
        }).join("") + "</ul>");
        html += "</div>";
      }
    } else if (s.kind === "sec" || s.kind === "con") {
      var i = focusSection(s), se = S[i], sc_ = chOf(se.c), con = s.kind === "con" ? s.id : null;
      var crumbs = [["root", D.root.t], ["ch" + se.c, shortCh(se.c)]];
      if (con) {
        var co = CON[con];
        crumbs.push([se.key, "§ " + short(se.t, 28)]);
        html = head(crumbs, U.concept + " · " + sc_.l, co.t, sc_.p) + '<div class="p-body">';
        if (co.l) html += '<p class="p-line">' + esc(co.l) + "</p>";
        html += '<div class="p-acts"><a class="btn primary" href="../concepts/' + esc(con) + '.html">' + esc(U.entry) + " " + ARROW + "</a></div>";
        html += sec3(esc(U.where), '<a class="guidebox" href="' + esc(sc_.h + "#" + (co.a || se.id)) + '"><img src="' + esc(sc_.im) + '" alt="" loading="lazy"><span><small>' +
                esc(sc_.l) + "</small><b>" + esc(sc_.t) + '</b><small class="sec">§ ' + esc(se.t) + "</small></span></a>" +
                '<p class="p-more">' + btn(se.key, esc(U.showsec) + " " + ARROW, "lnkbtn") + "</p>");
        html += relatedConcepts(con);
        var same = se.k.filter(function (x) { return x !== con; });
        if (same.length) html += sec3(esc(U.same), '<ul class="p-list">' + same.map(conBtn).join("") + "</ul>");
        html += "</div>";
      } else {
        html = head(crumbs, sc_.l + " · " + fmt(U.sec, { i: se.ord + 1, n: sc_.secs.length }), se.t, sc_.p) + '<div class="p-body">';
        if (se.x) html += '<p class="p-ex">' + esc(se.x) + "</p>";
        html += '<div class="p-acts"><a class="btn primary" href="' + esc(sc_.h + "#" + se.id) + '">' + esc(U.readsec) + " " + ARROW + "</a>" +
                (se.d ? '<a class="btn" href="' + esc(se.d) + '">' + esc(U.deeper) + "</a>" : "") + "</div>";
        if (se.k.length) html += sec3(esc(U.entries), '<ul class="p-list">' + se.k.map(conBtn).join("") + "</ul>");
        if (se.g.length) html += sec3(esc(U.terms), '<ul class="p-tags">' + se.g.map(function (g) { return '<li><a href="' + esc(g[1]) + '">' + esc(g[0]) + "</a></li>"; }).join("") + "</ul>");
        var outs = out[i], ins = inn[i];
        var refList = function (list) {
          return '<ul class="p-list">' + list.map(function (j) { return j >= 0 ? secBtn(j, shortCh(S[j].c)) : chBtn(-j); }).join("") + "</ul>";
        };
        if (outs.length) html += sec3(esc(U.out) + " · " + digits(outs.length), refList(outs));
        if (ins.length) html += sec3(esc(U["in"]) + " · " + digits(ins.length), refList(ins));
        var prev = i > 0 ? S[i - 1] : null, next = i < nS - 1 ? S[i + 1] : null;
        html += '<nav class="p-step">' + (prev ? btn(prev.key, "<small>" + (FA ? "→ " : "← ") + esc(U.prev) + "</small><b>" + esc(short(prev.t, 30)) + "</b>", "pv") : "<span></span>") +
                (next ? btn(next.key, "<small>" + esc(U.next) + (FA ? " ←" : " →") + "</small><b>" + esc(short(next.t, 30)) + "</b>", "nx") : "") + "</nav>";
        html += "</div>";
      }
    } else if (s.kind === "path") {
      var pa = PATHS[s.j];
      html = head([["root", D.root.t]], U.path + " · " + fmt(U.steps, { n: pa.st.length }), pa.t) + '<div class="p-body">';
      if (pa.m) html += '<p class="p-line">' + esc(pa.m) + "</p>";
      html += '<div class="p-acts"><a class="btn primary" href="' + esc(chOf(pa.st[0][0]).h) + '">' + esc(U.start) + " " + ARROW + "</a>" +
              '<button type="button" class="btn" data-act="leave">' + esc(U.closepath) + "</button></div>";
      html += '<ol class="p-list steps">' + pa.st.map(function (x, k) {
        var c2 = chOf(x[0]);
        return "<li>" + btn("ch" + x[0], '<b class="num">' + digits(k + 1) + '</b><img src="' + esc(c2.img) + '" alt=""><span><small>' + esc(c2.l) + "</small><b>" + esc(c2.t) + "</b>" +
               (x[1] ? "<em>" + esc(x[1]) + "</em>" : "") + "</span>", "chb p" + c2.p) + "</li>";
      }).join("") + "</ol></div>";
    }
    panel.innerHTML = html;
    panel.scrollTop = 0;
    panel.classList.toggle("open", s.kind !== "root" || !narrow());
    syncToggle();
  }
  function relatedConcepts(id) {
    var ks = CON[id].k.filter(function (x) { return CON[x]; });
    return ks.length ? sec3(esc(U.related), '<ul class="p-list">' + ks.map(conBtn).join("") + "</ul>") : "";
  }
  function syncToggle() {
    var t = panel.querySelector(".p-toggle");
    if (!t) return;
    var open = panel.classList.contains("open");
    t.setAttribute("aria-expanded", open ? "true" : "false");
    t.setAttribute("aria-label", open ? U.close : U.open);
  }
  panel.addEventListener("click", function (e) {
    var b = e.target.closest("[data-sel]");
    if (b) { select(b.getAttribute("data-sel"), { keepPath: true }); return; }
    if (e.target.closest("[data-act=leave]")) { pathIdx = -1; select("root"); return; }
    if (e.target.closest(".p-toggle") || (narrow() && e.target.closest(".p-head") && !e.target.closest("a,button"))) {
      panel.classList.toggle("open"); syncToggle();
    }
  });

  /* ------------------------------------------------------------ choosing on the chart */
  var drag = null, moved = false;
  function idFrom(t) { var g = t && t.closest && t.closest("[data-sel]"); return g && svg.contains(g) ? g.getAttribute("data-sel") : null; }
  svg.addEventListener("click", function (e) {
    if (moved) return;
    var id = idFrom(e.target);
    if (!id) return;
    if (id === selId && /^ch\d+$/.test(id)) id = "root";  // a second click on the chosen chapter lets it go
    select(id, { keepPath: true });
  });
  svg.addEventListener("pointerover", function (e) {
    if (e.pointerType === "touch" || drag) return;
    var id = idFrom(e.target), s = id && id !== "root" ? parse(id) : null;
    if (s && s.kind !== "path" && id !== hover_id) { hover = s; hover_id = id; markPops(); paint(); renderLabels(); }
  });
  var hover_id = null;
  svg.addEventListener("pointerout", function (e) {
    if (!hover) return;
    var to = idFrom(e.relatedTarget);
    if (to !== hover_id) { hover = null; hover_id = null; markPops(); paint(); renderLabels(); }
  });
  // the keyboard: arrows step through the sections (or chapters), Escape goes back up
  chart.addEventListener("keydown", function (e) {
    if (e.target.closest("input, .chart-res")) return;
    var inSvg = svg.contains(e.target);
    var id = inSvg ? idFrom(e.target) : null;
    if (inSvg && id && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(id, { keepPath: true }); return; }
    if (e.key === "Escape") {
      var up = sel.kind === "sec" ? "ch" + S[sel.i].c : sel.kind === "con" ? (CON[sel.id].s >= 0 ? S[CON[sel.id].s].key : "ch" + CON[sel.id].c) : "root";
      if (sel.kind !== "root") { e.preventDefault(); select(up, { keepPath: up !== "root" }); focusSel(); }
      return;
    }
    if (!inSvg) return;
    var fwd = e.key === (FA ? "ArrowLeft" : "ArrowRight"), back = e.key === (FA ? "ArrowRight" : "ArrowLeft");
    if (!fwd && !back && e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    var d = fwd || e.key === "ArrowDown" ? 1 : -1, nx;
    var fi = focusSection(sel), f = focusChapter(sel);
    if (e.key === "ArrowUp" && sel.kind !== "root") nx = fi >= 0 ? "ch" + f : "root";
    else if (e.key === "ArrowDown" && sel.kind === "ch") nx = S[chOf(f).secs[0]].key;
    else if (fi >= 0) nx = S[(fi + d + nS) % nS].key;
    else if (f) nx = "ch" + ((f - 1 + d + 16) % 16 + 1);
    else if (sel.kind === "part") nx = "part-" + ((sel.j + d + PARTS.length) % PARTS.length + 1);
    else nx = d > 0 ? "ch1" : "ch16";
    select(nx, { keepPath: true, dur: 520 });
    focusSel();
  });
  function focusSel() {
    var g = svg.querySelector('[data-sel="' + (sel.kind === "con" ? (CON[sel.id].s >= 0 ? S[CON[sel.id].s].key : "ch" + CON[sel.id].c) : selId) + '"]');
    if (g && g.focus) try { g.focus({ preventScroll: true }); } catch (_) { g.focus(); }
  }

  // drag to move (mouse and pen); two fingers to pinch on touch screens; Ctrl + scroll to zoom
  svg.addEventListener("pointerdown", function (e) {
    if (e.pointerType === "touch" || e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, tx: tx, ty: ty }; moved = false;
  });
  window.addEventListener("pointermove", function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!moved && Math.hypot(dx, dy) < 4) return;
    if (!moved) { moved = true; svg.classList.add("dragging"); settle(); drag.tx = tx - dx; drag.ty = ty - dy; }
    tx = drag.tx + dx; ty = drag.ty + dy; apply();
  });
  window.addEventListener("pointerup", function () { if (drag) { drag = null; svg.classList.remove("dragging"); setTimeout(function () { moved = false; }, 0); } });
  svg.addEventListener("wheel", function (e) {
    if (!(e.ctrlKey || e.metaKey)) return;  // plain scrolling scrolls the page
    e.preventDefault();
    settle();
    var b = svg.getBoundingClientRect(), ns = clamp(sc * Math.exp(-e.deltaY * 0.0022), MINS, MAXS);
    var cx = e.clientX - b.left, cy = e.clientY - b.top;
    tx = cx - (cx - tx) * ns / sc; ty = cy - (cy - ty) * ns / sc; sc = ns; apply(); renderLabels();
  }, { passive: false });
  var pinch = null;
  svg.addEventListener("touchstart", function (e) {
    if (e.touches.length !== 2) return;
    settle();
    var a = e.touches[0], b = e.touches[1], r = svg.getBoundingClientRect();
    pinch = { d: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY), x: (a.clientX + b.clientX) / 2 - r.left, y: (a.clientY + b.clientY) / 2 - r.top, tx: tx, ty: ty, sc: sc };
  }, { passive: true });
  svg.addEventListener("touchmove", function (e) {
    if (!pinch || e.touches.length !== 2) return;
    e.preventDefault();
    var a = e.touches[0], b = e.touches[1], r = svg.getBoundingClientRect();
    var d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    var x = (a.clientX + b.clientX) / 2 - r.left, y = (a.clientY + b.clientY) / 2 - r.top;
    var ns = clamp(pinch.sc * d / pinch.d, MINS, MAXS);
    tx = x - (pinch.x - pinch.tx) * ns / pinch.sc; ty = y - (pinch.y - pinch.ty) * ns / pinch.sc; sc = ns; apply(); renderLabels();
  }, { passive: false });
  svg.addEventListener("touchend", function (e) { if (e.touches.length < 2) pinch = null; });
  chart.querySelectorAll("[data-zoom]").forEach(function (b) {
    b.addEventListener("click", function () {
      var z = b.getAttribute("data-zoom");
      if (z === "fit") { select("root"); return; }
      settle();
      zoomAt(z === "in" ? 1.35 : 1 / 1.35);
    });
  });
  document.querySelectorAll("[data-map-go]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      chart.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      select(a.getAttribute("data-map-go"));
    });
  });

  /* ------------------------------------------------------------ search */
  var q = document.getElementById("mapq"), res = document.getElementById("mapres");
  var IDX = [];
  CH.forEach(function (c) { IDX.push({ id: "ch" + c.n, t: c.t, sub: c.l, k: U.kch, h: (c.t + " " + c.sh).toLowerCase(), r: 0 }); });
  Object.keys(CON).forEach(function (id) {
    var c = CON[id];
    if (id !== "root" && c.c) IDX.push({ id: id, t: c.t, sub: chOf(c.c).l, k: U.kcon, h: c.h + " " + c.t.toLowerCase(), r: 1 });
  });
  S.forEach(function (s) {
    IDX.push({ id: s.key, t: s.t, sub: chOf(s.c).l, k: U.ksec, h: s.t.toLowerCase(), r: 2 });
    s.g.forEach(function (g) { IDX.push({ id: s.key, t: g[0], sub: "§ " + s.t, k: U.kterm, h: g[0].toLowerCase(), r: 3 }); });
  });
  var hits = [], active = -1;
  function showResults() {
    var s = q.value.trim().toLowerCase();
    if (!s) { res.hidden = true; q.setAttribute("aria-expanded", "false"); return; }
    var seen = {};
    hits = IDX.filter(function (x) { return x.h.indexOf(s) >= 0; }).map(function (x) {
      var t = x.t.toLowerCase();
      return { x: x, o: (t.indexOf(s) === 0 ? 0 : t.indexOf(s) > 0 ? 1 : 2) * 10 + x.r };
    }).sort(function (a, b) { return a.o - b.o || a.x.t.length - b.x.t.length; })
      .filter(function (y) { var key = y.x.id + "|" + y.x.t; if (seen[key]) return false; seen[key] = 1; return true; })
      .slice(0, 9).map(function (y) { return y.x; });
    active = hits.length ? 0 : -1;
    res.innerHTML = hits.length ? hits.map(function (x, i) {
      return '<div role="option" id="mr' + i + '" data-go="' + esc(x.id) + '"' + (i === active ? ' aria-selected="true"' : "") + "><span><b>" + esc(x.t) + "</b><small>" +
             esc(x.k) + " · " + esc(x.sub) + "</small></span></div>";
    }).join("") : '<div class="none">' + esc(U.none) + "</div>";
    res.hidden = false; q.setAttribute("aria-expanded", "true");
    q.setAttribute("aria-activedescendant", active >= 0 ? "mr" + active : "");
  }
  function pick(id) { q.value = ""; res.hidden = true; q.setAttribute("aria-expanded", "false"); select(id, { keepPath: true }); }
  q.addEventListener("input", showResults);
  q.addEventListener("keydown", function (e) {
    if (res.hidden) return;
    if ((e.key === "ArrowDown" || e.key === "ArrowUp") && hits.length) {
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + hits.length) % hits.length;
      res.querySelectorAll("[role=option]").forEach(function (o, i) { o.setAttribute("aria-selected", i === active ? "true" : "false"); });
      q.setAttribute("aria-activedescendant", "mr" + active);
    } else if (e.key === "Enter" && active >= 0) { e.preventDefault(); pick(hits[active].id); }
    else if (e.key === "Escape") { res.hidden = true; q.setAttribute("aria-expanded", "false"); }
  });
  res.addEventListener("click", function (e) { var o = e.target.closest("[data-go]"); if (o) pick(o.getAttribute("data-go")); });
  document.addEventListener("click", function (e) { if (!e.target.closest(".chart-find")) { res.hidden = true; q.setAttribute("aria-expanded", "false"); } });

  /* ------------------------------------------------------------ start: the wheel turns into place */
  var hint = document.querySelector(".chart-hint");
  if (hint && window.matchMedia && matchMedia("(pointer: coarse)").matches) hint.textContent = hint.getAttribute("data-hint-touch");
  size();
  var start = decodeURIComponent(location.hash.slice(1)), first = start && parse(start) ? start : "root";
  if (first === "root" && !reduce) {
    st.rot = -0.9; st.intro = 0;
    render();
    var cam0 = camAfter(layoutFor({ kind: "root" }), { kind: "root" });
    tx = cam0.tx; ty = cam0.ty; sc = cam0.sc; apply();
    renderPanel(); paint();
    var lay0 = layoutFor({ kind: "root" }); lay0.intro = 1;
    animate(lay0, cam0, 1700);
  } else {
    render();
    var cam1 = camAfter(layoutFor({ kind: "root" }), { kind: "root" });
    tx = cam1.tx; ty = cam1.ty; sc = cam1.sc; apply(); renderLabels();
    select(first, { hash: false, dur: first === "root" ? 0 : 900 });
  }
  var rsz = 0;
  window.addEventListener("resize", function () {
    clearTimeout(rsz);
    rsz = setTimeout(function () {
      var w0 = W, h0 = H;
      size();
      if (Math.abs(W - w0) < 2 && Math.abs(H - h0) < 2) return;
      settle();
      var lay = layoutFor(sel), cam = camAfter(lay, sel);
      st.k = lay.k; st.mk = lay.mk; st.rot = lay.rot; tx = cam.tx; ty = cam.ty; sc = cam.sc;
      render(); apply();
    }, 140);
  });
  window.addEventListener("hashchange", function () {
    var id = decodeURIComponent(location.hash.slice(1));
    if (id && id !== selId && parse(id)) select(id, { hash: false });
  });
})();
