/* The case engine (Correlation Detective, the kids' openers, and every game built like them). The order follows
   good explorable explanations: a question, your prediction, clues one at a time (with a chance to change your
   mind after each), a surprise, the explanation, and, if the case has one, a sandbox where you make the rules.
   Nothing is marked right or wrong until the end, and the end shows how your answer moved.

   Data (one language, already picked by the build):
   {title, again, done, share, cases: [{id, label, headline, q,
     choices: [{id, text, short, why}], best: [choice ids],
     clues: [{title, text, chart: {kind: "bars"|"strip", …}}],
     surprise: {text, after, params}, ideas: [{name, text}], sim: {…}, sandbox: {intro, params, controls},
     next: {text, href}}]} */
(function () {
  "use strict";
  Games.register("case", function (box, data, G) {
    var T = G.T, N = G.N, el = G.el;
    var cases = data.cases || [], ci = 0, changes = 0, good = 0;

    function show(node, focus) {
      node.scrollIntoView({ block: "nearest", behavior: G.reduced() ? "auto" : "smooth" });
      if (focus) { node.setAttribute("tabindex", "-1"); node.focus({ preventScroll: true }); }
    }
    function choiceOf(c, id) { return c.choices.filter(function (x) { return x.id === id; })[0] || {}; }

    // one question with the case's choices; "current" is the answer so far (marked, but you still have to tap)
    function ask(parent, prompt, c, current, done) {
      var q = el("div", "cs-ask");
      q.appendChild(el("p", "cs-q", prompt));
      var list = el("div", "cs-choices");
      list.setAttribute("role", "group");
      list.setAttribute("aria-label", prompt);
      c.choices.forEach(function (ch) {
        var b = el("button", "cs-choice"); b.type = "button";
        b.appendChild(el("span", "", ch.text));
        if (ch.id === current) {
          b.classList.add("current");
          b.appendChild(el("small", "cs-tag", T("your answer so far", "جوابِ تا این‌جا")));
        }
        b.onclick = function () {
          list.querySelectorAll("button").forEach(function (x) { x.disabled = true; x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
          b.classList.add("picked");
          q.classList.add("answered");
          done(ch.id);
        };
        list.appendChild(b);
      });
      q.appendChild(list);
      parent.appendChild(q);
      return q;
    }

    function chart(spec) {
      if (!spec) return null;
      if (spec.kind === "bars") {
        var max = spec.max || Math.max.apply(null, spec.bars.map(function (b) { return b.value; })) * 1.1;
        var w = el("div", "cs-bars");
        if (spec.caption) w.appendChild(el("p", "cs-chart-cap", spec.caption));
        spec.bars.forEach(function (b) {
          var row = el("div", "cs-bar" + (b.hi ? " hi" : ""));
          row.appendChild(el("span", "cs-bar-l", b.label));
          var track = el("span", "cs-bar-t"), fill = el("i");
          fill.style.width = Math.max(2, Math.min(100, 100 * b.value / max)) + "%";
          track.appendChild(fill); row.appendChild(track);
          row.appendChild(el("b", "cs-bar-v", N(b.value) + (spec.unit || "")));
          w.appendChild(row);
        });
        return w;
      }
      if (spec.kind === "strip") {  // many results on one line, one of them picked out; drawn at its shown width
        var w2 = el("div", "cs-stripw");
        if (spec.caption) w2.appendChild(el("p", "cs-chart-cap", spec.caption));
        var ns = "http://www.w3.org/2000/svg";
        var svg = document.createElementNS(ns, "svg");
        svg.setAttribute("class", "cs-strip"); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", spec.caption || "");
        w2.appendChild(svg);
        var draw = function () {
          var W = Math.max(260, w2.clientWidth || 600), H = 92, lo = spec.min, hi = spec.max;
          var x = function (v) { return 20 + (W - 40) * (v - lo) / (hi - lo); };
          var add = function (tag, attrs, text) {
            var n = document.createElementNS(ns, tag);
            Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
            if (text !== undefined) n.textContent = text;
            svg.appendChild(n); return n;
          };
          while (svg.firstChild) svg.removeChild(svg.firstChild);
          svg.setAttribute("viewBox", "0 0 " + W + " " + H);
          add("line", { x1: 20, x2: W - 20, y1: 46, y2: 46, "class": "axis" });
          add("line", { x1: x(0), x2: x(0), y1: 30, y2: 62, "class": "zero" });
          spec.values.forEach(function (v, i) {
            add("circle", { cx: x(v), cy: 46 + ((i * 7) % 3 - 1) * 7, r: i === spec.hi ? 9 : 6, "class": i === spec.hi ? "hi" : "dot" });
          });
          if (spec.hi_label) add("text", { x: Math.min(W - 30, x(spec.values[spec.hi])), y: 20, "text-anchor": "middle", "class": "lab" }, spec.hi_label);
          add("text", { x: 20, y: 84, "class": "tick" }, N(lo) + (spec.unit || ""));
          add("text", { x: x(0), y: 84, "text-anchor": "middle", "class": "tick" }, N(0));
          add("text", { x: W - 20, y: 84, "text-anchor": "end", "class": "tick" }, "+" + N(hi) + (spec.unit || ""));
        };
        requestAnimationFrame(draw);
        window.addEventListener("resize", function () { requestAnimationFrame(draw); });
        return w2;
      }
      return null;
    }

    function clue(c, k) {
      var cl = c.clues[k];
      var s = el("section", "cs-clue");
      s.appendChild(el("p", "cs-clue-k", c.clues.length > 1 ? T("Clue ", "سرنخِ ") + N(k + 1) + T(" of ", " از ") + N(c.clues.length) : T("A clue", "یک سرنخ")));
      if (cl.title) s.appendChild(el("h3", "", cl.title));
      if (cl.text) s.appendChild(el("p", "", cl.text));
      var ch = chart(cl.chart);
      if (ch) s.appendChild(ch);
      return s;
    }

    function simulate(parent, c, mode) {
      var make = G.sims && c.sim && G.sims[c.sim.kind];
      if (!make) return false;
      var cfg = mode === "surprise" ? { params: c.surprise.params, controls: [] } : c.sandbox;
      make(parent, c.sim, { params: cfg.params || {}, controls: cfg.controls || [] });
      return true;
    }

    function finish(wrap, c, picks) {
      var end = el("section", "cs-end");
      if (c.surprise) {
        var sp = el("div", "cs-surprise");
        sp.appendChild(el("p", "cs-clue-k", T("The twist", "پیچِ ماجرا")));
        sp.appendChild(el("p", "", c.surprise.text));
        simulate(sp, c, "surprise");
        if (c.surprise.after) sp.appendChild(el("p", "cs-after", c.surprise.after));
        end.appendChild(sp);
      }
      if (c.ideas && c.ideas.length) {
        var ideas = el("div", "cs-ideas");
        ideas.appendChild(el("p", "cs-clue-k", T("What was going on", "ماجرا چه بود")));
        c.ideas.forEach(function (it) {
          var d = el("div", "cs-idea");
          d.appendChild(el("b", "", it.name)); d.appendChild(el("span", "", it.text));
          ideas.appendChild(d);
        });
        end.appendChild(ideas);
      }
      var last = picks[picks.length - 1], ok = (c.best || []).indexOf(last) >= 0;
      if (ok) good++;
      var v = el("div", "cs-verdict " + (ok ? "good" : "catch"));
      v.appendChild(el("b", "", ok ? T("Well reasoned!", "خوب فکر کردی!") : T("Here's the catch", "نکته این‌جاست")));
      v.appendChild(el("p", "", choiceOf(c, last).why || ""));
      if (!ok && c.best && c.best.length) {
        v.appendChild(el("p", "cs-best", T("Better answer: ", "جوابِ بهتر: ") + c.best.map(function (id) { return "“" + choiceOf(c, id).text + "”"; }).join(T(" or ", " یا "))));
      }
      if (picks.length > 1) {
        var path = el("ol", "cs-path");
        path.setAttribute("aria-label", T("How your answer moved", "جوابت چطور عوض شد"));
        picks.forEach(function (id, i) {
          var li = el("li", i && id !== picks[i - 1] ? "moved" : "");
          li.appendChild(el("small", "", i === 0 ? T("First guess", "حدسِ اول") : T("After clue ", "بعد از سرنخِ ") + N(i)));
          li.appendChild(el("span", "", choiceOf(c, id).short || choiceOf(c, id).text));
          path.appendChild(li);
        });
        v.appendChild(path);
      }
      end.appendChild(v);
      if (c.sandbox && c.sim) {
        var sb = el("div", "cs-sandbox");
        sb.appendChild(el("p", "cs-clue-k", T("Your turn", "نوبتِ تو")));
        if (c.sandbox.intro) sb.appendChild(el("p", "", c.sandbox.intro));
        if (!simulate(sb, c, "sandbox")) sb.remove(); else end.appendChild(sb);
      }
      var nav = el("div", "cs-nav");
      if (c.next && c.next.href) {
        var a = el("a", "cs-go", c.next.text); a.href = c.next.href;
        a.addEventListener("click", function () { G.star(box); });
        nav.appendChild(a);
      } else if (ci + 1 < cases.length) {
        var nb = el("button", "cs-go", T("Next case", "پروندهٔ بعدی")); nb.type = "button";
        nb.onclick = function () { ci++; start(); };
        nav.appendChild(nb);
      } else {
        nav.appendChild(summary());
      }
      end.appendChild(nav);
      wrap.appendChild(end);
      show(end.firstChild, true);
    }

    function summary() {
      var d = el("div", "cs-done");
      d.appendChild(el("span", "kg-star", "★"));
      d.appendChild(el("p", "", T("You changed your mind ", "") + N(changes) + T(changes === 1 ? " time." : " times.", " بار نظرت را عوض کردی.")));
      if (cases.length > 1) d.appendChild(el("p", "", T("Your final answer was a good one in ", "جوابِ آخرت در ") + N(good) + T(" of ", " پرونده از ") + N(cases.length) + T(" cases.", " پرونده خوب بود.")));
      if (data.done) d.appendChild(el("p", "cs-moral", data.done));
      var row = el("div", "cs-row");
      if (data.share && (navigator.share || navigator.clipboard)) {
        var sh = el("button", "cs-go alt", T("Share this game", "این بازی را بفرست")); sh.type = "button";
        sh.onclick = function () {
          var url = location.href.split("#")[0];
          var text = T("I changed my mind " + changes + " times in " + data.title + ". Can you do better?",
                       "در «" + data.title + "» " + N(changes) + " بار نظرم عوض شد. تو چطور؟");
          if (navigator.share) navigator.share({ title: data.title, text: text, url: url }).catch(function () {});
          else navigator.clipboard.writeText(url).then(function () { sh.textContent = T("Link copied", "پیوند کپی شد"); });
        };
        row.appendChild(sh);
      }
      var again = el("button", "cs-go", T("Play again", "دوباره بازی کن")); again.type = "button";
      again.onclick = function () { ci = 0; changes = 0; good = 0; start(); };
      row.appendChild(again);
      d.appendChild(row);
      G.star(box);
      G.say(T("Finished! You earned a star.", "تمام شد! یک ستاره گرفتی."));
      return d;
    }

    function start() {
      box.querySelectorAll(".cs").forEach(function (n) { n.remove(); });
      var c = cases[ci], picks = [], k = 0;
      var wrap = el("div", "cs");
      var top = el("div", "cs-top");
      if (cases.length > 1) top.appendChild(el("span", "cs-count", T("Case ", "پروندهٔ ") + N(ci + 1) + T(" of ", " از ") + N(cases.length)));
      if (c.label) top.appendChild(el("span", "cs-label", c.label));
      wrap.appendChild(top);
      wrap.appendChild(el("p", "cs-headline", c.headline));
      box.appendChild(wrap);
      function step(id) {
        if (picks.length && id !== picks[picks.length - 1]) changes++;
        picks.push(id);
        if (k < (c.clues || []).length) {
          var card = clue(c, k++);
          wrap.appendChild(card);
          ask(wrap, data.again || T("Has your mind changed?", "نظرت عوض شد؟"), c, id, step);
          show(card, true);
        } else {
          finish(wrap, c, picks);
        }
      }
      ask(wrap, c.q, c, null, step);
      if (ci) show(wrap, true);
    }
    start();
  });
})();
