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

  // ---- the stage: actors and props keep their element between scenes, so they can glide.
  // Stage(el) fills a .dstage element; .set(scene, instant) arranges a scene; .face(id, mood) changes a mood.
  function Stage(stage) {
    var bgLayer = el("div", "dbg"), picLayer = el("div", "dpic"), items = el("div", "ditems");
    stage.appendChild(bgLayer); stage.appendChild(picLayer); stage.appendChild(items);
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

    return {
      set: function (sc, instant) { setBg(sc.bg); setPic(sc.pic); buildStage(sc, instant); },
      face: function (id, f) { if (live[id]) setFace(live[id], f); },
      node: function (id) { return live[id] || null; }
    };
  }

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
    var label = el("p", "dlabel");
    var listen = el("button", "dlisten"); listen.type = "button";
    // one small replay icon (no pause, no big button); it shows only on scenes that are read aloud
    var replay = el("button", "dreplay", "↻"); replay.type = "button"; replay.setAttribute("aria-label", ui.replay || T("Replay", "دوباره")); replay.title = ui.replay || T("Replay", "دوباره");
    var ctl = el("div", "dctl"); ctl.hidden = true; ctl.appendChild(replay);
    var scene = el("div", "dscene"); scene.setAttribute("tabindex", "-1");
    var text = el("div", "dtext"); text.setAttribute("aria-live", "polite");
    var ask = el("div", "dask");
    var gameSlot = el("div", "dgame");
    scene.appendChild(text); scene.appendChild(ask); scene.appendChild(gameSlot);
    var paper = document.body.classList.contains("paper"), tprog = document.getElementById("tprog"), tsound = document.getElementById("tsound");
    var ttl = el("div", "dttl"), pickBox = el("div", "dpick");
    var nav = el("nav", "dnav"); nav.setAttribute("aria-label", ui.nav || T("Scenes", "صحنه‌ها"));
    var back = el("button", "dbtn dback", ui.back || T("Back", "قبلی")); back.type = "button";
    var dots = el("div", "ddots"); dots.setAttribute("role", "tablist");
    var next = el("button", "dbtn dnext", ui.next || T("Next", "بعدی")); next.type = "button";
    var count = el("span", "dcount"), chips = null, partLabels = ui.parts || null;
    if (paper && tprog && partLabels && scenes.some(function (x) { return x.part; })) {  // a mission in parts: Story / Investigate / Try it
      chips = el("div", "dparts"); chips.setAttribute("role", "tablist");
      var seen = {};
      scenes.forEach(function (x, i) {
        if (!x.part || seen[x.part]) return;
        seen[x.part] = el("button", "dpart", partLabels[x.part] || x.part); seen[x.part].type = "button"; seen[x.part].setAttribute("data-part", x.part);
        seen[x.part].onclick = function () { go(i, { noskip: true }); };
        chips.appendChild(seen[x.part]);
      });
    }
    if (paper && tprog) { tprog.innerHTML = ""; if (chips) tprog.appendChild(chips); else tprog.appendChild(dots); tprog.appendChild(count); if (chips) tprog.classList.add("parts"); tprog.classList.toggle("many", n > 12 && !chips); root.classList.add("tbdeck"); }
    else nav.appendChild(dots);
    nav.insertBefore(back, nav.firstChild); nav.appendChild(next);
    scene.appendChild(pickBox);
    wrap.appendChild(ttl); wrap.appendChild(stage); wrap.appendChild(label); wrap.appendChild(ctl); wrap.appendChild(scene); wrap.appendChild(nav);
    root.appendChild(wrap);

    var dotEls = scenes.map(function (s, i) {
      var d = el("button", "ddot"); d.type = "button";
      d.setAttribute("aria-label", (ui.scene || T("Scene", "صحنه")) + " " + N(i + 1) + " / " + N(n));
      d.onclick = function () { go(i, { noskip: true }); };
      dots.appendChild(d); return d;
    });

    var st = Stage(stage);

    // ---- narration: each scene may play its own stretch of one audio file, lighting the words as they are read
    var audio = null, rafId = 0, segEnd = 0, words = [], wb = [], sentOf = [], playTimer = 0, gen = 0;
    function setListenText(on) { listen.textContent = on ? (ui.pause || T("Pause", "مکث")) : (ui.listen || T("Listen", "گوش کن")); }
    function clearMarks() { words.forEach(function (w) { w.classList.remove("now"); w.classList.remove("now-s"); }); }
    function stopAudio() {
      gen++; clearTimeout(playTimer); if (audio) audio.pause(); cancelAnimationFrame(rafId);
      listen.setAttribute("aria-pressed", "false"); setListenText(false); clearMarks();
    }
    function tick() {
      var t = audio.currentTime, cw = -1;
      for (var i = 0; i < wb.length; i++) { if (wb[i][0] <= t && t <= wb[i][1] + .25) { cw = i; } }
      var cs = cw >= 0 ? sentOf[cw] : -1;
      words.forEach(function (w, i) { w.classList.toggle("now", i === cw); w.classList.toggle("now-s", cs >= 0 && sentOf[i] === cs); });
      if (t >= segEnd - .05) { audio.pause(); listen.setAttribute("aria-pressed", "false"); setListenText(false); clearMarks(); return; }
      if (!audio.paused) rafId = requestAnimationFrame(tick);
    }
    function ensureAudio() {
      if (!audio) { audio = new Audio(data.audio.src); audio.preload = "auto"; audio.addEventListener("play", function () { cancelAnimationFrame(rafId); rafId = requestAnimationFrame(tick); }); }
      return audio;
    }
    // a tap on Next/the sound switch "unlocks" the audio for phones, so a timed start a moment later is allowed
    function unlock() { if (!data.audio || audio) return; ensureAudio(); var pr = audio.play(); audio.pause(); if (pr && pr.catch) pr.catch(function () { /* fine */ }); }
    // read a scene: get the audio to its place first (seek finished), wait `delay` ms, then play. Replay uses no delay.
    function playScene(sc, delay) {
      if (!sc.audio) return;
      stopAudio(); var my = gen; ensureAudio(); segEnd = sc.audio[1];
      var start = sc.audio[0], waited = false, ready = false;
      function fire() {
        if (my !== gen || !waited || !ready) return;
        var pr = audio.play();
        if (pr && pr.catch) pr.catch(function () { listen.setAttribute("aria-pressed", "false"); setListenText(false); });
        listen.setAttribute("aria-pressed", "true"); setListenText(true);
      }
      function prep() {
        if (my !== gen) return;
        if (Math.abs(audio.currentTime - start) > .03) {
          audio.addEventListener("seeked", function f() { audio.removeEventListener("seeked", f); ready = true; fire(); });
          audio.currentTime = start;
        } else { ready = true; fire(); }
      }
      if (audio.readyState >= 1) prep(); else audio.addEventListener("loadedmetadata", function f() { audio.removeEventListener("loadedmetadata", f); prep(); });
      playTimer = setTimeout(function () { waited = true; fire(); }, delay || 0);
    }
    listen.onclick = function () {
      var sc = scenes[cur]; if (!sc.audio) return;
      if (audio && !audio.paused) { stopAudio(); return; }
      playScene(sc, 0);
    };
    replay.onclick = function () { var sc = scenes[cur]; if (sc.audio) playScene(sc, 0); };
    // the sound switch of the bottom bar (paper pages): on = each scene reads itself aloud
    var sound = G.state.sound !== false;
    function soundBtn() {
      if (!tsound) return;
      tsound.setAttribute("aria-pressed", sound ? "true" : "false");
      tsound.querySelector("span").textContent = sound ? T("ON", "روشن") : T("OFF", "خاموش");
    }
    if (paper && tsound && data.audio) {
      tsound.hidden = false; soundBtn();
      tsound.onclick = function () {
        sound = !sound; G.state.sound = sound; G.save(); soundBtn();
        unlock(); if (!sound) stopAudio(); else if (scenes[cur] && scenes[cur].audio) playScene(scenes[cur], 0);
      };
    }

    // ---- text, question, game, end
    function showText(sc) {
      text.innerHTML = ""; words = []; wb = []; sentOf = []; var sentCount = 0;
      if (sc.lines) {
        sc.lines.forEach(function (ln) {
          var p = el("p", "line r-" + (ln.role || "narrator") + (ln.li ? " li" : ""));
          if (ln.who) p.appendChild(el("b", "who", ln.who));
          var sid = sentCount;
          (ln.w || []).forEach(function (w, i) {
            var s = el("span", "w" + (w[3] ? " bd" : ""), w[0]); p.appendChild(s); if (i < ln.w.length - 1) p.appendChild(document.createTextNode(" "));
            words.push(s); wb.push([w[1], w[2]]); sentOf.push(sid);
            if (/[.!?؟…:]["”»')]*$/.test(w[0])) sid = ++sentCount;
          });
          if (sid === sentCount) sentCount++;
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
        if (sc.continue && G.state.last && G.state.last.href) {  // pick up where the child left off
          var cli = el("li", "dcont"), ca = el("a", "", (ui.cont || T("Continue your case", "ادامهٔ پرونده")) + ": " + G.state.last.t);
          ca.href = G.state.last.href + "#scene-" + G.state.last.scene; cli.appendChild(ca); nl.appendChild(cli);
        }
        sc.links.forEach(function (l) {
          var li = el("li"), a = el("a", "", l.t); a.href = l.hrefs ? (l.hrefs[G.state.level] || l.hrefs.explorers) : l.href;
          if (l.hrefs) a.setAttribute("data-hrefs", JSON.stringify(l.hrefs));
          if (l.sub) a.appendChild(el("small", "", l.sub));
          li.appendChild(a); nl.appendChild(li);
        });
        text.appendChild(nl);
      }
    }
    function showTitle(sc) {
      ttl.innerHTML = "";
      wrap.classList.toggle("is-title", !!sc.title);
      if (!sc.title) return;
      var t = sc.title, box = el("div", "dttl-in");
      var h = el("h2", "dttl-h");
      (t.big || []).forEach(function (line, k) { h.appendChild(el("span", "tl tl" + k, line)); });
      box.appendChild(h);
      if (t.sub) box.appendChild(el("p", "dttl-sub", t.sub));
      var go1 = el("button", "dbtn dplay", (t.go || T("Play", "بازی")) + " "); go1.type = "button";
      go1.appendChild(el("span", "arr", FA ? "←" : "→"));
      go1.onclick = function () { go(cur + 1, { dir: 1 }); };
      box.appendChild(go1);
      var art = el("div", "dttl-art"); ttl.appendChild(art); ttl.appendChild(box);
      var draw = function () { var r = ttl.getBoundingClientRect(); if (r.width) art.innerHTML = P.crowd(Math.round(r.width), Math.round(r.height), 11); };
      redraw = draw; draw(); requestAnimationFrame(draw);
    }
    var redraw = null, rt = 0;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if (redraw && wrap.classList.contains("is-title")) redraw(); }, 150); });
    function applyLevel() {
      document.querySelectorAll("a[data-hrefs]").forEach(function (a) { try { var h = JSON.parse(a.getAttribute("data-hrefs")); a.href = h[G.state.level] || h.explorers; } catch (e) { /* ignore */ } });
      document.querySelectorAll(".tage").forEach(function (a) { a.textContent = G.state.level === "investigators" ? N("11–14") : G.state.level ? N("7–10") : N("7–14"); });
    }
    function showPick(sc) {
      pickBox.innerHTML = "";
      if (!sc.pick) return;
      if (sc.pick.q) pickBox.appendChild(el("p", "dq", sc.pick.q));
      var row = el("div", "dpick-row"); row.setAttribute("role", "group");
      sc.pick.options.forEach(function (o) {
        var b = el("button", "dbtn dchoice"); b.type = "button"; b.appendChild(el("b", "", o.t)); if (o.sub) b.appendChild(el("small", "", o.sub));
        b.setAttribute("aria-pressed", G.state.level === o.level ? "true" : "false");
        b.onclick = function () {
          G.state.level = o.level; G.save(); applyLevel();
          row.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
          document.dispatchEvent(new CustomEvent("games:level"));
          go(cur + 1, { dir: 1, noskip: true });
        };
        row.appendChild(b);
      });
      pickBox.appendChild(row);
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
          if (o.face && sc.ask.who) st.face(sc.ask.who, o.face);
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
      if (scenes[i].skip === "seen" && G.state.seen && !opts.noskip && i + (opts.dir || 1) >= 0 && i + (opts.dir || 1) < n) { return go(i + (opts.dir || 1), opts); }
      if (scenes[i].pick && scenes[i].pick.skip && G.state.level && !opts.noskip && i + (opts.dir || 1) >= 0 && i + (opts.dir || 1) < n) { return go(i + (opts.dir || 1), opts); }
      var first = cur < 0;
      stopAudio();
      var sc = scenes[i];
      cur = i;
      st.set(sc, first);
      label.textContent = sc.label || ""; label.hidden = !sc.label;
      showText(sc); showAsk(sc); showGame(sc); showTitle(sc); showPick(sc);
      ctl.hidden = !sc.audio || !!sc.game || !!sc.title; setListenText(false);
      if (paper && tsound && sound && sc.audio && !opts.quiet) playScene(sc, 1000);  // with the sound on, each scene reads itself when it arrives
      scene.className = "dscene" + (sc.game ? " has-game" : "") + (sc.pic ? " has-pic" : "");
      stage.hidden = !!sc.nostage || !!sc.title; label.classList.toggle("over", false);
      count.textContent = N(i + 1) + " / " + N(n);
      var h1 = document.querySelector("h1.sr-h");
      if (paper && root.getAttribute("data-level") && h1 && !opts.quiet && i > 0) { G.state.last = { href: location.pathname, scene: i + 1, t: h1.textContent, n: n }; G.save(); }
      if (sc.continue) { G.state.seen = true; G.save(); }
      if (chips) Array.prototype.forEach.call(chips.children, function (c) { c.classList.toggle("on", c.getAttribute("data-part") === sc.part); c.setAttribute("aria-current", c.getAttribute("data-part") === sc.part ? "step" : "false"); });
      dotEls.forEach(function (d, k) { d.classList.toggle("on", k === i); d.classList.toggle("done", k < i); d.setAttribute("aria-current", k === i ? "step" : "false"); });
      nav.style.setProperty("--p", n > 1 ? (100 * i / (n - 1)).toFixed(1) + "%" : "100%");
      back.disabled = i === 0;
      next.disabled = false; next.hidden = !!sc.title || !!sc.nonext; back.hidden = !!sc.title;
      next.classList.remove("pulse");
      next.textContent = i === n - 1 ? (ui.again || T("Start again", "دوباره از اول")) : (sc.next || ui.next || T("Next", "بعدی"));
      next.classList.toggle("last", i === n - 1);
      if (sc.end) { confetti(); root.setAttribute("data-game", "deck"); G.star(root); G.say(T("Finished! You earned a star.", "تمام شد! یک ستاره گرفتی.")); }
      if (!first && !opts.quiet) { scene.focus({ preventScroll: true }); root.scrollIntoView({ block: "start", behavior: G.reduced() ? "auto" : "smooth" }); }
      if (history.replaceState && !opts.quiet) { try { history.replaceState(null, "", "#scene-" + (i + 1)); } catch (e) { /* ignore */ } }
    }
    next.onclick = function () { unlock(); if (cur === n - 1) { go(0, { noskip: true }); } else go(cur + 1, { dir: 1 }); };
    back.onclick = function () { go(cur - 1, { dir: -1 }); };
    var dir = FA ? -1 : 1;
    root.addEventListener("keydown", function (e) {
      if (e.target.closest && e.target.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight") { go(cur + dir, { dir: dir }); e.preventDefault(); }
      if (e.key === "ArrowLeft") { go(cur - dir, { dir: -dir }); e.preventDefault(); }
    });
    var sx = null;
    wrap.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
    wrap.addEventListener("touchend", function (e) {
      if (sx === null) return;
      var dx = e.changedTouches[0].clientX - sx; sx = null;
      if (Math.abs(dx) > 70 && !(e.target.closest && e.target.closest(".dgame, .dask"))) go(cur + (dx < 0 ? dir : -dir), { dir: dx < 0 ? dir : -dir });
    }, { passive: true });
    function fromHash() {
      var h = location.hash.replace("#", ""), m = /^scene-(\d+)$/.exec(h);
      if (m) { go(+m[1] - 1, { quiet: true }); return true; }
      for (var k = 0; k < n; k++) if (scenes[k].anchor === h) { go(k, { noskip: true }); return true; }
      return false;
    }
    window.addEventListener("hashchange", fromHash);
    applyLevel();
    if (!fromHash()) go(0, { quiet: true });
    root.deck = { go: go, count: n, audio: function () { return audio; } };
  }

  // the hand-drawn wobble: every line on the stage is pushed a little off true by this filter (see scenes.css)
  function roughen() {
    if (document.getElementById("d-rough")) return;
    var d = document.createElement("div");
    d.setAttribute("aria-hidden", "true"); d.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
    d.innerHTML = '<svg width="0" height="0"><filter id="d-rough" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="4" result="n"/>' +
      '<feDisplacementMap in="SourceGraphic" in2="n" scale="3.2" xChannelSelector="R" yChannelSelector="G"/></filter></svg>';
    document.body.appendChild(d);
  }
  if (document.body) roughen(); else document.addEventListener("DOMContentLoaded", roughen);

  window.Scenes = { Stage: Stage, rich: rich };
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-deck]").forEach(Deck);
  });
})();
