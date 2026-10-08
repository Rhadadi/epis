/* Scene decks: one idea per screen. A deck is a row of scenes (a stage with drawn characters and things, one or two
   sentences, sometimes a question or a game). Characters that appear in two scenes in a row glide to their new place,
   leave when they are no longer needed and pop in when they arrive. The server writes every scene as a plain list
   (so nothing is lost without JavaScript) and a JSON description; this file turns them into the stage.

   <section data-deck data-unit data-level data-game="deck">
     <ol class="dlist"><li data-scene="s1"> … (text, picture, game box) </li> …</ol>
     <script type="application/json" class="dscript">{ audio: {src}, ui: {…}, scenes: [ {id, bg, pic, actors, props, label, text | lines, audio:[b,e], ask, game, end, anchor} ] }</script>
   </section>
   Actor: {id, who, x, y, s, face, anim, say, flip}  (x, y in % of the stage; y is where the feet are)
   Prop:  {id, what, x, y, s, anim}                  (y is the bottom edge)                                              */
(function () {
  "use strict";
  var G = window.Games, P = window.Puppets;
  var T = G.T, N = G.N, el = G.el;
  var FA = G.FA;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function rich(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>"); }

  function Deck(root) {
    var data;
    try { data = JSON.parse(root.querySelector("script.dscript").textContent); } catch (e) { return; }
    var scenes = data.scenes, n = scenes.length, cur = -1, ui = data.ui || {};
    var list = root.querySelector(".dlist");
    var boxes = {};  // game boxes the server rendered inside the list, by scene id
    Array.prototype.forEach.call(list.querySelectorAll("li[data-scene]"), function (li) {
      var box = li.querySelector(".kgame"); if (box) { boxes[li.getAttribute("data-scene")] = box; box.setAttribute("data-scene-id", li.getAttribute("data-scene")); }
    });
    root.classList.add("live");
    list.hidden = true;

    var wrap = el("div", "dwrap");
    var stage = el("div", "dstage"); stage.setAttribute("aria-hidden", "true");
    var bgLayer = el("div", "dbg"), picLayer = el("div", "dpic"), items = el("div", "ditems");
    stage.appendChild(bgLayer); stage.appendChild(picLayer); stage.appendChild(items);
    var label = el("p", "dlabel");
    var listen = el("button", "dlisten"); listen.type = "button"; listen.hidden = true;
    var scene = el("div", "dscene"); scene.setAttribute("tabindex", "-1");
    var text = el("div", "dtext"); text.setAttribute("aria-live", "polite");
    var ask = el("div", "dask");
    var gameSlot = el("div", "dgame");
    scene.appendChild(text); scene.appendChild(ask); scene.appendChild(gameSlot);
    var nav = el("nav", "dnav"); nav.setAttribute("aria-label", ui.nav || T("Scenes", "صحنه‌ها"));
    var back = el("button", "dbtn dback", ui.back || T("Back", "قبلی")); back.type = "button";
    var dots = el("div", "ddots"); dots.setAttribute("role", "tablist");
    var next = el("button", "dbtn dnext", ui.next || T("Next", "بعدی")); next.type = "button";
    nav.appendChild(back); nav.appendChild(dots); nav.appendChild(next);
    wrap.appendChild(stage); wrap.appendChild(label); wrap.appendChild(listen); wrap.appendChild(scene); wrap.appendChild(nav);
    root.appendChild(wrap);

    var dotEls = scenes.map(function (s, i) {
      var d = el("button", "ddot"); d.type = "button";
      d.setAttribute("aria-label", (ui.scene || T("Scene", "صحنه")) + " " + N(i + 1) + " / " + N(n));
      d.onclick = function () { go(i); };
      dots.appendChild(d); return d;
    });

    // ---- the stage: actors and props keep their element between scenes, so they can glide
    var live = {};  // id → element
    function place(node, o, kind) {
      node.style.left = o.x + "%"; node.style.top = (o.y == null ? 100 : o.y) + "%";
      node.style.width = "calc(var(--" + (kind === "actor" ? "aw" : "pw") + ") * " + (o.s || 1) + ")";
      node.classList.toggle("flip", !!o.flip);
    }
    function setAnim(node, a) {
      var inner = node.firstChild; inner.className = "act-in" + (a && a !== "none" ? " a-" + a : "");
    }
    function setFace(node, f) {
      node.className = node.className.replace(/\bf-\w+/g, "").trim() + " f-" + (f || "happy");
    }
    function setSay(node, say, o) {
      var b = node.querySelector(".bub");
      if (!say) { if (b) b.remove(); return; }
      if (!b) { b = el("div", "bub"); node.appendChild(b); }
      b.textContent = say;
      b.className = "bub" + (o.x < 24 ? " bub-l" : o.x > 76 ? " bub-r" : "") + (o.say_think ? " think" : "");
    }
    function buildStage(sc, instant) {
      var want = {};
      (sc.actors || []).forEach(function (a) { want[a.id] = a; });
      (sc.props || []).forEach(function (p) { want[p.id] = p; });
      Object.keys(live).forEach(function (id) {
        if (!want[id]) { var gone = live[id]; delete live[id]; gone.classList.add("out"); setTimeout(function () { gone.remove(); }, 450); }
      });
      var z = 0;
      (sc.props || []).concat(sc.actors || []).forEach(function (o) {
        var isActor = !!o.who, node = live[o.id];
        if (!node) {
          node = el("div", isActor ? "act" : "prp");
          var inner = el("div", "act-in"); inner.innerHTML = isActor ? P.actor(o.who) : P.prop(o.what);
          node.appendChild(inner); items.appendChild(node); live[o.id] = node;
          place(node, o, isActor ? "actor" : "prop");
          if (!instant) { node.classList.add("in"); setTimeout(function () { node.classList.remove("in"); }, 700); }
        } else {
          place(node, o, isActor ? "actor" : "prop");
        }
        node.style.zIndex = o.z != null ? o.z : (isActor ? 20 + Math.round(o.y || 0) : 10 + z);
        z++;
        setAnim(node, o.anim);
        if (isActor) { setFace(node, o.face); setSay(node, o.say, o); }
      });
    }
    var curBg = null;
    function setBg(name) {
      name = name || "plain";
      if (name === curBg) return;
      curBg = name;
      var layer = el("div", "dbgi"); layer.innerHTML = P.bg(name);
      bgLayer.appendChild(layer);
      requestAnimationFrame(function () { layer.classList.add("on"); });
      setTimeout(function () { while (bgLayer.children.length > 1) bgLayer.removeChild(bgLayer.firstChild); }, 700);
    }
    function setPic(pic) {
      picLayer.innerHTML = "";
      stage.classList.toggle("haspic", !!pic);
      if (!pic) return;
      var im = el("img"); im.src = pic.src; if (pic.srcset) { im.srcset = pic.srcset; im.sizes = "(max-width: 900px) 100vw, 860px"; }
      im.alt = ""; im.decoding = "async";
      picLayer.appendChild(im);
      requestAnimationFrame(function () { im.classList.add("on"); });
      stage.setAttribute("aria-label", pic.alt || "");
    }

    // ---- narration: each scene may play its own stretch of one audio file, lighting the words as they are read
    var audio = null, rafId = 0, segEnd = 0, words = [], wb = [];
    function stopAudio() { if (audio) audio.pause(); cancelAnimationFrame(rafId); listen.setAttribute("aria-pressed", "false"); setListenText(false); }
    function setListenText(on) { listen.textContent = on ? (ui.pause || T("Pause", "مکث")) : (ui.listen || T("Listen", "گوش کن")); }
    function tick() {
      var t = audio.currentTime, cw = -1;
      for (var i = 0; i < wb.length; i++) { if (wb[i][0] <= t && t <= wb[i][1] + .25) { cw = i; } }
      words.forEach(function (w, i) { w.classList.toggle("now", i === cw); });
      if (t >= segEnd - .05) { audio.pause(); listen.setAttribute("aria-pressed", "false"); setListenText(false); words.forEach(function (w) { w.classList.remove("now"); }); return; }
      if (!audio.paused) rafId = requestAnimationFrame(tick);
    }
    listen.onclick = function () {
      var sc = scenes[cur]; if (!sc.audio) return;
      if (!audio) { audio = new Audio(data.audio.src); audio.preload = "none"; audio.addEventListener("play", function () { cancelAnimationFrame(rafId); rafId = requestAnimationFrame(tick); }); }
      if (!audio.paused) { stopAudio(); return; }
      segEnd = sc.audio[1];
      if (audio.currentTime < sc.audio[0] - .2 || audio.currentTime > sc.audio[1]) audio.currentTime = sc.audio[0];
      audio.play(); listen.setAttribute("aria-pressed", "true"); setListenText(true);
    };

    // ---- text, question, game, end
    function showText(sc) {
      text.innerHTML = ""; words = []; wb = [];
      if (sc.lines) {
        sc.lines.forEach(function (ln) {
          var p = el("p", "line r-" + (ln.role || "narrator"));
          if (ln.who) p.appendChild(el("b", "who", ln.who));
          (ln.w || []).forEach(function (w, i) {
            var s = el("span", "w", w[0]); p.appendChild(s); if (i < ln.w.length - 1) p.appendChild(document.createTextNode(" "));
            words.push(s); wb.push([w[1], w[2]]);
          });
          if (!ln.w) p.appendChild(document.createTextNode(ln.t));
          text.appendChild(p);
        });
      } else if (sc.text) {
        (Array.isArray(sc.text) ? sc.text : [sc.text]).forEach(function (t) { var p = el("p"); p.innerHTML = rich(t); text.appendChild(p); });
      }
      if (sc.list) {
        var ul = el("ul", "dl");
        sc.list.forEach(function (t) { var li = el("li"); li.innerHTML = rich(t); ul.appendChild(li); });
        text.appendChild(ul);
      }
      if (sc.cards) {
        var grid = el("div", "dcards");
        sc.cards.forEach(function (c) {
          var d = el("div", "dcard" + (c.img ? " has-img" : ""));
          if (c.img) { var im = el("img"); im.src = c.img; im.alt = ""; im.decoding = "async"; im.loading = "lazy"; d.appendChild(im); }
          var b = el("b", "", c.word); d.appendChild(b); var q = el("span"); q.innerHTML = rich(c.def); d.appendChild(q);
          if (c.eg) { var e = el("i", "", c.eg); d.appendChild(e); }
          grid.appendChild(d);
        });
        text.appendChild(grid);
      }
      if (sc.links) {
        var nl = el("ul", "dl dlinks");
        sc.links.forEach(function (l) { var li = el("li"), a = el("a", "", l.t); a.href = l.href; li.appendChild(a); nl.appendChild(li); });
        text.appendChild(nl);
      }
    }
    function showAsk(sc) {
      ask.innerHTML = "";
      if (!sc.ask) return;
      if (sc.ask.q) ask.appendChild(el("p", "dq", sc.ask.q));
      var opts = el("div", "dopts"); opts.setAttribute("role", "group");
      var fb = el("div", "dwhy"); fb.hidden = true; fb.setAttribute("aria-live", "polite");
      sc.ask.options.forEach(function (o) {
        var b = el("button", "cs-choice dopt"); b.type = "button"; b.textContent = o.t;
        b.onclick = function () {
          opts.querySelectorAll("button").forEach(function (x) { x.disabled = true; });
          b.classList.add(o.ok ? "right" : "wrong");
          if (!o.ok) { var good = opts.querySelector("[data-ok]"); if (good) good.classList.add("right"); }
          fb.hidden = false; fb.className = "dwhy " + (o.ok ? "yes" : "no");
          fb.innerHTML = "<b>" + esc(o.ok ? (ui.yes || T("Yes!", "آفرین!")) : (ui.notquite || T("Not quite.", "نه دقیقاً."))) + "</b> " + rich(o.why || "");
          if (o.face && sc.ask.who && live[sc.ask.who]) setFace(live[sc.ask.who], o.face);
          next.classList.add("pulse");
        };
        if (o.ok) b.setAttribute("data-ok", "1");
        opts.appendChild(b);
      });
      ask.appendChild(opts); ask.appendChild(fb);
    }
    function showGame(sc) {
      // park the previous game's box back in the (hidden) list, so it stays on the page and can be counted
      Array.prototype.forEach.call(gameSlot.querySelectorAll(".kgame"), function (bx) {
        var li = list.querySelector('li[data-scene="' + bx.getAttribute("data-scene-id") + '"]'); if (li) li.appendChild(bx); else bx.remove();
      });
      gameSlot.innerHTML = "";
      if (!sc.game) return;
      var box = boxes[sc.id];
      if (!box) return;
      gameSlot.appendChild(box);
      if (!box.getAttribute("data-mounted")) { box.setAttribute("data-mounted", "1"); G.mount(box); }
    }
    function confetti() {
      if (G.reduced()) return;
      var colors = ["#FF4F8B", "#FFC92E", "#2F86FF", "#1FB57A", "#8B5CF6", "#FF7A2F"], layer = el("div", "cs-confetti");
      layer.setAttribute("aria-hidden", "true");
      for (var i = 0; i < 46; i++) {
        var bit = el("i");
        bit.style.left = (Math.random() * 100) + "%"; bit.style.background = colors[i % colors.length];
        bit.style.animationDelay = (Math.random() * .35) + "s"; bit.style.animationDuration = (1.1 + Math.random() * .9) + "s";
        bit.style.setProperty("--x", (Math.random() * 160 - 80) + "px"); bit.style.setProperty("--r", (Math.random() * 720 - 360) + "deg");
        layer.appendChild(bit);
      }
      stage.appendChild(layer); setTimeout(function () { layer.remove(); }, 2600);
    }

    // ---- moving about
    function go(i, opts) {
      opts = opts || {};
      i = Math.max(0, Math.min(n - 1, i));
      if (i === cur) return;
      var first = cur < 0;
      stopAudio();
      var sc = scenes[i];
      cur = i;
      setBg(sc.bg); setPic(sc.pic); buildStage(sc, first);
      label.textContent = sc.label || ""; label.hidden = !sc.label;
      showText(sc); showAsk(sc); showGame(sc);
      listen.hidden = !sc.audio; setListenText(false);
      scene.className = "dscene" + (sc.game ? " has-game" : "") + (sc.pic ? " has-pic" : "");
      stage.hidden = !!sc.nostage; label.classList.toggle("over", false);
      dotEls.forEach(function (d, k) { d.classList.toggle("on", k === i); d.classList.toggle("done", k < i); d.setAttribute("aria-current", k === i ? "step" : "false"); });
      back.disabled = i === 0;
      next.disabled = i === n - 1 && !sc.end;
      next.classList.remove("pulse");
      next.textContent = i === n - 1 ? (ui.again || T("Start again", "دوباره از اول")) : (sc.next || ui.next || T("Next", "بعدی"));
      next.classList.toggle("last", i === n - 1);
      if (sc.end) { confetti(); root.setAttribute("data-game", "deck"); G.star(root); G.say(T("Finished! You earned a star.", "تمام شد! یک ستاره گرفتی.")); }
      if (!first && !opts.quiet) { scene.focus({ preventScroll: true }); root.scrollIntoView({ block: "start", behavior: G.reduced() ? "auto" : "smooth" }); }
      if (history.replaceState && !opts.quiet) { try { history.replaceState(null, "", "#scene-" + (i + 1)); } catch (e) { /* ignore */ } }
    }
    next.onclick = function () { if (cur === n - 1) { go(0); } else go(cur + 1); };
    back.onclick = function () { go(cur - 1); };
    var dir = FA ? -1 : 1;
    root.addEventListener("keydown", function (e) {
      if (e.target.closest && e.target.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight") { go(cur + dir); e.preventDefault(); }
      if (e.key === "ArrowLeft") { go(cur - dir); e.preventDefault(); }
    });
    var sx = null;
    wrap.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
    wrap.addEventListener("touchend", function (e) {
      if (sx === null) return;
      var dx = e.changedTouches[0].clientX - sx; sx = null;
      if (Math.abs(dx) > 70 && !(e.target.closest && e.target.closest(".dgame, .dask"))) go(cur + (dx < 0 ? dir : -dir));
    }, { passive: true });
    function fromHash() {
      var h = location.hash.replace("#", ""), m = /^scene-(\d+)$/.exec(h);
      if (m) { go(+m[1] - 1, { quiet: true }); return true; }
      for (var k = 0; k < n; k++) if (scenes[k].anchor === h) { go(k); return true; }
      return false;
    }
    window.addEventListener("hashchange", fromHash);
    if (!fromHash()) go(0, { quiet: true });
    root.deck = { go: go, count: n };
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-deck]").forEach(Deck);
  });
})();
