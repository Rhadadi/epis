/* Quick check: one question at a time; every answer, right or wrong, gets an explanation. A star for finishing. */
(function () {
  "use strict";
  Kids.register("quiz", function (box, data, K) {
    var T = K.T, N = K.N, el = K.el;
    var items = data.items, i, right;
    function start() { i = 0; right = 0; show(); }
    function show() {
      box.querySelectorAll(".kg").forEach(function (n) { n.remove(); });
      var wrap = el("div", "kg");
      if (i >= items.length) return done(wrap);
      var q = items[i];
      var prog = el("div", "kg-progress");
      prog.appendChild(el("span", "", T("Question ", "سؤالِ ") + N(i + 1) + T(" of ", " از ") + N(items.length)));
      wrap.appendChild(prog);
      wrap.appendChild(el("p", "kg-card", q.q));
      var list = el("div", "kg-choices");
      list.setAttribute("role", "group");
      var fb = el("div", "kg-feedback"); fb.hidden = true; fb.setAttribute("aria-live", "polite");
      q.choices.forEach(function (c, n) {
        var btn = el("button", "kg-choice", c); btn.type = "button";
        btn.onclick = function () {
          var ok = n === q.correct;
          if (ok) right++;
          list.querySelectorAll("button").forEach(function (x, m) { x.disabled = true; if (m === q.correct) x.classList.add("right"); });
          if (!ok) btn.classList.add("wrong");
          fb.hidden = false; fb.className = "kg-feedback " + (ok ? "yes" : "no"); fb.innerHTML = "";
          fb.appendChild(el("b", "", ok ? T("That's right!", "درست است!") : T("Not quite.", "نه دقیقاً.")));
          fb.appendChild(el("span", "", q.explain || ""));
          var next = el("button", "kg-next", i + 1 < items.length ? T("Next question", "سؤالِ بعدی") : T("Finish", "تمام"));
          next.type = "button"; next.onclick = function () { i++; show(); };
          fb.appendChild(el("br")); fb.appendChild(next);
          next.focus();
        };
        list.appendChild(btn);
      });
      wrap.appendChild(list); wrap.appendChild(fb);
      box.appendChild(wrap);
    }
    function done(wrap) {
      var d = el("div", "kg-done");
      d.appendChild(el("span", "kg-star", "★"));
      d.appendChild(el("p", "", T("You got ", "") + N(right) + T(" of ", " از ") + N(items.length) + T(" right.", " را درست جواب دادی.")));
      if (data.done) d.appendChild(el("p", "", data.done));
      var again = el("button", "kg-next", T("Try again", "دوباره امتحان کن")); again.type = "button"; again.onclick = start;
      d.appendChild(again);
      wrap.appendChild(d); box.appendChild(wrap);
      K.star(box); K.say(T("Finished! You earned a star.", "تمام شد! یک ستاره گرفتی."));
    }
    start();
  });
})();
