/* Episodes: a short animated film the child plays inside. Each clip plays with the characters' voices and captions,
   then the picture holds on its last frame and the child acts in it: picks an answer, taps things to measure or
   inspect, drags cards onto people. Answers change what plays next (a wrong idea plays out as a funny scene, then
   the film rewinds to the question). Data: the episode's steps, lines and media, embedded by tools/kids/site_kids.py;
   media files from tools/video/episode.py. Nothing is sent anywhere; progress stays in this browser. */
(function () {
  "use strict";
  var G = window.Games;
  if (!G) return;
  var T = G.T, el = G.el;

  // ---- little sounds, made on the spot (no files)
  var ac = null;
  function actx() {
    if (!ac) { try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { ac = null; } }
    if (ac && ac.state === "suspended") ac.resume();
    return ac;
  }
  function tone(f0, f1, dur, type, vol, delay) {
    var a = actx(); if (!a || G.state.sound === false) return;
    var t = a.currentTime + (delay || 0), o = a.createOscillator(), g = a.createGain();
    o.type = type || "sine"; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol || 0.18, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(a.destination); o.start(t); o.stop(t + dur + 0.05);
  }
  var fx = {
    pop: function () { tone(420, 900, 0.12, "sine", 0.2); },
    ding: function () { tone(880, 880, 0.18, "triangle", 0.16); tone(1320, 1320, 0.3, "triangle", 0.14, 0.12); },
    boing: function () { tone(300, 90, 0.35, "sine", 0.22); },
    rewind: function () { for (var i = 0; i < 6; i++) tone(900 - i * 110, 700 - i * 100, 0.09, "sawtooth", 0.05, i * 0.1); },
    tada: function () { [523, 659, 784, 1047].forEach(function (f, i) { tone(f, f, 0.25, "triangle", 0.15, i * 0.11); }); }
  };

  // ---- doodle icons for the answer cards
  var ICON = {
    up: '<path d="M14 30V18l6-10c2-3 6-1 5 2l-2 8h9c3 0 4 3 3 5l-4 9c-1 2-2 3-4 3H14z"/><path d="M6 18h8v16H6z"/>',
    down: '<path d="M14 10v12l6 10c2 3 6 1 5-2l-2-8h9c3 0 4-3 3-5l-4-9c-1-2-2-3-4-3H14z"/><path d="M6 6h8v16H6z"/>',
    hmm: '<circle cx="20" cy="20" r="14"/><path d="M14 16h.01M26 16h.01"/><path d="M14 27c4-2 8-2 12 1"/>',
    foot: '<path d="M14 36c-5 0-6-6-5-12 1-7 3-12 8-12s7 6 6 12c-1 5 0 12-9 12z"/><circle cx="12" cy="6" r="2"/><circle cx="17" cy="4" r="2"/><circle cx="22" cy="5" r="2"/><circle cx="26" cy="8" r="1.6"/>',
    shoe: '<path d="M4 26c0-4 2-8 6-8 3 0 5 3 9 3 6 0 10 2 15 4 3 1 3 6-1 6H6c-2 0-2-2-2-5z"/><path d="M12 18l3-6"/>',
    q: '<path d="M14 13c0-5 4-8 8-8s7 3 7 7c0 6-8 6-8 12"/><path d="M21 31h.01"/>'
  };
  function icon(name) {
    if (!ICON[name]) return null;
    var s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 40 40"); s.setAttribute("aria-hidden", "true"); s.setAttribute("class", "ep-ico");
    s.innerHTML = ICON[name];
    return s;
  }

  G.register("episode", function (box, D) {
    var level = box.getAttribute("data-level") || "explorers";
    var steps = D.steps, byId = {};
    steps.forEach(function (s, i) { s._i = i; byId[s.id] = s; });
    var off = {};          // answers already tried (a wrong idea is not offered again)
    var pred = null;       // the child's first guess, recalled at the end
    var sound = G.state.sound !== false;

    box.innerHTML = "";
    var wrap = el("div", "ep");
    var stage = el("div", "ep-stage");
    var still = el("img", "ep-still"); still.alt = ""; still.decoding = "async";
    var video = el("video", "ep-video");
    video.setAttribute("playsinline", ""); video.setAttribute("webkit-playsinline", ""); video.preload = "auto";
    video.setAttribute("aria-hidden", "true");
    var layer = el("div", "ep-layer");
    var cap = el("p", "ep-cap"); cap.setAttribute("aria-live", "polite"); cap.hidden = true;
    var skip = el("button", "ep-skip", "⏭"); skip.type = "button"; skip.setAttribute("aria-label", T("Skip this bit", "رد شدن")); skip.hidden = true;
    stage.appendChild(still); stage.appendChild(video); stage.appendChild(layer); stage.appendChild(cap); stage.appendChild(skip);
    var ask = el("div", "ep-ask"); ask.hidden = true;
    wrap.appendChild(stage); wrap.appendChild(ask);
    box.appendChild(wrap);
    var voice = new Audio(); voice.preload = "auto";
    var line = new Audio(); line.preload = "auto";

    // the bar's sound switch: off = no voices or film sound (the captions stay)
    var tsound = document.getElementById("tsound");
    function mute() { video.muted = !sound; voice.muted = !sound; line.muted = !sound; }
    if (tsound) {
      tsound.hidden = false;
      var paint = function () { tsound.setAttribute("aria-pressed", sound ? "true" : "false"); tsound.querySelector("span").textContent = sound ? T("ON", "روشن") : T("OFF", "خاموش"); };
      paint();
      tsound.onclick = function () { sound = !sound; G.state.sound = sound; G.save(); paint(); mute(); };
    }
    mute();
    // progress: one circle per film clip
    var tprog = document.getElementById("tprog"), clipIds = [];
    steps.forEach(function (s) { if (s.clip && clipIds.indexOf(s.clip) < 0 && !s.side) clipIds.push(s.clip); });
    function progress(cid) {
      if (!tprog) return;
      tprog.innerHTML = "";
      var k = clipIds.indexOf(cid);
      clipIds.forEach(function (c, i) { var d = el("i", i < k ? "done" : i === k ? "on" : ""); tprog.appendChild(d); });
      tprog.hidden = false;
    }

    function showCap(who, text) {
      if (!text) { cap.hidden = true; return; }
      cap.innerHTML = "";
      if (who && D.names[who]) cap.appendChild(el("b", "ep-who ep-" + who, D.names[who]));
      cap.appendChild(el("span", "", text));
      cap.hidden = false;
    }
    function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
    // play an audio element to its end; if the phone will not play it, wait as long as it would have taken
    function playTo(a, src, dur) {
      return new Promise(function (resolve) {
        var done = false, timer;
        function fin() { if (done) return; done = true; clearTimeout(timer); a.onended = null; resolve(); }
        a.src = src; a.currentTime = 0;
        a.onended = fin;
        timer = setTimeout(fin, (dur + 1.5) * 1000);
        var p = a.play();
        if (p && p.catch) p.catch(function () { clearTimeout(timer); timer = setTimeout(fin, dur * 1000); });
      });
    }
    // one spoken line (a question or a reaction), captioned
    function say(id) {
      var L = D.lines[id];
      if (!L) return Promise.resolve();
      showCap(L.who, L.t);
      return playTo(line, L.src, L.dur).then(function () { return wait(250); });
    }

    // a film clip with its voices; resolves when both have finished (the picture holds on its last frame)
    var skipNow = null;
    function playClip(cid) {
      var C = D.clips[cid];
      progress(cid);
      layer.innerHTML = ""; ask.hidden = true; ask.innerHTML = "";
      still.src = C.first; still.hidden = false;
      video.poster = C.first;
      video.src = C.video;
      var vDone = new Promise(function (r) {
        var t = setTimeout(r, (C.dur + 4) * 1000);
        video.onended = function () { clearTimeout(t); r(); };
        video.onerror = function () { clearTimeout(t); r(); };
      });
      var p = video.play();
      if (p && p.catch) p.catch(function () { /* blocked: the still shows; the voice timer carries on */ });
      video.onplaying = function () { still.hidden = true; };
      var V = C.voice;
      voice.ontimeupdate = function () {
        var t = voice.currentTime, cur = null;
        V.lines.forEach(function (l) { if (t >= l.b - 0.05 && t < l.e + 0.3) cur = l; });
        if (cur) showCap(cur.who, cur.t); else if (t > 0.1) cap.hidden = true;
      };
      var aDone = playTo(voice, V.src, V.dur);
      skip.hidden = false;
      return new Promise(function (resolve) {
        var over = false;
        function end() {
          if (over) return; over = true; skipNow = null; skip.hidden = true;
          voice.ontimeupdate = null; cap.hidden = true;
          still.src = C.last; still.hidden = false;
          resolve();
        }
        skipNow = function () { voice.pause(); video.pause(); end(); };
        Promise.all([vDone, aDone]).then(end);
      });
    }
    skip.onclick = function () { if (skipNow) skipNow(); };

    function go(id) {
      var s = id ? byId[id] : null;
      if (!s) return;
      if (s.levels && s.levels.indexOf(level) < 0) return go(nextOf(s));
      if (s.clip) {
        playClip(s.clip).then(function () {
          if (s.after) return say(s.after);
        }).then(function () {
          if (s.rewind) return rewindTo(s.rewind);
          go(nextOf(s));
        });
      } else if (s.do === "choose") choose(s);
      else if (s.do === "tap") tap(s);
      else if (s.do === "drag") drag(s);
      else if (s.do === "finish") finish(s);
    }
    function nextOf(s) {
      for (var i = s._i + 1; i < steps.length; i++) if (!steps[i].side) return steps[i].id;
      return null;
    }
    function rewindTo(id) {
      fx.rewind();
      stage.classList.add("rewinding");
      // back to the picture the question was asked on
      var back = byId[id], prev = null;
      for (var i = back._i - 1; i >= 0; i--) if (steps[i].clip) { prev = steps[i].clip; break; }
      return wait(1100).then(function () {
        stage.classList.remove("rewinding");
        if (prev) { still.src = D.clips[prev].last; still.hidden = false; progress(prev); }
        go(id);
      });
    }

    function question(s) {
      ask.innerHTML = ""; ask.hidden = false;
      var q = el("p", "ep-q", s.q);
      var again = el("button", "ep-again", "↻"); again.type = "button"; again.setAttribute("aria-label", T("Hear it again", "دوباره بشنو"));
      again.onclick = function () { say(s.say); };
      q.appendChild(again);
      ask.appendChild(q);
      return q;
    }

    // ---- pick an answer
    function choose(s) {
      question(s);
      var row = el("div", "ep-opts" + (s.options.length > 2 ? " three" : ""));
      ask.appendChild(row);
      var busy = false;
      s.options.forEach(function (o) {
        var b = el("button", "ep-opt"); b.type = "button";
        var ic = icon(o.icon); if (ic) b.appendChild(ic);
        b.appendChild(el("span", "", o.t));
        if (off[s.id + "/" + o.id]) { b.disabled = true; b.classList.add("tried"); }
        b.onclick = function () {
          if (busy) return; busy = true;
          actx(); fx.pop();
          if (s.id === "believe") pred = o;
          row.querySelectorAll(".ep-opt").forEach(function (x) { x.classList.toggle("dim", x !== b); });
          b.classList.add("picked");
          if (o.right) { fx.ding(); b.classList.add("right"); }
          if (o.retry) { fx.boing(); b.classList.add("shake"); }
          (o.say ? say(o.say) : wait(400)).then(function () {
            if (o.retry) {
              off[s.id + "/" + o.id] = 1; busy = false; b.disabled = true; b.classList.add("tried");
              row.querySelectorAll(".ep-opt").forEach(function (x) { x.classList.remove("dim", "picked", "shake"); });
              return;
            }
            if (o.go && byId[o.go] && !o.right) off[s.id + "/" + o.id] = 1;
            go(o.go || nextOf(s));
          });
        };
        row.appendChild(b);
      });
      say(s.say);
    }

    // ---- tap things in the picture (measure feet, inspect children)
    function tap(s) {
      question(s);
      var left = s.spots.length;
      s.spots.forEach(function (sp, i) {
        var b = el("button", "ep-spot"); b.type = "button";
        b.style.left = sp.x + "%"; b.style.top = sp.y + "%";
        b.style.animationDelay = (i * 0.25) + "s";
        b.setAttribute("aria-label", T("Look here", "این‌جا را ببین") + " " + (i + 1));
        b.onclick = function () {
          if (b.classList.contains("seen")) return;
          actx(); fx.pop();
          b.classList.add("seen"); b.disabled = true;
          var tag = el("span", "ep-tag", sp.t); tag.style.left = sp.x + "%"; tag.style.top = sp.y + "%";
          layer.appendChild(tag);
          G.say(sp.t);
          if (--left === 0) {
            fx.ding();
            wait(500).then(function () { return s.after ? say(s.after) : null; }).then(function () { return wait(700); })
              .then(function () { go(nextOf(s)); });
          }
        };
        layer.appendChild(b);
      });
      say(s.say);
    }

    // ---- drag cards onto people (tap a card, then a person, works too)
    function drag(s) {
      question(s);
      var tray = el("div", "ep-tray"); ask.appendChild(tray);
      var targets = s.targets.map(function (t, i) {
        var d = el("button", "ep-target"); d.type = "button";
        d.style.left = t.x + "%"; d.style.top = t.y + "%";
        d.setAttribute("aria-label", T("Child", "بچهٔ") + " " + (i + 1));
        layer.appendChild(d);
        return d;
      });
      var chosen = null, placed = 0, missed = 0;
      function place(card, k) {
        var c = s.cards[card.dataset.i];
        if (c.to === k && !targets[k].classList.contains("full")) {
          fx.ding();
          targets[k].classList.add("full"); targets[k].textContent = c.t;
          card.classList.add("used"); card.disabled = true; card.style.transform = "";
          if (++placed === s.cards.length) done();
          return true;
        }
        fx.boing(); card.classList.add("shake"); setTimeout(function () { card.classList.remove("shake"); }, 500);
        if (missed++ === 0 && s.miss) say(s.miss);
        return false;
      }
      function done() {
        tray.remove();
        if (s.reveal === "cause") causeArt(s.cause);
        wait(600).then(function () { return say(s.after); }).then(function () { return wait(400); }).then(function () {
          var b = el("button", "ep-go", T("Next", "بعدی") + " ▸"); b.type = "button";
          b.onclick = function () { actx(); go(nextOf(s)); };
          ask.appendChild(b); b.focus();
        });
      }
      targets.forEach(function (t, k) { t.onclick = function () { if (chosen) { place(chosen, k); chosen.classList.remove("sel"); chosen = null; } }; });
      G.shuffle(s.cards.map(function (c, i) { return i; })).forEach(function (i) {
        var c = s.cards[i], card = el("button", "ep-card", c.t); card.type = "button"; card.dataset.i = i;
        tray.appendChild(card);
        card.onclick = function () { actx(); if (card.disabled) return; if (chosen) chosen.classList.remove("sel"); chosen = card; card.classList.add("sel"); fx.pop(); };
        card.onpointerdown = function (e) {
          if (card.disabled) return;
          actx();
          var x0 = e.clientX, y0 = e.clientY, moved = false;
          card.setPointerCapture(e.pointerId);
          card.onpointermove = function (m) {
            var dx = m.clientX - x0, dy = m.clientY - y0;
            if (!moved && Math.abs(dx) + Math.abs(dy) < 8) return;
            moved = true; card.classList.add("dragging");
            card.style.transform = "translate(" + dx + "px," + dy + "px) scale(1.1)";
          };
          card.onpointerup = function (u) {
            card.onpointermove = card.onpointerup = null;
            card.classList.remove("dragging");
            if (!moved) return;
            card.style.transform = "";
            var hit = -1;
            targets.forEach(function (t, k) { var r = t.getBoundingClientRect(); if (u.clientX > r.left - 20 && u.clientX < r.right + 20 && u.clientY > r.top - 20 && u.clientY < r.bottom + 20) hit = k; });
            if (hit >= 0) place(card, hit);
            setTimeout(function () { card.classList.remove("sel"); if (chosen === card) chosen = null; }, 0);
          };
        };
      });
      say(s.say);
    }

    // the hidden cause, drawn over the picture: Age → bigger feet, Age → more years of reading
    function causeArt(c) {
      var svg = '<svg viewBox="0 0 100 56" class="ep-cause" aria-hidden="true">' +
        '<path class="ep-arrow" d="M44 14 C34 22 26 30 20 41"/><path class="ep-arrow" d="M56 14 C66 22 74 30 80 41"/>' +
        '<path class="ep-arrow" d="M17 36 l3 5 4-4"/><path class="ep-arrow" d="M76 37 l4 4 2-5"/></svg>';
      var art = el("div", "ep-causewrap"); art.innerHTML = svg;
      art.appendChild(el("span", "ep-node ep-top", c.top));
      art.appendChild(el("span", "ep-node ep-l", c.left));
      art.appendChild(el("span", "ep-node ep-r", c.right));
      layer.innerHTML = ""; layer.appendChild(art);
      G.say(c.top + " → " + c.left + ", " + c.right);
    }

    // ---- the end: the clue card, the star, the first guess remembered, and the next case
    function finish(s) {
      layer.innerHTML = ""; fx.tada(); confetti();
      G.star(box);
      G.state.episodes = G.state.episodes || {}; G.state.episodes[D.id] = 1; G.save();
      ask.innerHTML = ""; ask.hidden = false;
      var card = el("div", "ep-clue");
      card.appendChild(el("p", "ep-clue-k", T("Clue card", "کارتِ سرنخ")));
      card.appendChild(el("h2", "", s.card.title));
      card.appendChild(el("p", "", s.card.text));
      ask.appendChild(card);
      if (pred) {
        var p = el("p", "ep-pred");
        p.textContent = T("At the start you said: “", "اولش گفتی: «") + pred.t + T("”. Now you know how to check.", "». حالا می‌دانی چطور بررسی کنی.");
        ask.appendChild(p);
      }
      var row = el("div", "ep-ends");
      var again = el("button", "ep-go ghost", "↺ " + T("Watch again", "دوباره تماشا کن")); again.type = "button";
      again.onclick = function () { off = {}; pred = null; go(steps[0].id); };
      row.appendChild(again);
      if (s.next) {
        var n = el("a", "ep-next"); n.href = s.next.href;
        if (s.next.img) { var im = el("img"); im.src = s.next.img; im.alt = ""; im.loading = "lazy"; n.appendChild(im); }
        n.appendChild(el("span", "", s.next.t + " ▸"));
        row.appendChild(n);
      }
      ask.appendChild(row);
      say(s.say);
    }
    function confetti() {
      if (G.reduced()) return;
      var c = el("div", "ep-confetti");
      for (var i = 0; i < 40; i++) {
        var p = el("i"); p.style.left = Math.random() * 100 + "%"; p.style.animationDelay = Math.random() * 0.6 + "s";
        p.style.background = ["#f4b400", "#e94b6b", "#2bb3a3", "#5a6cf0", "#ff8a3d"][i % 5];
        c.appendChild(p);
      }
      stage.appendChild(c); setTimeout(function () { c.remove(); }, 3200);
    }

    // ---- the title screen: one big Play button (the first tap also lets phones play sound)
    var first = D.clips[byId[steps[0].id].clip];
    still.src = first.first;
    var title = el("div", "ep-title");
    title.appendChild(el("h2", "", D.title));
    title.appendChild(el("p", "", D.hook));
    var play = el("button", "ep-play"); play.type = "button"; play.setAttribute("aria-label", T("Play", "پخش"));
    play.innerHTML = '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M14 9l18 11-18 11z"/></svg>';
    title.appendChild(play);
    if (G.state.episodes && G.state.episodes[D.id]) title.appendChild(el("p", "ep-seen", "★ " + T("Case solved. Play it again?", "پرونده حل شد. دوباره بازی می‌کنی؟")));
    layer.appendChild(title);
    play.onclick = function () {
      actx();
      // unlock the media elements on this tap, so the later, timed starts are allowed on phones
      // (the film and its voices start right below, on this same tap; the lines element is woken here, silently)
      try {
        line.src = D.lines[Object.keys(D.lines)[0]].src; line.muted = true;
        var q = line.play();
        if (q && q.then) q.then(function () { line.pause(); line.muted = !sound; }, function () { line.muted = !sound; });
      } catch (e) { line.muted = !sound; }
      title.remove();
      go(steps[0].id);
    };
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && skipNow) skipNow(); });
  });
})();
