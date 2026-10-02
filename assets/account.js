/* Mastering Epistemology — Google sign-in and sync.

   There is no server. Signing in with Google gives this page a short-lived
   access token (OAuth 2.0 for client-side apps) with one data permission:
   drive.appdata, a private folder in the reader's own Google Drive that only
   this site can see. Progress, notes, the review deck, reading settings,
   AI settings and chats are merged into one file there (epis-sync.json), so
   they follow the reader to any browser where they sign in.

   The client ID below is public by design; there is no client secret here. */
(function () {
  "use strict";
  var CLIENT_ID = "784452233050-hvolc36t22vat1h2egmf2kndghnlavpb.apps.googleusercontent.com";
  var SCOPES = "openid email profile https://www.googleapis.com/auth/drive.appdata";
  var FILE = "epis-sync.json";
  var SCRIPT = document.currentScript && document.currentScript.src;
  var ROOT = SCRIPT ? new URL("../", SCRIPT).href : new URL("./", location.href).href;
  var FA = document.documentElement.lang === "fa";
  var HOME = ROOT + (FA ? "fa/" : "");
  function T(en, fa) { return FA ? fa : en; }
  function N(x) { return FA ? String(x).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }) : String(x); }

  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { if (v === null || v === undefined) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  function json(k, fallback) { try { return JSON.parse(get(k) || "null") || fallback; } catch (e) { return fallback; } }
  function emit(name) { document.dispatchEvent(new Event(name)); }

  /* ------------------------------------------------------------ session */
  function user() { return json("epis-user", null); }
  function tokenInfo() { return json("epis-token", null); }
  function token() {
    var t = tokenInfo();
    return t && t.exp > Date.now() + 60000 ? t.access : null;
  }
  function signedIn() { return !!user(); }

  function signIn(opts) {
    opts = opts || {};
    var state = Math.random().toString(36).slice(2) + Date.now().toString(36);
    try { sessionStorage.setItem("epis-oauth", JSON.stringify({ state: state, back: opts.back || location.href, silent: !!opts.silent })); } catch (e) { /* ignore */ }
    var u = user();
    var params = {
      client_id: CLIENT_ID, redirect_uri: ROOT + "oauth-callback.html", response_type: "token", scope: SCOPES,
      include_granted_scopes: "true", state: state
    };
    if (opts.silent) params.prompt = "none";
    else if (!u) params.prompt = "select_account";
    if (u && u.email) params.login_hint = u.email;
    location.href = "https://accounts.google.com/o/oauth2/v2/auth?" + new URLSearchParams(params).toString();
  }
  function signOut() {
    var t = tokenInfo();
    if (t && t.access) fetch("https://oauth2.googleapis.com/revoke?token=" + encodeURIComponent(t.access), { method: "POST" }).catch(function () {});
    set("epis-token", null);
    set("epis-user", null);
    set("epis-sync", null);
    // Keys belong to the account; don't leave them in this browser.
    var ai = json("epis-ai", null);
    if (ai && ai.keys) { ai.keys = {}; set("epis-ai", JSON.stringify(ai)); }
    emit("epis:account");
    emit("epis:ai");
  }

  /* ------------------------------------------------------------ what gets synced */
  function newer(a, b, field) { return (a && a[field] || 0) >= (b && b[field] || 0) ? a : b; }
  function mergeMap(a, b, field) {
    var out = {};
    [a || {}, b || {}].forEach(function (m) {
      Object.keys(m).forEach(function (k) { out[k] = out[k] ? newer(out[k], m[k], field) : m[k]; });
    });
    return out;
  }
  function mergeProgress(a, b) {
    var out = mergeMap(a, b, "t");
    Object.keys(out).forEach(function (k) {
      var p = Math.max((a && a[k] && a[k].p) || 0, (b && b[k] && b[k].p) || 0);
      out[k] = Object.assign({}, out[k], { p: p });
    });
    return out;
  }
  function localState() {
    return {
      v: 1,
      notes: json("epis-notes", { v: 1, items: {} }),
      progress: json("epis-progress", {}),
      review: json("epis-review", {}),
      prefs: { ts: +(get("epis-prefs-ts") || 0), reader: json("epis-reader", {}), theme: get("epistemology-theme") || "system", shade: get("epis-shade") || "" },
      ai: json("epis-ai", null),
      chats: json("epis-chats", {})
    };
  }
  function merge(local, remote) {
    if (!remote || remote.v !== 1) return local;
    var notes = window.EpisNotes ? window.EpisNotes.merge(local.notes, remote.notes) : newer(local.notes, remote.notes, "updated");
    return {
      v: 1,
      notes: notes,
      progress: mergeProgress(local.progress, remote.progress),
      review: mergeMap(local.review, remote.review, "last"),
      prefs: newer(local.prefs, remote.prefs, "ts"),
      ai: local.ai || remote.ai ? newer(local.ai, remote.ai, "updated") : null,
      chats: mergeMap(local.chats, remote.chats, "updated")
    };
  }
  function applyLocal(s) {
    var before = JSON.stringify(localState());
    set("epis-notes", JSON.stringify(s.notes));
    set("epis-progress", JSON.stringify(s.progress));
    set("epis-review", JSON.stringify(s.review));
    if (s.prefs && s.prefs.ts) {
      set("epis-reader", JSON.stringify(s.prefs.reader || {}));
      set("epistemology-theme", s.prefs.theme || "system");
      set("epis-shade", s.prefs.shade || "");
      set("epis-prefs-ts", String(s.prefs.ts));
    }
    if (s.ai) set("epis-ai", JSON.stringify(s.ai));
    set("epis-chats", JSON.stringify(s.chats || {}));
    return before !== JSON.stringify(localState());
  }

  /* ------------------------------------------------------------ Google Drive (app data folder) */
  function api(url, init) {
    init = init || {};
    init.headers = Object.assign({ Authorization: "Bearer " + token() }, init.headers || {});
    return fetch(url, init).then(function (r) {
      if (r.status === 401) { set("epis-token", null); throw new Error("expired"); }
      if (!r.ok) return r.text().then(function (t) { throw new Error(r.status + " " + t.slice(0, 200)); });
      return r;
    });
  }
  function findFile() {
    var q = encodeURIComponent("name='" + FILE + "'");
    return api("https://www.googleapis.com/drive/v3/files?spaces=appDataFolder&fields=files(id,modifiedTime)&q=" + q)
      .then(function (r) { return r.json(); }).then(function (d) { return d.files && d.files[0] ? d.files[0].id : null; });
  }
  function download(id) {
    return api("https://www.googleapis.com/drive/v3/files/" + id + "?alt=media").then(function (r) { return r.json(); }).catch(function (e) {
      if (/expired/.test(e.message)) throw e;
      return null;
    });
  }
  function upload(id, data) {
    var body = JSON.stringify(data);
    if (id) {
      return api("https://www.googleapis.com/upload/drive/v3/files/" + id + "?uploadType=media",
        { method: "PATCH", headers: { "Content-Type": "application/json" }, body: body });
    }
    var boundary = "epis" + Date.now();
    var multipart = "--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n" +
      JSON.stringify({ name: FILE, parents: ["appDataFolder"] }) + "\r\n--" + boundary +
      "\r\nContent-Type: application/json\r\n\r\n" + body + "\r\n--" + boundary + "--";
    return api("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
      { method: "POST", headers: { "Content-Type": "multipart/related; boundary=" + boundary }, body: multipart });
  }

  var syncing = null, again = false;
  function status() { return json("epis-sync", {}); }
  function setStatus(s) { set("epis-sync", JSON.stringify(Object.assign(status(), s))); emit("epis:account"); }
  function sync() {
    if (!signedIn()) return Promise.resolve("signed-out");
    if (!token()) { setStatus({ pending: true }); return Promise.resolve("reconnect"); }
    if (syncing) { again = true; return syncing; }
    setStatus({ busy: true, error: "" });
    syncing = findFile().then(function (id) {
      return (id ? download(id) : Promise.resolve(null)).then(function (remote) {
        var merged = merge(localState(), remote);
        var changedHere = applyLocal(merged);
        return upload(id, Object.assign({ saved: Date.now() }, merged)).then(function () { return changedHere; });
      });
    }).then(function (changedHere) {
      setStatus({ busy: false, pending: false, at: Date.now(), error: "" });
      if (changedHere) { emit("epis:notes"); emit("epis:review"); emit("epis:ai"); emit("epis:synced"); }
      return "ok";
    }).catch(function (e) {
      setStatus({ busy: false, pending: true, error: /expired/.test(e.message) ? "" : e.message });
      return "error";
    }).then(function (r) {
      syncing = null;
      if (again) { again = false; return sync(); }
      return r;
    });
    return syncing;
  }
  var timer = 0;
  function soon() {
    if (!signedIn()) return;
    setStatus({ pending: true });
    clearTimeout(timer);
    timer = setTimeout(sync, 4000);
  }
  ["epis:notes", "epis:review", "epis:progress", "epis:prefs", "epis:ai", "epis:chats"].forEach(function (ev) {
    document.addEventListener(ev, function () { if (!syncing) soon(); });
  });
  window.addEventListener("pagehide", function () { if (status().pending && token()) sync(); });

  window.EpisAccount = { signedIn: signedIn, user: user, token: token, signIn: signIn, signOut: signOut, sync: sync, status: status };

  /* ------------------------------------------------------------ on every page */
  var navLinks = document.querySelectorAll('#umenu a[href$="account/"], #ubtn, #mnav a[href$="account/"]');
  function paintNav() { Array.prototype.forEach.call(navLinks, paintLink); }
  function paintLink(navLink) {
    var u = user();
    var label = navLink.querySelector("span");
    if (label) label.textContent = u ? (u.given_name || (u.name || "").split(" ")[0] || T("Account", "حساب")) : T("Sign in", "ورود");
    navLink.classList.toggle("signed-in", !!u);
    if (u && u.picture) {
      var img = navLink.querySelector("img.av");
      if (!img) { img = document.createElement("img"); img.className = "av"; img.alt = ""; img.referrerPolicy = "no-referrer"; navLink.insertBefore(img, navLink.firstChild); }
      img.src = u.picture;
    }
  }
  paintNav();
  document.addEventListener("epis:account", paintNav);

  // Once per browser session, quietly renew an expired sign-in so syncing just works.
  if (signedIn()) {
    if (token()) sync();
    else {
      var tried = false;
      try { tried = sessionStorage.getItem("epis-renewed") === "1"; } catch (e) { tried = true; }
      if (!tried && !/oauth-callback/.test(location.pathname)) {
        try { sessionStorage.setItem("epis-renewed", "1"); } catch (e) { /* ignore */ }
        signIn({ silent: true });
      }
    }
  }

  /* ------------------------------------------------------------ the account page */
  var host = document.getElementById("account");
  if (!host) return;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function ago(t) {
    if (!t) return "never";
    var m = Math.round((Date.now() - t) / 60000);
    return m < 1 ? T("just now", "همین حالا") : m < 60 ? N(m) + T(" min ago", " دقیقه پیش") : m < 1440 ? N(Math.round(m / 60)) + T(" h ago", " ساعت پیش")
      : new Date(t).toLocaleDateString(FA ? "fa-IR" : undefined);
  }
  function counts() {
    var notes = window.EpisNotes ? window.EpisNotes.live(window.EpisNotes.load()) : [];
    var prog = json("epis-progress", {}), rev = json("epis-review", {}), now = Date.now();
    return {
      hl: notes.filter(function (i) { return i.type !== "page"; }).length,
      read: Object.keys(prog).filter(function (k) { return prog[k].p >= 0.97; }).length,
      started: Object.keys(prog).length,
      due: Object.keys(rev).filter(function (k) { return rev[k].due <= now; }).length,
      deck: Object.keys(rev).length
    };
  }
  function render() {
    var u = user(), st = status(), c = counts();
    var card = u
      ? '<div class="acc-user">' + (u.picture ? '<img alt="" referrerpolicy="no-referrer" src="' + esc(u.picture) + '">' : "") +
        "<div><b>" + esc(u.name || u.email) + "</b><span>" + esc(u.email || "") + "</span></div></div>" +
        '<p class="acc-sync">' + (st.busy ? T("Syncing…", "در حال همگام‌سازی…") : st.error ? T("Last sync failed: ", "آخرین همگام‌سازی ناموفق بود: ") + esc(st.error)
          : (st.at ? T("Synced ", "همگام‌سازی: ") + ago(st.at) : T("Not synced yet", "هنوز همگام‌سازی نشده"))) +
        (st.pending && !token() ? T(" · sign-in needs renewing to sync new changes", " · برای همگام‌سازیِ تغییراتِ تازه باید دوباره وصل شوید") : "") + "</p>" +
        '<div class="acc-actions">' + (token() ? '<button type="button" class="btn primary" data-act="sync">' + T("Sync now", "همگام‌سازی") + '</button>'
          : '<button type="button" class="btn primary" data-act="renew">' + T("Reconnect to sync", "اتصالِ دوباره برای همگام‌سازی") + '</button>') +
        '<button type="button" class="btn" data-act="signout">' + T("Sign out", "خروج") + '</button></div>'
      : '<p>' + T("Sign in to keep your reading progress, highlights and notes, review deck, reading settings and AI keys in your own Google Drive, " +
        "so they follow you to any device. Without signing in, everything still works, but stays in this browser only.",
        "وارد شوید تا پیشرفتِ خواندن، نشانه‌گذاری‌ها و یادداشت‌ها، دستهٔ مرور، تنظیماتِ خواندن و کلیدهای هوش مصنوعی در گوگل‌درایوِ خودتان نگه داشته شوند " +
        "و در هر دستگاهی همراهتان باشند. بی‌ورود هم همه‌چیز کار می‌کند، ولی فقط در همین مرورگر می‌ماند.") + "</p>" +
        '<button type="button" class="gbtn" data-act="signin"><svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.6 13.3l7.9 6.1C12.4 13.7 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.7c4.3-4 6.9-9.9 6.9-17.1z"/><path fill="#FBBC05" d="M10.5 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.6 10.7l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.7c-2.1 1.4-4.8 2.3-8.5 2.3-6.3 0-11.6-4.2-13.5-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z"/></svg>' + T("Sign in with Google", "ورود با حساب گوگل") + '</button>' +
        '<p class="acc-fine">' + T("Google asks for permission to see your name and email, and to use a private app folder in your Drive. " +
        "The site can't see any of your other files, and there is no server of ours in between.",
        "گوگل اجازه می‌خواهد نام و ایمیلتان را ببیند و از پوشه‌ای خصوصی در درایوتان استفاده کند. " +
        "این سایت هیچ‌یک از دیگر پرونده‌هایتان را نمی‌بیند و هیچ سروری از ما در این میان نیست.") +
        ' <a href="' + HOME + 'privacy.html">' + T("Privacy policy", "سیاستِ حریم خصوصی") + '</a> · <a href="' + HOME + 'terms.html">' +
        T("Terms of service", "شرایطِ استفاده") + "</a></p>";
    host.querySelector("[data-slot=signin]").innerHTML = card;
    host.querySelector("[data-slot=study]").innerHTML =
      '<a class="acc-tile" href="' + HOME + 'notes/"><b>' + N(c.hl) + "</b><span>" + T("highlights and notes", "نشانه‌گذاری و یادداشت") + "</span><em>" + T("Open your notebook →", "باز کردنِ دفترچه ←") + "</em></a>" +
      '<a class="acc-tile" href="' + HOME + 'review/"><b>' + N(c.due) + "</b><span>" + T("questions due for review", "پرسشِ آمادهٔ مرور") + "</span><em>" + N(c.deck) + T(" in your deck →", " در دستهٔ شما ←") + "</em></a>" +
      '<a class="acc-tile" href="' + HOME + 'guide/"><b>' + N(c.read) + "</b><span>" + T("chapters finished", "فصلِ تمام‌شده") + "</span><em>" + N(c.started) + T(" started →", " آغازشده ←") + "</em></a>";
    var err = host.querySelector("[data-slot=error]");
    var e = "";
    try { e = sessionStorage.getItem("epis-oauth-error") || ""; sessionStorage.removeItem("epis-oauth-error"); } catch (x) { /* ignore */ }
    if (e && !/interaction_required|login_required|consent_required/.test(e)) err.innerHTML = '<p class="acc-err">' + T("Google sign-in did not complete: ", "ورود با گوگل کامل نشد: ") + esc(e) + "</p>";
  }
  host.addEventListener("click", function (e) {
    var b = e.target.closest("[data-act]");
    if (!b) return;
    var act = b.getAttribute("data-act");
    if (act === "signin") signIn({ back: location.href });
    else if (act === "renew") signIn({ back: location.href });
    else if (act === "signout") { if (confirm(T("Sign out? Your notes stay in this browser and in your Google Drive; your AI keys are removed from this browser.", "خارج می‌شوید؟ یادداشت‌هایتان در این مرورگر و در گوگل‌درایو می‌مانند؛ کلیدهای هوش مصنوعی از این مرورگر پاک می‌شوند."))) signOut(); }
    else if (act === "sync") sync();
    else if (act === "export") {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([JSON.stringify(localState(), null, 1)], { type: "application/json" }));
      a.download = "epistemology-backup.json"; document.body.appendChild(a); a.click(); a.remove();
    } else if (act === "wipe") {
      if (!confirm(T("Delete all your progress, notes, review deck, chats and settings from this browser? Anything already synced stays in your Google Drive.", "همهٔ پیشرفت، یادداشت‌ها، دستهٔ مرور، گفت‌وگوها و تنظیمات از این مرورگر پاک شوند؟ آنچه همگام‌سازی شده در گوگل‌درایو می‌ماند."))) return;
      ["epis-notes", "epis-progress", "epis-review", "epis-reader", "epis-shade", "epis-prefs-ts", "epis-ai", "epis-chats", "epis-focus"].forEach(function (k) { set(k, null); });
      location.reload();
    }
  });
  ["epis:account", "epis:notes", "epis:review", "epis:synced"].forEach(function (ev) { document.addEventListener(ev, render); });
  render();
})();
