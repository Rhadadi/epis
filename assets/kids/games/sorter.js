/* Sorter: one card at a time; tap the bucket it belongs in; every answer is explained. A star for finishing. */
(function () {
  "use strict";
  Games.register("sorter", function (box, data, K) {
    var T = K.T, N = K.N, el = K.el;
    var cards, i, right;
    function start() { cards = K.shuffle(data.cards); i = 0; right = 0; show(); }
    function show() {
      box.querySelectorAll(".kg").forEach(function (n) { n.remove(); });
      var wrap = el("div", "kg");
      if (i >= cards.length) return done(wrap);
      var c = cards[i];
      var prog = el("div", "kg-progress");
      prog.appendChild(el("span", "", T("Card ", "کارتِ ") + N(i + 1) + T(" of ", " از ") + N(cards.length)));
      prog.appendChild(el("span", "", "✓ " + N(right)));
      wrap.appendChild(prog);
      var card = el("p", "kg-card", c.text);
      wrap.appendChild(card);
      var bins = el("div", "kg-bins");
      bins.setAttribute("role", "group");
      bins.setAttribute("aria-label", T("Choose where it goes", "انتخاب کن کجا می‌رود"));
      var fb = el("div", "kg-feedback"); fb.hidden = true; fb.setAttribute("aria-live", "polite");
      data.buckets.forEach(function (b) {
        var btn = el("button", "kg-bin"); btn.type = "button";
        btn.appendChild(el("b", "", b.label));
        if (b.hint) btn.appendChild(el("small", "", b.hint));
        btn.onclick = function () {
          var ok = b.id === c.bucket;
          if (ok) right++;
          bins.querySelectorAll("button").forEach(function (x) { x.disabled = true; });
          btn.classList.add(ok ? "right" : "wrong");
          var correct = data.buckets.filter(function (x) { return x.id === c.bucket; })[0];
          fb.hidden = false; fb.className = "kg-feedback " + (ok ? "yes" : "no"); fb.innerHTML = "";
          fb.appendChild(el("b", "", ok ? T("Yes!", "آفرین!") : T("Not quite. It fits “", "نه دقیقاً. جایش در «") + correct.label + T("” better.", "» است.")));
          fb.appendChild(el("span", "", c.why || ""));
          var next = el("button", "kg-next", i + 1 < cards.length ? T("Next card", "کارتِ بعدی") : T("Finish", "تمام"));
          next.type = "button"; next.onclick = function () { i++; show(); };
          fb.appendChild(el("br")); fb.appendChild(next);
          next.focus();
        };
        bins.appendChild(btn);
      });
      wrap.appendChild(bins); wrap.appendChild(fb);
      box.appendChild(wrap);
    }
    function done(wrap) {
      var d = el("div", "kg-done");
      d.appendChild(el("span", "kg-star", "★"));
      d.appendChild(el("p", "", T("You got ", "") + N(right) + T(" of ", " از ") + N(cards.length) + T(" right.", " را درست گفتی.")));
      if (data.done) d.appendChild(el("p", "", data.done));
      var again = el("button", "kg-next", T("Play again", "دوباره بازی کن")); again.type = "button"; again.onclick = start;
      d.appendChild(again);
      wrap.appendChild(d); box.appendChild(wrap);
      K.star(box); K.say(T("Finished! You earned a star.", "تمام شد! یک ستاره گرفتی."));
    }
    start();
  });
})();
