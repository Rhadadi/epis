/* Sandbox: a made-up town where a hidden factor (health, age…) decides both who is in which group and the
   outcome. Run "the study" and read the headline it would publish. Change the rules: how strongly the hidden
   factor sorts people into groups, what the treatment really does, how many people take part; let a coin decide
   the groups (a fair test), or compare only people alike in the hidden factor. Seeded random numbers, so the same
   settings give the same town. Used by the case engine: Games.sims.confounder(parent, sim, {params, controls}).

   sim (one language): {groups: [treated, untreated], outcome, base, spread, sd, unit, lo, hi, hidden,
     hidden_low, hidden_high, more, less, same, people, luck_yes, luck_no, luck_small, fixed,
     labels: {link, effect, n, coin, fix, show, run}}; outcome = base + spread × hidden (+ effect if treated) + noise. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var SIZES = [20, 50, 200, 1000, 5000];

  function rng(seed) {
    return function () {
      seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(r) { var u = 1 - r(), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

  // the town and the study: returns both groups (people with hidden factor h and outcome y) and the headline numbers
  function study(sim, p) {
    var r = rng(p.seed || 7), groups = [[], []];
    for (var i = 0; i < p.n; i++) {
      var h = r();
      var pin = p.coin ? 0.5 : 0.5 + (p.link / 100) * 0.35 * (2 * h - 1);
      var g = r() < pin ? 0 : 1;
      var y = sim.base + sim.spread * h + (g === 0 ? p.effect : 0) + sim.sd * gauss(r);
      if (p.fix && (h < 0.42 || h > 0.58)) continue;
      groups[g].push({ h: h, y: y, j: r() });
    }
    var st = groups.map(function (g) {
      var m = g.reduce(function (s, x) { return s + x.y; }, 0) / Math.max(1, g.length);
      var v = g.reduce(function (s, x) { return s + (x.y - m) * (x.y - m); }, 0) / Math.max(1, g.length - 1);
      return { n: g.length, mean: m, v: v };
    });
    var diff = st[0].mean - st[1].mean;
    var se = Math.sqrt(st[0].v / Math.max(1, st[0].n) + st[1].v / Math.max(1, st[1].n));
    return { groups: groups, st: st, pct: 100 * diff / st[1].mean, luck: Math.abs(diff) < 2 * se };
  }

  function make(parent, sim, opts) {
    var G = window.Games, T = G.T, N = G.N, el = G.el, L = sim.labels || {};
    var p = { link: 95, effect: 0, n: 1000, coin: false, fix: false, show: false, seed: 7 };
    Object.keys(opts.params || {}).forEach(function (k) { p[k] = opts.params[k]; });
    var box = el("div", "sim");
    var head = el("p", "sim-headline"); head.setAttribute("aria-live", "polite");
    var sub = el("p", "sim-sub");
    box.appendChild(head); box.appendChild(sub);
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "sim-svg"); svg.setAttribute("role", "img");
    box.appendChild(svg);
    var legend = el("p", "sim-legend");
    box.appendChild(legend);

    var controls = el("div", "sim-ctls"), inputs = {};
    (opts.controls || []).forEach(function (k) {
      if (k === "coin" || k === "fix" || k === "show") {
        var b = el("button", "sim-tog", L[k] || k); b.type = "button";
        b.setAttribute("aria-pressed", p[k] ? "true" : "false");
        b.onclick = function () { p[k] = !p[k]; b.setAttribute("aria-pressed", p[k] ? "true" : "false"); draw(); };
        inputs[k] = b; controls.appendChild(b);
        return;
      }
      var lab = el("label", "sim-ctl"), name = el("span", "", L[k] || k), out = el("output");
      var inp = document.createElement("input");
      inp.type = "range";
      if (k === "link") { inp.min = 0; inp.max = 100; inp.step = 5; inp.value = p.link; }
      if (k === "effect") { inp.min = -4; inp.max = 4; inp.step = 1; inp.value = p.effect; }
      if (k === "n") { inp.min = 0; inp.max = SIZES.length - 1; inp.step = 1; inp.value = Math.max(0, SIZES.indexOf(p.n)); }
      inp.oninput = function () {
        if (k === "n") p.n = SIZES[+inp.value]; else p[k] = +inp.value;
        draw();
      };
      lab.appendChild(name); lab.appendChild(inp); lab.appendChild(out);
      inputs[k] = { input: inp, out: out, label: lab };
      controls.appendChild(lab);
    });
    var again = el("button", "sim-run", L.run || T("Run the study again", "دوباره پژوهش کن")); again.type = "button";
    again.onclick = function () { p.seed = (p.seed * 7919 + 13) % 100003; draw(); };
    controls.appendChild(again);
    box.appendChild(controls);
    parent.appendChild(box);

    function fill(t, vals) { return String(t || "").replace(/\{(\w+)\}/g, function (_, k) { return vals[k]; }); }
    function svgAdd(tag, attrs, text) {
      var n = document.createElementNS(NS, tag);
      Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
      if (text !== undefined) n.textContent = text;
      svg.appendChild(n); return n;
    }
    function draw() {
      var res = study(sim, p), st = res.st;
      var pct = Math.round(Math.abs(res.pct));
      head.textContent = pct < 1 ? fill(sim.same, {}) : fill(res.pct > 0 ? sim.more : sim.less, { pct: N(pct) });
      head.className = "sim-headline " + (pct < 1 ? "same" : res.pct > 0 ? "more" : "less");
      var who = fill(sim.people || T("{n} people compared", "{n} نفر مقایسه شدند"), { n: N(st[0].n + st[1].n) });
      var luck = st[0].n + st[1].n < 100 && sim.luck_small ? sim.luck_small : res.luck ? sim.luck_yes : sim.luck_no;
      sub.textContent = who + " · " + luck + (p.fix && sim.fixed ? " · " + sim.fixed : "");
      if (inputs.link) {
        inputs.link.out.textContent = N(p.link) + "%";
        inputs.link.input.disabled = p.coin; inputs.link.label.classList.toggle("off", p.coin);
      }
      if (inputs.effect) inputs.effect.out.textContent = (p.effect > 0 ? "+" : "") + N(p.effect) + (sim.unit || "");
      if (inputs.n) inputs.n.out.textContent = N(p.n);
      // the picture: one lane per group, a dot per person (up to 110 per lane), the group's average as a line;
      // drawn at the width it is shown, so its labels stay readable on a phone
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var W = Math.max(280, Math.round(box.clientWidth - 28) || 600);
      svg.setAttribute("viewBox", "0 0 " + W + " 182");
      var lo = sim.lo, hi = sim.hi, x = function (v) { return 14 + (W - 28) * Math.max(0, Math.min(1, (v - lo) / (hi - lo))); };
      [0, 1].forEach(function (g) {
        var top = g ? 96 : 14, people = res.groups[g].slice(0, 110);
        svgAdd("rect", { x: 6, y: top - 6, width: W - 12, height: 72, rx: 14, "class": "lane l" + g });
        svgAdd("text", { x: 16, y: top + 10, "class": "lane-t" }, sim.groups[g] + " · " + N(st[g].n));
        people.forEach(function (d) {
          var cls = p.show ? (d.h < 0.34 ? "h0" : d.h < 0.67 ? "h1" : "h2") : "g" + g;
          svgAdd("circle", { cx: x(d.y), cy: top + 22 + d.j * 36, r: 4.2, "class": "pp " + cls });
        });
        if (st[g].n) {
          svgAdd("line", { x1: x(st[g].mean), x2: x(st[g].mean), y1: top + 14, y2: top + 62, "class": "mean" });
          svgAdd("text", { x: x(st[g].mean), y: top + 74 - 4, "text-anchor": "middle", "class": "mean-t" }, N(st[g].mean.toFixed(1)));
        }
      });
      svgAdd("text", { x: 14, y: 178, "class": "tick" }, N(lo));
      svgAdd("text", { x: W / 2, y: 178, "text-anchor": "middle", "class": "tick" }, sim.outcome + " →");
      svgAdd("text", { x: W - 14, y: 178, "text-anchor": "end", "class": "tick" }, N(hi));
      svg.setAttribute("aria-label", head.textContent + ". " + sub.textContent);
      legend.innerHTML = "";
      if (p.show) {
        [["h0", sim.hidden_low], ["h1", T("in between", "میانه")], ["h2", sim.hidden_high]].forEach(function (k) {
          var s = el("span"); s.appendChild(el("i", k[0])); s.appendChild(document.createTextNode(k[1])); legend.appendChild(s);
        });
        legend.insertBefore(el("b", "", sim.hidden + ":"), legend.firstChild);
      } else {
        sim.groups.forEach(function (name, g) {
          var s = el("span"); s.appendChild(el("i", "g" + g)); s.appendChild(document.createTextNode(name)); legend.appendChild(s);
        });
      }
    }
    draw();
    requestAnimationFrame(draw);  // again once on the page, at its real width
    var last = box.clientWidth;
    window.addEventListener("resize", function () {
      if (Math.abs(box.clientWidth - last) > 20) { last = box.clientWidth; requestAnimationFrame(draw); }
    });
  }

  window.Games = window.Games || {};
  Games.sims = Games.sims || {};
  Games.sims.confounder = make;
  Games.sims.confounder.study = study;  // for tests
})();
