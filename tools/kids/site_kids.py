"""Build the children's section, How Do You Know? / «از کجا می‌دانی؟»: kids/ and fa/kids/.

Called by tools/site/build.py once per language, with the build module itself (b) so the shell, page writer,
Markdown renderer and the language being built are shared with the rest of the site.
Pages: kids/ (quest map), kids/<unit>/ (Explorers, ages 7–10), kids/<unit>/investigators.html (ages 11–14),
kids/<unit>/grownups.html, kids/words/, kids/books/, kids/grownups/.
"""
import html
import json
import os
import re
from pathlib import Path

import kidslib as K

ASSETS_KIDS = K.ROOT / "assets" / "kids"
LEVEL_FILE = {"explorers": "index.html", "investigators": "investigators.html"}
SCRIPTS = {"case": "games/case.js", "sorter": "kids/games/sorter.js", "quiz": "kids/games/quiz.js",
           "sim:confounder": "games/sims/confounder.js"}


def engine_scripts(b, root, engines):
    """The script tags for the game engines (and simulations) a page uses."""
    return "".join(f'<script src="{b.av(root, SCRIPTS[e])}" defer></script>' for e in sorted(engines))
ENGINE_OF = {}  # game id -> engine, filled while building


def esc(s):
    return html.escape(str(s), quote=True)


def published(u):
    return u.get("status") == "published" or (u.get("status") == "draft" and os.environ.get("EPIS_KIDS_DRAFTS") == "1")


def build(b, art, md):
    lang = b.LANG
    L, num = b.L, b.num
    data = K.units()
    units = data["units"]
    quests = {q["id"]: K.pick(q, lang) for q in data["quests"]}
    live = [u for u in units if published(u)]
    problems = []
    for u in live:
        problems += [f"{u['id']}: {p}" for p in unit_problems(u["id"])]
    if problems:
        raise SystemExit("kids: problems in published units:\n  " + "\n  ".join(problems))
    words = {w["id"]: K.pick(w, lang) for w in K.read_json(K.KIDS / "words.json")}
    out_dir = b.OUT() / "kids"
    written = set()

    def kpage(rel, **kw):
        b.page(f"kids/{rel}", kids=True, **kw)
        written.add((b.OUT() / "kids" / rel).resolve())

    # unit pages
    for i, u in enumerate(live):
        uid = u["id"]
        meta = K.unit_meta(uid)
        st = K.story(uid, lang)
        sync = load_sync(uid, lang)
        quest = quests[u["quest"]]
        prev_u, next_u = (live[i - 1] if i else None), (live[i + 1] if i + 1 < len(live) else None)
        title_u = K.pick(u, lang)["title"]
        for level in K.LEVELS:
            root = b.up(2)
            text = (K.unit_dir(uid) / f"{level}.{lang}.md").read_text(encoding="utf-8")
            fm, text = K.front_matter(text)
            engines = set()
            opener = ""
            m = next((m for m in K.BLOCK.finditer(text) if m.group(1) == "opener"), None)
            if m:  # game first: the opener comes before the story
                opener = render_lesson(b, md, m.group(0), uid, level, words, engines).replace("kblk k-opener", "kblk k-opener kopen", 1)
                text = text[:m.start()] + text[m.end():]
            lesson = render_lesson(b, md, text, uid, level, words, engines)
            story_html = render_story(b, uid, meta, st, sync, root)
            switch = level_switch(b, level)
            pager = unit_pager(b, prev_u, next_u, level, lang)
            body = (f'<main id="main" class="kmain kunit q{quest["n"]}"><header class="khead kband">{HUDHUD}'
                    f'<p class="kicker">{L("Quest", "ماجرای")} {num(quest["n"])} · {esc(quest["title"])} · {L("Unit", "درس")} {num(u["n"])}</p>'
                    f'<h1>{esc(title_u)}</h1>{switch}'
                    f'<p class="kstars" data-unit="{uid}" data-level="{level}" aria-live="polite"></p></header>'
                    f'{opener}{story_html}<div class="klesson prose">{lesson}</div>'
                    f'<p class="kgrown"><a href="grownups.html">{L("Notes for parents and teachers", "یادداشت برای پدر و مادر و معلم")} →</a></p>'
                    f'{pager}</main>')
            scripts = engine_scripts(b, root, engines)
            if sync:
                scripts += f'<script src="{b.av(root, "kids/player.js")}" defer></script>'
            lvl_name = L("Explorers", "کاوشگرها") if level == "explorers" else L("Investigators", "کارآگاه‌ها")
            kpage(f"{uid}/{LEVEL_FILE[level]}", root=root, title=f"{title_u} ({lvl_name})",
                  desc=fm.get("desc") or L("A thinking adventure for children.", "یک ماجرای فکری برای بچه‌ها."),
                  body=body, current="quests", extra_scripts=scripts)
        # grown-ups notes for the unit
        root = b.up(2)
        text = (K.unit_dir(uid) / f"grownups.{lang}.md").read_text(encoding="utf-8")
        fm, text = K.front_matter(text)
        notes, _ = md.render(text, link_rewriter(b, uid))
        body = (f'<main id="main" class="kmain"><header class="khead"><p class="kicker">{L("For grown-ups", "برای بزرگ‌ترها")} · '
                f'{L("Unit", "درس")} {num(u["n"])}</p><h1>{esc(title_u)}</h1>'
                f'<p><a href="./">{L("Explorers page (7–10)", "صفحهٔ کاوشگرها (۷ تا ۱۰)")}</a> · <a href="investigators.html">'
                f'{L("Investigators page (11–14)", "صفحهٔ کارآگاه‌ها (۱۱ تا ۱۴)")}</a></p></header>'
                f'<div class="prose kgrownups">{notes}</div></main>')
        kpage(f"{uid}/grownups.html", root=root, title=L("For grown-ups: ", "برای بزرگ‌ترها: ") + title_u,
              desc=L("Goals, discussion plan, answers and rubric for this unit.", "هدف‌ها، برنامهٔ گفت‌وگو، پاسخ‌ها و معیارِ ارزیابیِ این درس."),
              body=body, current="grownups")

    # the arcade: games shared with Baloney Detector, in their kids' versions (kids/arcade/<id>/)
    import site_play  # tools/play (on the path via tools/site/build.py)
    arcade = [K.pick(a, lang) for a in K.read_json(K.KIDS / "arcade.json")["games"]]
    for a in arcade:
        root = b.up(3)
        for level in K.LEVELS:
            engines = set()
            g = kid_friendly(b, for_level(K.pick(K.game(a["id"]), lang), level))
            g["title"] = a["title"]
            engines.add(g["engine"])
            engines.update(f'sim:{c["sim"]["kind"]}' for c in g.get("cases", []) if c.get("sim"))
            unit = f"arcade-{a['id']}"
            body = (f'<main id="main" class="kmain kunit karc c-{a["color"]}"><header class="khead kband">{HUDHUD}'
                    f'<p class="kicker">{L("Play now", "حالا بازی کن")}</p><h1>{esc(a["title"])}</h1>{level_switch(b, level)}'
                    f'<p class="kstars" data-unit="{unit}" data-level="{level}" aria-live="polite"></p></header>'
                    f'<section class="kblk k-opener kopen">{site_play.game_box(b, a["id"], g, level, unit)}</section>'
                    f'<p class="kgrown"><a href="../../">{L("Back to the quests", "برگشت به ماجراها")}</a></p></main>')
            kpage(f"arcade/{a['id']}/{LEVEL_FILE[level]}", root=root, title=a["title"], desc=a["hook"], body=body,
                  current="quests", extra_scripts=engine_scripts(b, root, engines))

    # home: the quest map
    root = b.up(1)
    kpage("index.html", root=root, title=L("How Do You Know?", "از کجا می‌دانی؟"),
          desc=L("Thinking adventures for ages 7–14: stories, games and questions about how we know what we know.",
                 "ماجراهای فکری برای ۷ تا ۱۴ ساله‌ها: قصه، بازی و پرسش دربارهٔ این‌که از کجا می‌دانیم."),
          body=home_body(b, data, quests, arcade), current="quests")
    kpage("words/index.html", root=b.up(2), title=L("Picture dictionary", "واژه‌نامهٔ تصویری"),
          desc=L("The thinking words, with pictures, in English and Persian.", "واژه‌های فکر کردن، با تصویر، به فارسی و انگلیسی."),
          body=words_body(b, live, words), current="words")
    kpage("books/index.html", root=b.up(2), title=L("Book club", "باشگاهِ کتاب"),
          desc=L("Famous books to read with this site, with questions to talk about.", "کتاب‌های معروف برای خواندن همراهِ این سایت، با پرسش‌هایی برای گفت‌وگو."),
          body=books_body(b), current="books")
    kpage("grownups/index.html", root=b.up(2), title=L("For grown-ups", "برای بزرگ‌ترها"),
          desc=L("How the children's section works, what it teaches and how it keeps children safe.",
                 "بخشِ کودکان چطور کار می‌کند، چه یاد می‌دهد و چطور بچه‌ها را امن نگه می‌دارد."),
          body=grownups_body(b, md, data, live), current="grownups")

    # remove pages of units that are no longer published
    if out_dir.exists():
        for p in out_dir.rglob("*.html"):
            if p.resolve() not in written:
                p.unlink()
    return live


# ----------------------------------------------------------------------------- checks used by the build

def unit_problems(uid):
    """Structural problems that stop the build (check.py adds reading level, parity of wording, media)."""
    errs = []
    d = K.unit_dir(uid)
    for lang in K.LANGS:
        for name in ("story", "explorers", "investigators", "grownups"):
            if not (d / f"{name}.{lang}.md").exists():
                errs.append(f"missing {name}.{lang}.md")
    if errs:
        return errs
    meta = K.unit_meta(uid)
    shots = [s["id"] for s in meta.get("shots", [])]
    for lang in K.LANGS:
        st = K.story(uid, lang)
        if st["shots"] != shots:
            errs.append(f"story.{lang}.md shots {st['shots']} differ from unit.json {shots}")
        for level in K.LEVELS:
            _, text = K.front_matter((d / f"{level}.{lang}.md").read_text(encoding="utf-8"))
            kinds = [k for k, _, _ in K.lesson_blocks(text)]
            order = [K.BLOCK_ORDER.index(k) if k in K.BLOCK_ORDER else -1 for k in kinds]
            if -1 in order:
                errs.append(f"{level}.{lang}.md: unknown block ::: {kinds[order.index(-1)]}")
            elif order != sorted(order):
                errs.append(f"{level}.{lang}.md: blocks out of order ({', '.join(kinds)})")
            for need in K.REQUIRED[level]:
                if need not in kinds:
                    errs.append(f"{level}.{lang}.md: missing ::: {need}")
            for k, arg, _ in K.lesson_blocks(text):
                if k in ("tryit", "check", "opener"):
                    if not K.game_path(arg).exists():
                        errs.append(f"{level}.{lang}.md: ::: {k} {arg} has no kids/games/{arg}.json or play/data/{arg}.json")
    # the same games and quizzes in both languages, level by level
    for level in K.LEVELS:
        sets = []
        for lang in K.LANGS:
            _, text = K.front_matter((d / f"{level}.{lang}.md").read_text(encoding="utf-8"))
            sets.append([(k, a) for k, a, _ in K.lesson_blocks(text) if k in ("opener", "tryit", "check", "words")])
        if [x for x in sets[0] if x[0] != "words"] != [x for x in sets[1] if x[0] != "words"]:
            errs.append(f"{level}: games and quizzes differ between English and Persian")
    return errs


# ----------------------------------------------------------------------------- pieces

def load_sync(uid, lang):
    p = ASSETS_KIDS / "sync" / f"{uid}.{lang}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def art_img(b, root, key, alt, cls="kshot-img"):
    """A picture from assets/kids/art/<key>-<width>.webp, or a drawn placeholder until it exists."""
    w800, w1440 = ASSETS_KIDS / "art" / f"{key}-800.webp", ASSETS_KIDS / "art" / f"{key}-1440.webp"
    if w800.exists():
        srcset = f'{root}assets/kids/art/{key}-800.webp 800w' + (f', {root}assets/kids/art/{key}-1440.webp 1440w' if w1440.exists() else "")
        return (f'<img class="{cls}" src="{root}assets/kids/art/{key}-800.webp" srcset="{srcset}" sizes="(max-width: 760px) 100vw, 720px" '
                f'alt="{esc(alt)}" loading="lazy" decoding="async">')
    return f'<div class="{cls} kph" role="img" aria-label="{esc(alt)}"><span>{esc(alt)}</span></div>'


def role_name(role, lang):
    cast = K.read_json(K.KIDS / "cast.json")
    c = cast.get(role)
    return K.pick(c, lang)["name"] if c else ""


def render_story(b, uid, meta, st, sync, root):
    """The story as an illustrated reading, one picture per shot; with narration, every word carries its time."""
    L, lang = b.L, b.LANG
    times = {}
    if sync:
        times = {ln["id"]: ln for ln in sync.get("lines", [])}
    shots = {s["id"]: K.pick(s, lang) for s in meta.get("shots", [])}
    parts, cur = [], None
    for ln in st["lines"]:
        if ln["shot"] != cur:
            if cur is not None:
                parts.append("</div></figure>")
            cur = ln["shot"]
            s = shots.get(cur, {})
            t = (sync or {}).get("shots", {}).get(cur) if sync else None
            tb = f' data-b="{t}"' if t is not None else ""
            parts.append(f'<figure class="kshot" id="{cur}"{tb}>{art_img(b, root, s.get("art", cur), s.get("alt", ""))}<div class="klines">')
        words = K.words_of(ln["text"])
        tm = times.get(ln["id"])
        if tm and len(tm.get("w", [])) == len(words):
            inner = " ".join(f'<span class="w" data-b="{w[0]}" data-e="{w[1]}">{esc(t)}</span>' for t, w in zip(words, tm["w"]))
            span = f' data-b="{tm["b"]}" data-e="{tm["e"]}"'
        else:
            inner, span = esc(ln["text"]), ""
        who = role_name(ln["role"], lang) if ln["role"] not in ("narrator",) else ""
        tag = f'<b class="who">{esc(who)}</b>' if who else ""
        parts.append(f'<p class="line r-{ln["role"]}" id="{ln["id"]}"{span}>{tag}{inner}</p>')
    if cur is not None:
        parts.append("</div></figure>")
    audio = ""
    if sync:
        audio = (f'<div class="kplayer" data-audio="{root}assets/kids/audio/{esc(sync["file"])}">'
                 f'<button type="button" class="kplay" aria-pressed="false">{L("Listen to the story", "قصه را گوش کن")}</button>'
                 f'<span class="kdur">{b.num(b.mmss(sync.get("duration", 0)))}</span></div>')
    source = K.read_json(K.KIDS / "stories.json").get(meta["story"], {})
    note = K.pick(source, lang).get("note", "") if source else ""
    return (f'<section class="kstory" id="story" aria-labelledby="story-h"><h2 id="story-h"><span class="kicker">{L("The story", "قصه")}</span>'
            f'{esc(st["title"])}</h2>{audio}<div class="kstory-body">{"".join(parts)}</div>'
            + (f'<p class="ksource">{esc(note)}</p>' if note else "") + "</section>")


BLOCK_LABEL = {
    "opener": ("Quick! What would you do?", "زود باش! تو چه می‌کردی؟"),
    "think": ("Think about it", "فکر کن"),
    "bigidea": ("The big idea", "ایدهٔ اصلی"),
    "words": ("New words", "واژه‌های تازه"),
    "tryit": ("Try it!", "امتحان کن!"),
    "check": ("Quick check", "خودت را بسنج"),
    "talk": ("Talk about it", "با هم حرف بزنید"),
    "further": ("Go further", "بیشتر بدان"),
}


def link_rewriter(b, uid):
    fa = b.LANG == "fa"

    def rewrite(href):
        m = re.match(r"^(\d\d-[\w-]+)\.md(#.*)?$", href)
        if m:
            return f"../../guide/{m.group(1)}.html{m.group(2) or ''}"
        m = re.match(r"^deeper:(\d\d-[\w-]+)/([\w-]+)$", href)
        if m:
            if fa and not (K.ROOT / "fa" / "deeper" / m.group(1) / f"{m.group(2)}.html").exists() \
                    and not (K.ROOT / "deeper" / "src-fa" / m.group(1) / f"{m.group(2)}.md").exists():
                return f"../../../deeper/{m.group(1)}/{m.group(2)}.html"
            return f"../../deeper/{m.group(1)}/{m.group(2)}.html"
        m = re.match(r"^kids:([\w-]+)$", href)
        if m:
            return f"../{m.group(1)}/"
        return href
    return rewrite


def render_md(b, md, text, uid):
    out, _ = md.render(text, link_rewriter(b, uid))
    return re.sub(r"\n\s*\n", "\n", out).strip()


def render_lesson(b, md, text, uid, level, words, engines):
    L, lang = b.L, b.LANG

    def block(m):
        kind, arg, inner = m.group(1), (m.group(2) or "").strip(), m.group(3)
        label = L(*BLOCK_LABEL[kind])
        if kind == "words":
            ids = [w.strip() for w in re.split(r"[,\s]+", inner.strip()) if w.strip()]
            cards = "".join(word_card(b, words[w]) for w in ids if w in words)
            content = f'<div class="kwords">{cards}</div>'
        elif kind in ("tryit", "check", "opener"):
            g = K.pick(K.game(arg), lang)
            engines.add(g["engine"])
            engines.update(f'sim:{c["sim"]["kind"]}' for c in for_level(g, level).get("cases", []) if c.get("sim"))
            g = kid_friendly(b, for_level(g, level))
            intro = render_md(b, md, inner, uid) if inner.strip() else ""
            payload = json.dumps(g, ensure_ascii=False).replace("</", "<\\/")
            content = (f'{intro}<div class="kgame" data-game="{esc(arg)}" data-engine="{esc(g["engine"])}" data-unit="{uid}" data-level="{level}">'
                       f'<script type="application/json">{payload}</script>'
                       f'<p class="knojs">{L("This game needs JavaScript turned on.", "این بازی به جاوااسکریپت نیاز دارد.")}</p></div>')
            if kind == "tryit" and arg:
                label = f'{label} <span class="kgame-t">{esc(g.get("title", ""))}</span>'
        else:
            content = render_md(b, md, inner, uid)
        return f'\n\n<section class="kblk k-{kind}"><p class="kblk-k">{label}</p>{content}</section>\n\n'

    text = K.BLOCK.sub(block, text)
    out, _ = md.render(text, link_rewriter(b, uid))
    return out


def kid_friendly(b, g):
    """Gentle verdicts for the case engine on the kids' site (never "wrong"), and no share button."""
    if g.get("engine") == "case":
        g = dict(g, share=False)
        g.setdefault("good", b.L("Well done, detective!", "آفرین، کارآگاه!"))
        g.setdefault("catch", b.L("Not quite. Here's why", "نه دقیقاً. ببین چرا"))
    return g


def for_level(g, level):
    """Keep only the cards, buckets, questions and cases meant for this level (items without "levels" are for every level)."""
    def keep(x):
        return not isinstance(x, dict) or "levels" not in x or level in x["levels"]
    g = dict(g)
    for k in ("cards", "buckets", "items", "cases"):
        if k in g:
            g[k] = [x for x in g[k] if keep(x)]
    return g


def word_card(b, w):
    root = "../../" + ("../" if b.LANG == "fa" else "")
    pic = art_img(b, root, w["art"], w["word"], cls="kword-img") if w.get("art") and (ASSETS_KIDS / "art" / f"{w['art']}-800.webp").exists() else ""
    return f'<div class="kword">{pic}<p class="kw">{esc(w["word"])}</p><p class="kd">{esc(w["def"])}</p></div>'


def level_switch(b, level):
    L = b.L
    def item(lv, label, ages):
        cur = ' aria-current="page"' if lv == level else ""
        return f'<a href="{LEVEL_FILE[lv] if lv != "explorers" else "./"}"{cur} data-set-level="{lv}"><b>{label}</b><span>{ages}</span></a>'
    return (f'<nav class="klevels" aria-label="{L("Choose your level", "سطحت را انتخاب کن")}">'
            + item("explorers", L("Explorers", "کاوشگرها"), L("ages 7–10", "۷ تا ۱۰ سال"))
            + item("investigators", L("Investigators", "کارآگاه‌ها"), L("ages 11–14", "۱۱ تا ۱۴ سال")) + "</nav>")


def unit_pager(b, prev_u, next_u, level, lang):
    L = b.L
    f = LEVEL_FILE[level] if level != "explorers" else ""
    cells = []
    if prev_u:
        cells.append(f'<a class="prev" href="../{prev_u["id"]}/{f}"><span>{L("Previous", "قبلی")}</span>{esc(K.pick(prev_u, lang)["title"])}</a>')
    if next_u:
        cells.append(f'<a class="next" href="../{next_u["id"]}/{f}"><span>{L("Next", "بعدی")}</span>{esc(K.pick(next_u, lang)["title"])}</a>')
    cells.append(f'<a class="home" href="../">{L("All quests", "همهٔ ماجراها")}</a>')
    return f'<nav class="kpager">{"".join(cells)}</nav>'


HUDHUD = ('<svg class="hudhud" viewBox="0 0 120 120" aria-hidden="true">'
          '<path d="M52 30 L40 6 L50 26 L44 2 L56 24 L56 0 L62 26 L70 6 L66 30Z" fill="#F08A24"/>'
          '<path d="M44 8 l3 6M51 4 l2 6M58 2 l1 7M67 8 l-3 6" stroke="#1B2730" stroke-width="3" stroke-linecap="round"/>'
          '<ellipse cx="60" cy="76" rx="32" ry="30" fill="#F4A64A"/>'
          '<path d="M38 70 Q60 64 86 78 Q78 100 52 98 Q40 92 38 70Z" fill="#1B2730"/>'
          '<path d="M44 76h34M46 84h30M50 92h22" stroke="#fff" stroke-width="4" stroke-linecap="round"/>'
          '<circle cx="58" cy="44" r="20" fill="#F8B865"/>'
          '<circle cx="64" cy="40" r="7" fill="#fff"/><circle cx="66" cy="40" r="3.6" fill="#1B2730"/><circle cx="67.2" cy="38.8" r="1.2" fill="#fff"/>'
          '<path d="M76 46 Q98 50 112 64 Q94 56 76 52Z" fill="#5A3A1E"/>'
          '<circle cx="52" cy="50" r="3.5" fill="#F37A8B" opacity=".6"/>'
          '<path d="M50 104l-4 12M66 104l4 12" stroke="#5A3A1E" stroke-width="4" stroke-linecap="round"/></svg>')

QUESTIONS = [("What exactly is being said?", "دقیقاً چه گفته می‌شود؟"), ("How do they know?", "از کجا می‌داند؟"),
             ("What else could explain it?", "چه توضیحِ دیگری ممکن است؟"), ("How sure should I be?", "چقدر باید مطمئن باشم؟")]


def home_body(b, data, quests, arcade):
    import site_play
    L, num, lang = b.L, b.num, b.LANG
    hello = L("Hi! I'm Hudhud. Let's find out how we know things!", "سلام! من هدهدم. بیا با هم بفهمیم از کجا چیزها را می‌دانیم!")
    qs = "".join(f'<li class="kq{i}"><b>{num(i)}</b><span>{L(en, fa)}</span></li>' for i, (en, fa) in enumerate(QUESTIONS, 1))
    games = "".join(f'<li class="gcard c-{a["color"]}"><a href="arcade/{a["id"]}/" data-unit-link="arcade/{a["id"]}">'
                    f'<span class="gcard-art">{site_play.ART.get(a.get("art"), "")}</span><b>{esc(a["title"])}</b><span>{esc(a["hook"])}</span>'
                    f'<em class="pgo">{L("Play", "بازی کن")}</em></a></li>' for a in arcade)
    rows = []
    for q in data["quests"]:
        qq = K.pick(q, lang)
        stops = []
        for u in [u for u in data["units"] if u["quest"] == q["id"]]:
            uu = K.pick(u, lang)
            t, hook = esc(uu["title"]), esc(uu.get("hook", ""))
            if published(u):
                stops.append(f'<li class="kstop on"><a href="{u["id"]}/" data-unit-link="{u["id"]}"><b>{num(u["n"])}</b>'
                             f'<span class="khook">{hook}</span><span class="kstop-t">{t}</span>'
                             f'<em class="pgo">{L("Play", "بازی کن")}</em><i class="kstop-stars" data-unit="{u["id"]}"></i></a></li>')
            else:
                stops.append(f'<li class="kstop"><span class="soon"><b>{num(u["n"])}</b><span class="khook">{hook}</span>'
                             f'<span class="kstop-t">{t}</span><i>{L("coming soon", "به‌زودی")}</i></span></li>')
        rows.append(f'<section class="kquest q{q["n"]}"><h3><span class="kicker">{L("Quest", "ماجرای")} {num(q["n"])}</span>{esc(qq["title"])}</h3>'
                    f'<p>{esc(qq.get("blurb", ""))}</p><ol class="ktrail">{"".join(stops)}</ol></section>')
    return (f'<main id="main" class="kmain khome"><header class="khero"><div class="kblobs" aria-hidden="true"><i></i><i></i><i></i><i></i></div>'
            f'<div class="khero-mascot">{HUDHUD}<p class="kbubble">{hello}</p></div><h1>{L("How do you know?", "از کجا می‌دانی؟")}</h1>'
            f'<p class="kdek">{L("Stories, games and puzzles about the biggest little question in the world.", "قصه، بازی و معما دربارهٔ کوچک‌ترین سؤالِ بزرگِ دنیا.")}</p>'
            f'<div class="kchoose" role="group" aria-label="{L("Choose your level", "سطحت را انتخاب کن")}">'
            f'<button type="button" data-set-level="explorers"><b>{L("Explorers", "کاوشگرها")}</b><span>{L("ages 7–10", "۷ تا ۱۰ سال")}</span></button>'
            f'<button type="button" data-set-level="investigators"><b>{L("Investigators", "کارآگاه‌ها")}</b><span>{L("ages 11–14", "۱۱ تا ۱۴ سال")}</span></button></div>'
            f'<p class="ktotal" aria-live="polite"></p></header>'
            + (f'<section class="karcade"><h2>{L("Play now", "حالا بازی کن")}</h2><ul class="ggrid">{games}</ul></section>' if games else "")
            + f'<section class="kmap"><h2>{L("Your quests", "ماجراهای تو")}</h2>{"".join(rows)}</section>'
            f'<section class="kfour"><h2>{L("The detective questions", "سؤال‌های کارآگاهی")}</h2><ol>{qs}</ol></section>'
            f'<p class="kmore"><a href="words/">{L("Picture dictionary", "واژه‌نامهٔ تصویری")}</a><a href="books/">{L("Book club", "باشگاهِ کتاب")}</a>'
            f'<a href="grownups/">{L("For grown-ups", "برای بزرگ‌ترها")}</a></p></main>')


def words_body(b, live, words):
    L = b.L
    used = []
    for u in live:
        for level in K.LEVELS:
            _, text = K.front_matter((K.unit_dir(u["id"]) / f"{level}.{b.LANG}.md").read_text(encoding="utf-8"))
            for k, _, inner in K.lesson_blocks(text):
                if k == "words":
                    used += [w.strip() for w in re.split(r"[,\s]+", inner.strip()) if w.strip()]
    ids = list(dict.fromkeys(w for w in used if w in words))
    cards = "".join(word_card(b, words[w]) for w in sorted(ids, key=lambda w: words[w]["word"]))
    return (f'<main id="main" class="kmain"><header class="khead"><h1>{L("Picture dictionary", "واژه‌نامهٔ تصویری")}</h1>'
            f'<p>{L("Every thinking word from the lessons, in plain words.", "همهٔ واژه‌های فکری درس‌ها، به زبانِ ساده.")}</p></header>'
            f'<div class="kwords kwords-all">{cards}</div></main>')


def books_body(b):
    L, lang = b.L, b.LANG
    books = [K.pick(x, lang) for x in K.read_json(K.KIDS / "books.json")]
    cards = []
    for bk in books:
        qs = "".join(f"<li>{esc(q)}</li>" for q in bk.get("questions", []))
        link = (f'<p class="kbook-find"><a href="{esc(bk["catalogue"])}" data-leave rel="noopener">'
                f'{L("Find it in a library catalogue", "در فهرستِ کتابخانه پیدایش کن")}</a></p>') if bk.get("catalogue") else ""
        cards.append(f'<article class="kbook"><p class="kicker">{esc(bk.get("ages", ""))} · {L("Unit", "درس")} {b.num(bk.get("unit", ""))}</p>'
                     f'<h3>{esc(bk["title"])}</h3><p class="kby">{esc(bk["author"])}, {b.num(bk["year"])}</p>'
                     f'<p>{esc(bk.get("why", ""))}</p><p class="kblk-k">{L("Talk about it", "با هم حرف بزنید")}</p><ul>{qs}</ul>{link}</article>')
    return (f'<main id="main" class="kmain"><header class="khead"><h1>{L("Book club", "باشگاهِ کتاب")}</h1>'
            f'<p>{L("Famous books to read alongside the quests. We never copy them: borrow them from a library or a friend, then use the questions to talk.", "کتاب‌های معروف برای خواندن همراهِ ماجراها. ما از آن‌ها رونوشت نمی‌گذاریم: از کتابخانه یا دوست قرض بگیر و بعد با این پرسش‌ها درباره‌شان حرف بزنید.")}</p>'
            f'</header><div class="kbooks">{"".join(cards)}</div></main>')


def grownups_body(b, md, data, live):
    L, lang = b.L, b.LANG
    _, text = K.front_matter((K.KIDS / f"grownups.{lang}.md").read_text(encoding="utf-8"))
    body, _ = md.render(text, link_rewriter(b, ""))
    units = "".join(f'<li><a href="../{u["id"]}/grownups.html">{esc(K.pick(u, lang)["title"])}</a></li>' for u in live)
    return (f'<main id="main" class="kmain"><header class="khead"><h1>{L("For grown-ups", "برای بزرگ‌ترها")}</h1></header>'
            f'<div class="prose kgrownups">{body}<h2>{L("Notes for each unit", "یادداشتِ هر درس")}</h2><ul>{units}</ul></div></main>')
