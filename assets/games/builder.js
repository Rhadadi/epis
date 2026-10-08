/* Build a mystery: a child sets a case for a parent or friend on the same device. Pick the culprit in secret, choose which
   clues to give (some point to a suspect, some rule one out, some do not help, and a red herring points the wrong way), pass
   the device, and the detective says who and how sure they are. Both sides get feedback on the reasoning: the builder on how
   fair the clues were, the detective on whether their confidence matched what the clues showed.
   data: {engine: "builder", title, intro, culprit_q, suspects: [{id, who, name}], clues: [{id, text, kind: "supports"|"rules_out"|"neutral", about}],
          take: {explorers: 2, investigators: 3}, bg}                                                                              */
(function () {
  "use strict";
  var G = window.Games, T = G.T, el = G.el, N = G.N;

  G.register("builder", function (box, data) {
    var level = box.getAttribute("data-level"), take = (data.take || {})[level] || 3;
    var root = el("div", "bd"); box.appendChild(root);
    var S = { culprit: null, picked: [], guess: null, conf: 1 };
    var byId = {}; data.suspects.forEach(function (s) { byId[s.id] = s; });
    var CONF = [T("Just a guess", "فقط حدس"), T("Pretty sure", "نسبتاً مطمئن"), T("Very sure", "خیلی مطمئن")];

    function stage(extra) {
      var st = el("div", "dstage my-stage"); st.setAttribute("aria-hidden", "true");
      var Sg = window.Scenes && window.Scenes.Stage;
      if (Sg) {
        var n = data.suspects.length, actors = data.suspects.map(function (s, i) { return { id: s.id, who: s.who, x: 18 + i * (64 / Math.max(1, n - 1)), y: 92, s: .95, face: "happy", anim: "bob" }; });
        Sg(st).set({ bg: data.bg || "field", actors: actors, props: extra || [] }, true);
      }
      return st;
    }
    function chips(parent, items, cur, onpick) {
      var row = el("div", "my-chips");
      var btns = items.map(function (it) {
        var b = el("button", "my-chip", it.text); b.type = "button"; b.setAttribute("aria-pressed", cur === it.id ? "true" : "false");
        b.onclick = function () { onpick(it.id); btns.forEach(function (x, j) { x.setAttribute("aria-pressed", items[j].id === it.id ? "true" : "false"); }); };
        row.appendChild(b); return b;
      });
      parent.appendChild(row); return row;
    }
    function tag(c) {
      if (c.kind === "neutral") return T("does not help", "کمکی نمی‌کند");
      return (c.kind === "supports" ? T("points to ", "اشاره می‌کند به ") : T("rules out ", "کنار می‌گذارد ")) + byId[c.about].name;
    }
    // what the clues show: supports +2, rules out -3 for that suspect; the best suspect, how far ahead, how sure that justifies
    function reading(ids) {
      var sc = {}; data.suspects.forEach(function (s) { sc[s.id] = 0; });
      ids.forEach(function (id) { var c = data.clues.filter(function (x) { return x.id === id; })[0]; if (c.kind === "supports") sc[c.about] += 2; if (c.kind === "rules_out") sc[c.about] -= 3; });
      var order = data.suspects.map(function (s) { return s.id; }).sort(function (a, b) { return sc[b] - sc[a]; });
      var margin = sc[order[0]] - sc[order[1]];
      return { best: margin >= 2 ? order[0] : "unsure", conf: margin >= 4 ? 2 : margin >= 2 ? 1 : 0, scores: sc, margin: margin };
    }

    function pickCulprit() {
      root.innerHTML = "";
      root.appendChild(el("p", "my-count", T("Step 1 of 3 · You are the mystery maker", "گام ۱ از ۳ · تو سازندهٔ معما هستی")));
      root.appendChild(stage());
      var panel = el("div", "my-panel"); root.appendChild(panel);
      panel.appendChild(el("p", "my-intro", data.intro));
      panel.appendChild(el("p", "my-q", data.culprit_q));
      var go = el("button", "my-go", T("Next: choose the clues", "بعدی: سرنخ‌ها را انتخاب کن")); go.type = "button"; go.disabled = true;
      chips(panel, data.suspects.map(function (s) { return { id: s.id, text: s.name }; }), S.culprit, function (id) { S.culprit = id; go.disabled = false; });
      go.onclick = pickClues; panel.appendChild(go);
      panel.appendChild(el("p", "my-left", T("Keep it secret! Only you should see this screen.", "مخفی نگهش دار! فقط خودت باید این صفحه را ببینی.")));
    }
    function pickClues() {
      root.innerHTML = "";
      S.picked = [];
      root.appendChild(el("p", "my-count", T("Step 2 of 3 · Choose " + take + " clues", "گام ۲ از ۳ · " + N(take) + " سرنخ انتخاب کن")));
      var panel = el("div", "my-panel bd-clues"); root.appendChild(panel);
      panel.appendChild(el("p", "my-intro", T("The culprit is " + byId[S.culprit].name + ". Give your detective clues. A fair mystery can be solved, but not too easily.", "گناهکار " + byId[S.culprit].name + " است. به کارآگاهت سرنخ بده. معمای منصفانه حل می‌شود، ولی نه خیلی راحت.")));
      var left = el("p", "my-left"), list = el("div", "bd-list"), go = el("button", "my-go", T("Pass the device to your detective", "دستگاه را به کارآگاهت بده")); go.type = "button"; go.disabled = true;
      function upd() { left.textContent = T("Chosen: " + S.picked.length + " of " + take, "انتخاب‌شده: " + N(S.picked.length) + " از " + N(take)); go.disabled = S.picked.length !== take; }
      data.clues.forEach(function (c) {
        var b = el("button", "bd-clue"); b.type = "button"; b.setAttribute("aria-pressed", "false");
        b.appendChild(el("b", "", c.text)); b.appendChild(el("small", "", tag(c)));
        b.onclick = function () {
          var i = S.picked.indexOf(c.id);
          if (i >= 0) { S.picked.splice(i, 1); b.setAttribute("aria-pressed", "false"); }
          else if (S.picked.length < take) { S.picked.push(c.id); b.setAttribute("aria-pressed", "true"); }
          upd();
        };
        list.appendChild(b);
      });
      panel.appendChild(left); panel.appendChild(list); panel.appendChild(go); upd();
      go.onclick = handOver;
    }
    function handOver() {
      root.innerHTML = "";
      var panel = el("div", "my-panel"); root.appendChild(panel);
      panel.appendChild(el("p", "my-intro", T("Pass the device now. The detective plays next!", "حالا دستگاه را بده. نوبتِ کارآگاه است!")));
      var go = el("button", "my-go", T("I am the detective", "من کارآگاهم")); go.type = "button"; go.onclick = detective; panel.appendChild(go);
    }
    function detective() {
      root.innerHTML = "";
      root.appendChild(el("p", "my-count", T("Step 3 of 3 · You are the detective", "گام ۳ از ۳ · تو کارآگاهی")));
      root.appendChild(stage([{ id: "q", what: "question", x: 50, y: 60, s: .8, anim: "float" }]));
      var panel = el("div", "my-panel"); root.appendChild(panel);
      panel.appendChild(el("p", "my-intro", T("Someone took the cookie! Read the clues.", "یک نفر کلوچه را برداشته! سرنخ‌ها را بخوان.")));
      var cards = el("div", "my-clues"); S.picked.forEach(function (id) { var c = data.clues.filter(function (x) { return x.id === id; })[0]; var d = el("div", "my-clue"); d.appendChild(el("span", "", c.text)); cards.appendChild(d); });
      panel.appendChild(cards);
      panel.appendChild(el("p", "my-q", T("Who did it?", "چه کسی این کار را کرد؟")));
      var opts = data.suspects.map(function (s) { return { id: s.id, text: s.name }; }).concat([{ id: "unsure", text: T("Not enough evidence yet", "هنوز نشانهٔ کافی نیست"), unsure: true }]);
      var go = el("button", "my-go", T("Show me", "نشانم بده")); go.type = "button"; go.disabled = true;
      chips(panel, opts, S.guess, function (id) { S.guess = id; go.disabled = false; });
      panel.appendChild(el("p", "my-q2", T("How sure are you?", "چقدر مطمئنی؟")));
      chips(panel, CONF.map(function (t, i) { return { id: i, text: t }; }), S.conf, function (i) { S.conf = i; });
      go.onclick = reveal; panel.appendChild(go);
    }
    function reveal() {
      var r = reading(S.picked), calibrated = S.guess === r.best && S.conf === r.conf, right = S.guess === S.culprit;
      root.innerHTML = "";
      var panel = el("div", "my-panel"); root.appendChild(panel);
      var truth = el("div", "my-verdict " + (right ? "good" : "catch"));
      truth.appendChild(el("b", "", T("The culprit was ", "گناهکار ") + byId[S.culprit].name + (T("", " بود")) + "!"));
      truth.appendChild(el("span", "", right ? T("The detective got it.", "کارآگاه درست گفت.") : S.guess === "unsure" ? T("The detective said “not enough evidence yet”.", "کارآگاه گفت «هنوز نشانهٔ کافی نیست».") : T("The detective guessed " + byId[S.guess].name + ".", "کارآگاه " + byId[S.guess].name + " را گفت.")));
      panel.appendChild(truth);
      var det = el("div", "my-verdict " + (calibrated ? "good" : "catch"));
      det.appendChild(el("b", "", T("For the detective", "برای کارآگاه")));
      var best = r.best === "unsure" ? T("The clues were not enough to name anyone. “Not enough evidence yet” was the best answer.", "سرنخ‌ها برای نام‌بردنِ کسی کافی نبود. «هنوز نشانهٔ کافی نیست» بهترین جواب بود.") : T("The clues pointed to " + byId[r.best].name + " (" + CONF[r.conf] + ").", "سرنخ‌ها به " + byId[r.best].name + " اشاره می‌کردند (" + CONF[r.conf] + ").");
      det.appendChild(el("span", "", (calibrated ? T("Well reasoned! ", "خوب استدلال کردی! ") : T("Look at what the clues really showed. ", "ببین سرنخ‌ها واقعاً چه نشان می‌دادند. ")) + best));
      panel.appendChild(det);
      var bl = el("div", "my-verdict " + (r.best === S.culprit ? "good" : "catch"));
      bl.appendChild(el("b", "", T("For the mystery maker", "برای سازندهٔ معما")));
      var mis = S.picked.some(function (id) { var c = data.clues.filter(function (x) { return x.id === id; })[0]; return (c.kind === "supports" && c.about !== S.culprit) || (c.kind === "rules_out" && c.about === S.culprit); });
      var msg = r.best === S.culprit ? T("Fair! Your clues really did point to the culprit." + (mis ? " And your tricky clue made it a real puzzle." : ""), "منصفانه! سرنخ‌هایت واقعاً به گناهکار اشاره می‌کردند." + (mis ? " و سرنخِ فریبنده‌ات آن را معمای واقعی کرد." : ""))
        : r.best === "unsure" ? T("Your clues did not tell the suspects apart. Next time add a clue that points to the culprit or rules out an innocent one.", "سرنخ‌هایت مظنون‌ها را از هم جدا نمی‌کرد. دفعهٔ بعد سرنخی بگذار که به گناهکار اشاره کند یا بی‌گناهی را کنار بگذارد.")
        : T("Your clues pointed to the wrong suspect. A misleading clue can be fun, but a fair mystery needs at least one clue that points to the real culprit.", "سرنخ‌هایت به مظنونِ اشتباه اشاره می‌کرد. سرنخِ فریبنده می‌تواند سرگرم‌کننده باشد، ولی معمای منصفانه دست‌کم یک سرنخ دربارهٔ گناهکارِ واقعی لازم دارد.");
      bl.appendChild(el("span", "", msg)); panel.appendChild(bl);
      var bd = el("p", "my-badges"); var any = false;
      if (r.best === S.culprit && r.margin >= 2) { bd.appendChild(el("span", "my-badge", "★ " + T("Built a fair mystery", "معمای منصفانه ساختی"))); any = true; G.star(box); }
      if (r.best === S.culprit && mis) { bd.appendChild(el("span", "my-badge", "★ " + T("Added a fair red herring", "فریبِ منصفانه اضافه کردی"))); any = true; }
      if (calibrated) { bd.appendChild(el("span", "my-badge", "★ " + T("Right amount of sure", "به اندازهٔ درست مطمئن بودی"))); any = true; }
      if (any) panel.appendChild(bd);
      var again = el("button", "my-go", T("Swap roles and build another", "جابه‌جا شوید و یکی دیگر بسازید")); again.type = "button";
      again.onclick = function () { S = { culprit: null, picked: [], guess: null, conf: 1 }; pickCulprit(); }; panel.appendChild(again);
      G.say(truth.textContent);
    }
    pickCulprit();
  });
})();
