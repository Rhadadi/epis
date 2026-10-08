/* The mission engine: a drawn scene to investigate. The child makes a first guess and says how sure they are, looks at
   a limited number of things (each gives a clue that may be weak, strong or tricky), then reconsiders. The feedback shows
   how the answer moved, whether the confidence matches the clues that were checked (including "not enough evidence yet"
   and "keep your answer"), what each clue could not rule out, and what was left unchecked. Useful reasoning earns badges;
   changing an answer by itself earns nothing. Rounds follow each other, the last one with a new situation to test transfer.

   data (one language, one level): {engine: "mystery", title, labels?, rounds: [{
     intro, stage: {bg, actors[], props[]}, hyps: [{id, text, unsure?}], limit,
     sources: [{id, target (id of a stage item), label, clue, pts: {hyp: n}, kind: "weak"|"strong", tricky}],
     given?: "a clue the child already has", changers?: [{id, text, good}],
     rules: [{if: [source ids that must all be checked], best: hyp id, conf: 0|1|2, why}]   (first match wins; last has if: [])
   }]}                                                                                                               */
(function () {
  "use strict";
  var G = window.Games, T = G.T, el = G.el, N = G.N;
  var CONF = function () { return [T("Just a guess", "فقط حدس"), T("Pretty sure", "نسبتاً مطمئن"), T("Very sure", "خیلی مطمئن")]; };

  G.register("mystery", function (box, data) {
    var rounds = data.rounds, ri = 0, badges = {};
    var root = el("div", "my"); box.appendChild(root);

    function chips(parent, items, cur, onpick, cls) {
      var row = el("div", cls || "my-chips"); row.setAttribute("role", "group");
      var btns = items.map(function (it, i) {
        var b = el("button", "my-chip" + (it.unsure ? " unsure" : ""), it.text); b.type = "button";
        b.setAttribute("aria-pressed", cur === it.id ? "true" : "false");
        b.onclick = function () { onpick(it.id); btns.forEach(function (x, j) { x.setAttribute("aria-pressed", items[j].id === it.id ? "true" : "false"); }); };
        row.appendChild(b); return b;
      });
      parent.appendChild(row); return row;
    }
    function confRow(parent, cur, onpick) {
      var items = CONF().map(function (t, i) { return { id: i, text: t }; });
      return chips(parent, items, cur, onpick, "my-chips my-conf");
    }
    function stageFor(r, hot) {
      var st = el("div", "dstage my-stage"); st.setAttribute("aria-hidden", "true");
      var S = window.Scenes && window.Scenes.Stage;
      if (!S) return { el: st, stage: null };
      var stage = S(st); stage.set(r.stage, true);
      return { el: st, stage: stage };
    }
    function round() {
      var r = rounds[ri], S = { first: null, firstConf: 1, seen: [], final: null, finalConf: 1, changer: null };
      root.innerHTML = "";
      var head = el("p", "my-count", rounds.length > 1 ? T("Case " + (ri + 1) + " of " + rounds.length, "پرونده " + N(ri + 1) + " از " + N(rounds.length)) : "");
      if (head.textContent) root.appendChild(head);
      var sc = stageFor(r); root.appendChild(sc.el);
      var panel = el("div", "my-panel"); root.appendChild(panel);
      panel.setAttribute("aria-live", "polite");
      function say(n) { G.say(n); }

      // 1. first guess
      function ask1() {
        panel.innerHTML = "";
        panel.appendChild(el("p", "my-intro", r.intro));
        if (r.given) panel.appendChild(el("p", "my-given", r.given));
        panel.appendChild(el("p", "my-q", T("What do you think?", "تو چه فکر می‌کنی؟")));
        chips(panel, r.hyps, S.first, function (id) { S.first = id; go.disabled = false; });
        panel.appendChild(el("p", "my-q2", T("How sure are you?", "چقدر مطمئنی؟")));
        confRow(panel, S.firstConf, function (i) { S.firstConf = i; });
        var go = el("button", "my-go", T("Let me investigate", "بگذار بررسی کنم")); go.type = "button"; go.disabled = true;
        go.onclick = investigate; panel.appendChild(go);
      }

      // 2. investigate: tap things in the scene (or the list below); each one gives a clue
      function investigate() {
        panel.innerHTML = "";
        var left = r.limit;
        var info = el("p", "my-left"), cards = el("div", "my-clues"), list = el("div", "my-list");
        function upd() { info.textContent = left ? T("You can look at " + left + " more " + (left === 1 ? "thing" : "things") + ". Tap what is lit up.", "هنوز می‌توانی " + N(left) + " چیز دیگر را ببینی. روی چیزهای روشن بزن.") : T("You have looked at everything you can.", "همهٔ چیزی را که می‌شد دید، دیدی."); }
        panel.appendChild(el("p", "my-intro", r.intro));
        panel.appendChild(info); panel.appendChild(cards); panel.appendChild(list);
        var done = el("button", "my-go", T("I'm ready to decide", "آماده‌ام تصمیم بگیرم")); done.type = "button"; done.disabled = true;
        done.onclick = reconsider; panel.appendChild(done);
        if (r.given) { var g0 = el("div", "my-clue given"); g0.appendChild(el("b", "", T("You already know", "از قبل می‌دانی"))); g0.appendChild(el("span", "", r.given)); cards.appendChild(g0); }
        var hot = {};
        function look(src) {
          if (S.seen.indexOf(src.id) >= 0 || !left) return;
          S.seen.push(src.id); left--; hot[src.id].forEach(function (b) { b.classList.remove("avail"); b.classList.add("done"); b.disabled = true; });
          var c = el("div", "my-clue " + (src.kind || "weak"));
          c.appendChild(el("b", "", src.label)); c.appendChild(el("span", "", src.clue));
          cards.appendChild(c); say(src.clue);
          if (!left) { list.querySelectorAll("button:not(.done)").forEach(function (b) { b.disabled = true; }); Object.keys(hot).forEach(function (k) { hot[k].forEach(function (b) { if (!b.classList.contains("done")) { b.classList.remove("avail"); b.disabled = true; } }); }); }
          done.disabled = false; upd();
        }
        r.sources.forEach(function (src) {
          hot[src.id] = [];
          var b = el("button", "my-src avail", src.label); b.type = "button"; b.onclick = function () { look(src); };
          list.appendChild(b); hot[src.id].push(b);
          var node = sc.stage && sc.stage.node(src.target);
          if (node) {
            var h = el("button", "my-hot avail"); h.type = "button"; h.setAttribute("aria-label", src.label); h.title = src.label;
            h.onclick = function () { look(src); }; node.appendChild(h); hot[src.id].push(h);
          }
        });
        upd();
      }

      // 3. reconsider
      function reconsider() {
        sc.el.querySelectorAll(".my-hot").forEach(function (h) { h.remove(); });
        panel.innerHTML = "";
        S.final = S.first; S.finalConf = S.firstConf;
        panel.appendChild(el("p", "my-q", T("Has your mind changed?", "نظرت عوض شده؟")));
        chips(panel, r.hyps, S.final, function (id) { S.final = id; });
        panel.appendChild(el("p", "my-q2", T("How sure are you now?", "حالا چقدر مطمئنی؟")));
        confRow(panel, S.finalConf, function (i) { S.finalConf = i; });
        if (r.changers && r.changers.length) {
          panel.appendChild(el("p", "my-q2", T("What would change your mind?", "چه چیزی نظرت را عوض می‌کند؟")));
          chips(panel, r.changers.map(function (c) { return { id: c.id, text: c.text }; }), null, function (id) { S.changer = id; });
        }
        var go = el("button", "my-go", T("Show me", "نشانم بده")); go.type = "button"; go.onclick = result; panel.appendChild(go);
      }

      // 4. the result: how it moved, what the clues could and could not show
      function result() {
        var rule = r.rules.filter(function (x) { return x.if.every(function (id) { return S.seen.indexOf(id) >= 0; }); })[0] || r.rules[r.rules.length - 1];
        var text = function (id) { return r.hyps.filter(function (h) { return h.id === id; })[0].text; };
        var same = S.final === rule.best, cn = CONF();
        var ok = same && S.finalConf === rule.conf, over = same && S.finalConf > rule.conf, under = same && S.finalConf < rule.conf;
        panel.innerHTML = "";
        var moved = el("div", "my-moved");
        moved.appendChild(el("b", "", T("How your answer moved", "جوابت چطور تغییر کرد")));
        moved.appendChild(el("span", "", T("Before: ", "پیش از این: ") + text(S.first) + " (" + cn[S.firstConf] + ")"));
        moved.appendChild(el("span", "", T("Now: ", "حالا: ") + text(S.final) + " (" + cn[S.finalConf] + ")"));
        panel.appendChild(moved);
        var v = el("div", "my-verdict " + (ok || under ? "good" : "catch"));
        var title = ok ? T("Well reasoned!", "خوب استدلال کردی!") : over ? T("Right answer, but your clues only allow “" + cn[rule.conf] + "”.", "جواب درست است، ولی سرنخ‌هایت فقط «" + cn[rule.conf] + "» را می‌پذیرند.")
          : under ? T("Right answer! Your clues were strong enough to be surer.", "جواب درست است! سرنخ‌هایت برای مطمئن‌تر بودن به‌اندازهٔ کافی قوی بودند.")
          : T("Not quite. Here is what your clues show.", "نه دقیقاً. ببین سرنخ‌هایت چه نشان می‌دهند.");
        v.appendChild(el("b", "", title));
        v.appendChild(el("span", "", text(rule.best) + " (" + cn[rule.conf] + "): " + rule.why));
        if (same && S.final === S.first && (ok || under)) v.appendChild(el("span", "my-keep", T("You kept your answer, and that was right: the clues backed it.", "جوابت را نگه داشتی و درست بود: سرنخ‌ها پشتش بودند.")));
        panel.appendChild(v);
        var tr = el("div", "my-tricks");
        tr.appendChild(el("b", "", T("What each clue can and cannot show", "هر سرنخ چه چیزی را می‌تواند نشان بدهد و چه چیزی را نه")));
        r.sources.forEach(function (src) {
          var seen = S.seen.indexOf(src.id) >= 0;
          var d = el("p", "my-trick" + (seen ? "" : " unseen"));
          d.appendChild(el("i", "", (seen ? "✓ " : "○ ") + src.label + ": "));
          d.appendChild(document.createTextNode((seen ? "" : T("(not checked) ", "(نگاه نکردی) ")) + (src.clue ? src.clue + " " : "") + (src.tricky || "")));
          tr.appendChild(d);
        });
        panel.appendChild(tr);
        // badges: useful reasoning only
        var strong = S.seen.some(function (id) { return r.sources.filter(function (x) { return x.id === id; })[0].kind === "strong"; });
        var other = S.seen.some(function (id) { var s = r.sources.filter(function (x) { return x.id === id; })[0]; return Object.keys(s.pts || {}).some(function (h) { return h !== S.first && s.pts[h] > 0; }); }) || (S.changer && (r.changers || []).some(function (c) { return c.id === S.changer && c.good; }));
        var bs = [];
        if (strong) { bs.push(T("Checked a strong clue", "سرنخِ قوی را وارسی کردی")); badges.check = 1; }
        if (other) { bs.push(T("Looked for another explanation", "دنبالِ توضیحِ دیگری گشتی")); badges.alt = 1; }
        if (ok) { bs.push(T("Right amount of sure", "به اندازهٔ درست مطمئن بودی")); badges.cal = 1; }
        if (bs.length) { var bl = el("p", "my-badges"); bs.forEach(function (t) { bl.appendChild(el("span", "my-badge", "★ " + t)); }); panel.appendChild(bl); }
        var last = ri === rounds.length - 1;
        var nx = el("button", "my-go", last ? T("Finish", "تمام") : T("Next case", "پروندهٔ بعدی")); nx.type = "button";
        nx.onclick = function () { if (last) finish(); else { ri++; round(); box.scrollIntoView({ block: "start" }); } };
        panel.appendChild(nx); nx.focus({ preventScroll: true });
      }
      ask1();
    }
    function finish() {
      root.innerHTML = "";
      var d = el("div", "my-done");
      d.appendChild(el("span", "kg-star", "★"));
      d.appendChild(el("p", "", data.done || T("You investigated like a detective!", "مثلِ کارآگاه بررسی کردی!")));
      var got = [];
      if (badges.check) got.push(T("Checked a strong clue", "سرنخِ قوی را وارسی کردی"));
      if (badges.alt) got.push(T("Looked for another explanation", "دنبالِ توضیحِ دیگری گشتی"));
      if (badges.cal) got.push(T("Right amount of sure", "به اندازهٔ درست مطمئن بودی"));
      if (got.length) { var bl = el("p", "my-badges"); got.forEach(function (t) { bl.appendChild(el("span", "my-badge", "★ " + t)); }); d.appendChild(bl); }
      if (data.offline) d.appendChild(el("p", "my-offline", data.offline));
      root.appendChild(d);
      G.star(box); G.say(T("Mission complete! You earned a star.", "مأموریت تمام شد! یک ستاره گرفتی."));
    }
    round();
  });
})();
