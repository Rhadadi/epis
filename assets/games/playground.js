/* The feet lab: a small experiment playground for confounding (Cause Detective, kids' version). Fourteen made-up children:
   bigger feet go with better reading, but only because older children have both. The child looks at everyone together,
   then sorts or colours by age, and sees the pattern vanish inside one age. Explorers get cards and bars; Investigators get
   a scatter plot, an age filter and the correlation numbers. Then a first-and-after question with careful feedback.
   data (one language, one level): {engine: "playground", title, intro, kids: [{age, foot, read}], text: {...}, choices: [...]} */
(function () {
  "use strict";
  var G = window.Games, T = G.T, el = G.el, N = G.N;
  var NS = "http://www.w3.org/2000/svg";
  var COLS = ["#E5484D", "#F29A4A", "#FFC92E", "#4FA35B", "#3E7FD0", "#8B5CF6", "#222"];

  function corr(a) {
    var n = a.length; if (n < 3) return null;
    var mx = a.reduce(function (s, p) { return s + p[0]; }, 0) / n, my = a.reduce(function (s, p) { return s + p[1]; }, 0) / n, sxy = 0, sxx = 0, syy = 0;
    a.forEach(function (p) { sxy += (p[0] - mx) * (p[1] - my); sxx += (p[0] - mx) * (p[0] - mx); syy += (p[1] - my) * (p[1] - my); });
    return sxx && syy ? sxy / Math.sqrt(sxx * syy) : 0;
  }
  function word(r) { return r === null ? "" : Math.abs(r) > .7 ? T("strongly", "به‌شدت") : Math.abs(r) > .35 ? T("a bit", "کمی") : T("hardly at all", "تقریباً هیچ"); }

  G.register("playground", function (box, data) {
    var level = box.getAttribute("data-level"), plot = level === "investigators";
    var kids = data.kids.slice().sort(function (a, b) { return a.foot - b.foot; });
    var ages = Array.from(new Set(kids.map(function (k) { return k.age; }))).sort(function (a, b) { return a - b; });
    var root = el("div", "pg"); box.appendChild(root);
    var state = { by: "none", only: 0, guess: null };
    root.appendChild(el("p", "pg-intro", data.intro));
    var view = el("div", "pg-view"), ctl = el("div", "pg-ctl"), note = el("p", "pg-note"), qa = el("div", "pg-qa");
    note.setAttribute("aria-live", "polite");
    root.appendChild(ctl); root.appendChild(view); root.appendChild(note); root.appendChild(qa);

    function tog(label, key, val) {
      var b = el("button", "my-chip", label); b.type = "button"; b.setAttribute("aria-pressed", state[key] === val ? "true" : "false");
      b.onclick = function () { state[key] = val; draw(); }; return b;
    }
    function controls() {
      ctl.innerHTML = "";
      var row = el("div", "my-chips");
      row.appendChild(tog(plot ? T("All kids, one colour", "همهٔ بچه‌ها، یک رنگ") : T("Everyone together", "همه با هم"), "by", "none"));
      row.appendChild(tog(plot ? T("Colour by age", "رنگ بر پایهٔ سن") : T("Sort by age", "مرتب بر پایهٔ سن"), "by", "age"));
      ctl.appendChild(row);
      if (plot && state.by === "age") {
        var lab = el("label", "pg-only"), out = el("output");
        var inp = document.createElement("input"); inp.type = "range"; inp.min = 0; inp.max = ages.length; inp.step = 1; inp.value = state.only ? ages.indexOf(state.only) + 1 : 0;
        lab.appendChild(el("span", "", T("Look at one age only", "فقط یک سن را ببین")));
        lab.appendChild(inp); lab.appendChild(out);
        var upd = function () { out.textContent = +inp.value ? N(ages[+inp.value - 1]) : T("all", "همه"); };
        inp.oninput = function () { state.only = +inp.value ? ages[+inp.value - 1] : 0; upd(); draw(true); }; upd();
        ctl.appendChild(lab);
      }
    }
    function cards() {
      view.innerHTML = "";
      var groups = state.by === "age" ? ages.map(function (a) { return kids.filter(function (k) { return k.age === a; }); }) : [kids];
      var leg = el("p", "pg-leg"); leg.innerHTML = '<i class="pg-sw foot"></i> ' + T("foot size", "اندازهٔ پا") + ' &nbsp; <i class="pg-sw read"></i> ' + T("reading", "خواندن");
      view.appendChild(leg);
      var wrap = el("div", "pg-groups");
      groups.forEach(function (g) {
        var col = el("div", "pg-group");
        if (state.by === "age") col.appendChild(el("b", "pg-age", T("Age ", "سن ") + N(g[0].age)));
        g.forEach(function (k) {
          var c = el("div", "pg-kid"); c.setAttribute("title", T("age " + k.age, "سن " + N(k.age)));
          c.appendChild(el("span", "pg-face", "☺"));
          var f = el("i", "pg-bar foot"); f.style.width = (k.foot - 12) * 7 + "px"; 
          var r = el("i", "pg-bar read"); r.style.width = (k.read - 10) * 1.4 + "px"; 
          c.appendChild(f); c.appendChild(r); col.appendChild(c);
        });
        wrap.appendChild(col);
      });
      view.appendChild(wrap);
    }
    function scatter() {
      view.innerHTML = "";
      var svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", "0 0 320 210"); svg.setAttribute("class", "pg-svg"); svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", T("Foot size and reading score of fourteen kids", "اندازهٔ پا و نمرهٔ خواندنِ چهارده بچه"));
      var add = function (tag, a, txt) { var n = document.createElementNS(NS, tag); Object.keys(a).forEach(function (k) { n.setAttribute(k, a[k]); }); if (txt) n.textContent = txt; svg.appendChild(n); return n; };
      add("path", { d: "M34 8 V176 H312", fill: "none", stroke: "#222", "stroke-width": 2 });
      add("text", { x: 172, y: 204, "text-anchor": "middle", "class": "pg-t" }, T("foot size →", "اندازهٔ پا ←"));
      add("text", { x: 10, y: 92, "class": "pg-t", transform: "rotate(-90 10 92)", "text-anchor": "middle" }, T("reading →", "خواندن ←"));
      var X = function (f) { return 40 + (f - 14) * 20; }, Y = function (r) { return 172 - (r - 15) * 2.1; };
      kids.forEach(function (k) {
        var on = !state.only || k.age === state.only, col = state.by === "age" ? COLS[ages.indexOf(k.age) % COLS.length] : "#666";
        add("circle", { cx: X(k.foot), cy: Y(k.read), r: 6, fill: col, opacity: on ? .95 : .12, stroke: "#222", "stroke-width": on ? 1.4 : 0 });
        if (state.by === "age" && on) add("text", { x: X(k.foot), y: Y(k.read) + 3.5, "text-anchor": "middle", "class": "pg-n" }, N(k.age));
      });
      view.appendChild(svg);
    }
    function draw(keep) {
      if (!keep) controls();
      if (plot) scatter(); else cards();
      // what the child can see, in words
      var all = corr(kids.map(function (k) { return [k.foot, k.read]; })), msg;
      if (state.by === "none") {
        msg = T("Bigger feet go with better reading, " + word(all) + " — hmm, why?", "پای بزرگ‌تر با خواندنِ بهتر همراه است، " + word(all) + " — هوم، چرا؟");
      } else if (plot) {
        var sub = state.only ? kids.filter(function (k) { return k.age === state.only; }) : null;
        if (sub) { var r1 = corr(sub.map(function (k) { return [k.foot, k.read]; })); msg = T("Only age " + state.only + ": ", "فقط سنِ " + N(state.only) + ": ") + (r1 === null ? T("too few kids to tell.", "بچه‌های کم‌تر از آن‌اند که بشود گفت.") : T("feet and reading go together " + word(r1) + ".", "پا و خواندن " + word(r1) + " با هم همراه‌اند.")); }
        else msg = T("Each colour is one age. Slide to look at one age: do bigger feet still read better?", "هر رنگ یک سن است. بکش و یک سن را ببین: آیا پای بزرگ‌تر باز هم بهتر می‌خواند؟");
      } else {
        var agree = 0, tot = 0;
        ages.forEach(function (a) { var g = kids.filter(function (k) { return k.age === a; }); if (g.length === 2) { tot++; if ((g[1].foot - g[0].foot) * (g[1].read - g[0].read) > 0) agree++; } });
        msg = T("Inside the same age, the bigger foot read better in only " + agree + " of " + tot + " groups. That looks like luck.", "درونِ یک سن، پای بزرگ‌تر فقط در " + N(agree) + " گروه از " + N(tot) + " بهتر می‌خواند. شبیهِ شانس است.");
      }
      note.textContent = msg;
      if (state.by === "age" && !qa.firstChild) question();
    }
    function question() {
      qa.innerHTML = "";
      qa.appendChild(el("p", "my-q", data.question));
      var row = el("div", "my-chips");
      data.choices.forEach(function (c) {
        var b = el("button", "my-chip", c.text); b.type = "button";
        b.onclick = function () {
          row.querySelectorAll("button").forEach(function (x) { x.disabled = true; });
          b.setAttribute("aria-pressed", "true");
          var fb = el("div", "my-verdict " + (c.ok ? "good" : "catch"));
          fb.appendChild(el("b", "", c.ok ? T("Good thinking!", "آفرین!") : c.unsure ? T("A fair answer.", "جواب منصفانه‌ای است.") : T("Not quite.", "نه دقیقاً.")));
          fb.appendChild(el("span", "", c.why)); qa.appendChild(fb);
          if (c.ok || c.unsure) G.star(box);
          G.say(c.why);
        };
        row.appendChild(b);
      });
      qa.appendChild(row);
    }
    draw();
  });
})();
