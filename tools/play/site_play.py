"""Baloney Detector (/play/ and /fa/play/): thinking games for teens and adults, built on the same game engines
as the kids' site (assets/games/). Called by tools/site/build.py once per language: build(b, art, md).

play/games.json   the catalogue: every game card on the home page (live or coming soon), with its colour, art and
                  "go deeper" links
play/data/<id>.json   a game's data (English at the top level, Persian under "fa"; cases carry "levels", and the
                  levels "explorers" and "investigators" are for the kids' site, "play" for this one)

Pages: play/index.html (the game cards) and play/<id>/index.html for every live game. Shell: safe_shell
(section "play"): no sign-in, notes or AI scripts, a content-security policy, progress only in this browser."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kids"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenes"))
import kidslib as K  # noqa: E402
import site_kids  # noqa: E402
import scenes as SC  # noqa: E402

ROOT = K.ROOT
PLAY = ROOT / "play"
ENGINE_JS = {"case": "games/case.js", "sorter": "kids/games/sorter.js", "quiz": "kids/games/quiz.js"}
SIM_JS = {"confounder": "games/sims/confounder.js"}


def esc(s):
    return html.escape(str(s), quote=True)


def catalogue():
    return K.read_json(PLAY / "games.json")["games"]


def game_data(gid):
    return K.read_json(PLAY / "data" / f"{gid}.json")


def art_src(root, key, width=800):
    """The URL of an illustration (key "kids/<id>" or "play/<id>", made by tools/art/make_art.py), or None."""
    base, iid = key.split("/", 1)
    if not (ROOT / "assets" / base / "art" / f"{iid}-{width}.webp").exists():
        return None
    return f"{root}assets/{base}/art/{iid}-{width}.webp"


def picture(root, key, alt="", cls="", sizes="(max-width: 760px) 100vw, 760px", lazy=True, widths=(800, 1440)):
    """An <img> for an illustration at the widths that exist, or "" if it hasn't been made yet."""
    urls = [(w, art_src(root, key, w)) for w in widths]
    urls = [(w, u) for w, u in urls if u]
    if not urls:
        return ""
    srcset = ", ".join(f"{u} {w}w" for w, u in urls)
    loading = ' loading="lazy"' if lazy else ""
    return f'<img class="{cls}" src="{urls[0][1]}" srcset="{srcset}" sizes="{sizes}" alt="{esc(alt)}"{loading} decoding="async">'


def with_art(root, g):
    """Cases with an "art" key get an "img" ({src, srcset, alt}) for the case engine, once the picture exists."""
    if "cases" not in g:
        return g
    cases = []
    for c in g["cases"]:
        small = art_src(root, c["art"]) if c.get("art") else None
        if small:
            big = art_src(root, c["art"], 1440)
            c = dict(c, img={"src": small, "srcset": f"{small} 800w" + (f", {big} 1440w" if big else ""), "alt": c.get("alt", "")})
        cases.append(c)
    return dict(g, cases=cases)


def scripts_for(b, root, g):
    """The engine and simulation scripts a game needs."""
    files = [ENGINE_JS[g["engine"]]]
    sims = sorted({c["sim"]["kind"] for c in g.get("cases", []) if c.get("sim")})
    files += [SIM_JS[s] for s in sims]
    if any(c.get("stages") for c in g.get("cases", [])):  # drawn stages need the puppets and the stage code
        files += ["scenes/puppets.js", "scenes/deck.js"]
    return "".join(f'<script src="{b.av(root, f)}" defer></script>' for f in files)


def game_box(b, gid, g, level, unit="play"):
    """A game, mounted by assets/games/core.js; its data travel inside the page so it works offline."""
    payload = json.dumps(g, ensure_ascii=False).replace("</", "<\\/")
    return (f'<div class="kgame" data-game="{esc(gid)}" data-engine="{esc(g["engine"])}" data-unit="{esc(unit)}" data-level="{esc(level)}">'
            f'<script type="application/json">{payload}</script>'
            f'<p class="knojs">{b.L("This game needs JavaScript turned on.", "این بازی به جاوااسکریپت نیاز دارد.")}</p></div>')


def card(b, c, root=""):
    L = b.L
    pic = picture(root, c["img"], sizes="(max-width: 700px) 100vw, 360px", widths=(800,)) if c.get("img") else ""
    art = f'<span class="gcard-art{" pic" if pic else ""}">{pic or ART.get(c.get("art"), "")}</span>'
    if c.get("live"):
        meta = f'<small>{esc(c["time"])}</small>' if c.get("time") else ""
        return (f'<li class="gcard c-{c["color"]}"><a href="{c["id"]}/">{art}<b>{esc(c["title"])}</b>'
                f'<span>{esc(c["hook"])}</span>{meta}<em class="pgo">{L("Play", "بازی کن")}</em></a></li>')
    return (f'<li class="gcard c-{c["color"]} soon"><div>{art}<b>{esc(c["title"])}</b><span>{esc(c["hook"])}</span>'
            f'<em class="psoon">{L("Coming soon", "به‌زودی")}</em></div></li>')


def build(b, art, md):
    L, lang = b.L, b.LANG
    out_dir = b.OUT() / "play"
    written = set()
    games = [K.pick(c, lang) for c in catalogue()]
    problems = []
    for c in games:
        if c.get("live"):
            problems += [f"{c['id']}: {p}" for p in game_problems(c["id"])]
    if problems:
        raise SystemExit("play: problems in live games:\n  " + "\n  ".join(problems))

    def ppage(rel, **kw):
        b.page(f"play/{rel}", safe="play", **kw)
        written.add((b.OUT() / "play" / rel).resolve())

    live = [c for c in games if c.get("live")]
    for n, c in enumerate(live, 1):
        root = b.up(2)
        h = b.home(root)
        g = with_art(root, site_kids.for_level(K.pick(game_data(c["id"]), lang), "play"))
        g["masthead"] = L("The Daily Claim", "ادعای روز")
        learn = "".join(f'<li><a href="{h}{esc(x["href"])}">{esc(x["title"])}</a></li>' for x in c.get("learn", []))
        body = (f'<main id="main" class="pdeck pgame c-{c["color"]}"><h1 class="sr-h">{esc(c["title"])}</h1>'
                f'{game_box(b, c["id"], g, "play")}'
                + (f'<section class="plearn"><h2>{L("Want to go deeper?", "می‌خواهید عمیق‌تر شوید؟")}</h2><ul>{learn}</ul></section>' if learn else "")
                + '</main>')
        ppage(f"{c['id']}/index.html", root=root, title=c["title"], desc=c["hook"], body=body,
              extra_scripts=scripts_for(b, root, g))

    root = b.up(1)
    h = b.home(root)
    raw = SC.load(PLAY / "home.deck.json", lang)
    scenes = []
    for sc in raw:
        if sc.pop("auto", False):
            sc["links"] = [{"t": c["title"], "sub": c["hook"], "href": f'{c["id"]}/'} for c in games if c.get("live")]
            soon = [c["title"] for c in games if not c.get("live")]
            if soon:
                sc["text"] = [sc["text"], L("Coming soon: ", "به‌زودی: ") + " · ".join(soon)]
        scenes.append(sc)
    probs = SC.validate(scenes)
    if probs:
        raise SystemExit("play home deck:\n  " + "\n  ".join(probs))
    deck = SC.render(scenes, ui={"next": L("Next", "بعدی"), "back": L("Back", "قبلی"), "again": L("Start again", "دوباره از اول")}, attrs='data-unit="play-home"')
    body = f'<main id="main" class="pdeck"><h1 class="sr-h">{L("Baloney Detector", "چرندسنج")}</h1>{deck}</main>'
    ppage("index.html", root=root, title=L("Baloney Detector", "چرندسنج"),
          desc=L("Games for people who enjoy being wrong: spot the trick in the headline, the graph and the study.",
                 "بازی برای کسانی که از اشتباه کردن خوششان می‌آید: ترفندِ تیتر و نمودار و پژوهش را پیدا کنید."),
          body=body, extra_scripts=f'<script src="{b.av(root, "scenes/puppets.js")}" defer></script><script src="{b.av(root, "scenes/deck.js")}" defer></script>')

    if out_dir.exists():
        for p in out_dir.rglob("*.html"):
            if p.resolve() not in written:
                p.unlink()
    return live


# ----------------------------------------------------------------------------- checks (also run by tools/play/check.py)

NON_TEXT = {"id", "engine", "kind", "art", "img", "color", "who", "what", "bg", "face", "anim", "stages", "href", "levels", "best", "unit", "sim", "controls", "params", "values", "hi"}


def missing_fa(obj, path=""):
    """Paths of English strings (and lists of strings) with no Persian counterpart under the nearest "fa"."""
    out = []
    if isinstance(obj, list):
        for i, x in enumerate(obj):
            out += missing_fa(x, f"{path}[{i}]")
    elif isinstance(obj, dict):
        fa = obj.get("fa") if isinstance(obj.get("fa"), dict) else {}
        for k, v in obj.items():
            if k == "fa" or (k in NON_TEXT and not isinstance(v, dict)):
                continue
            if isinstance(v, str) and v.strip() and not v.strip().isdigit() and k not in fa:
                out.append(f"{path}.{k}")
            elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                if not (isinstance(fa.get(k), list) and len(fa[k]) == len(v)):
                    out.append(f"{path}.{k}")
            elif isinstance(v, (dict, list)):
                out += missing_fa(v, f"{path}.{k}")
    return out


def case_problems(g):
    errs = []
    if g.get("engine") != "case":
        return errs
    for c in g.get("cases", []):
        cid = c.get("id", "?")
        ids = [ch.get("id") for ch in c.get("choices", [])]
        if len(ids) < 2 or len(set(ids)) != len(ids):
            errs.append(f"case {cid}: needs two or more choices with different ids")
        for ch in c.get("choices", []):
            if not ch.get("why"):
                errs.append(f"case {cid}: choice {ch.get('id')} has no 'why'")
        for b_ in c.get("best", []):
            if b_ not in ids:
                errs.append(f"case {cid}: best answer {b_!r} is not a choice")
        if not c.get("best"):
            errs.append(f"case {cid}: no best answer")
        for cl in c.get("clues", []):
            ch_ = cl.get("chart")
            if ch_ and ch_.get("kind") not in ("bars", "strip"):
                errs.append(f"case {cid}: unknown chart kind {ch_.get('kind')!r}")
            if ch_ and ch_.get("kind") == "strip" and not (0 <= ch_.get("hi", -1) < len(ch_.get("values", []))):
                errs.append(f"case {cid}: strip chart picks out a value that isn't there")
        if (c.get("surprise") or c.get("sandbox")) and not c.get("sim"):
            errs.append(f"case {cid}: a surprise or sandbox needs a 'sim'")
        if c.get("sim") and c["sim"].get("kind") not in SIM_JS:
            errs.append(f"case {cid}: unknown simulation {c['sim'].get('kind')!r}")
        for k in (c.get("sandbox") or {}).get("controls", []):
            if k not in ("link", "effect", "n", "coin", "fix", "show"):
                errs.append(f"case {cid}: unknown sandbox control {k!r}")
        if c.get("stages"):
            for lang in ("en", "fa"):
                stg = K.pick(c["stages"], lang)
                flat = [*(stg.get("clues") or []), *[stg[k] for k in ("twist", "verdict") if stg.get(k)]]
                errs += [f"case {cid} stages [{lang}]: {e}" for e in SC.validate(flat, need_text=False)]
            if len(c["stages"].get("clues", [])) > len(c.get("clues", [])):
                errs.append(f"case {cid}: more drawn clue stages than clues")
        for lv in c.get("levels", []):
            if lv not in ("explorers", "investigators", "play"):
                errs.append(f"case {cid}: unknown level {lv!r}")
    return errs


def game_problems(gid):
    p = PLAY / "data" / f"{gid}.json"
    if not p.exists():
        return [f"no data file play/data/{gid}.json"]
    g = game_data(gid)
    errs = [f"no Persian for {x}" for x in missing_fa(g)]
    errs += case_problems(g)
    if g.get("engine") not in ENGINE_JS:
        errs.append(f"unknown engine {g.get('engine')!r}")
    elif not site_kids.for_level(g, "play").get("cases", g.get("items", g.get("cards"))):
        errs.append("nothing for the 'play' level")
    return errs


# ----------------------------------------------------------------------------- card art (inline SVG, no text inside)

_S = 'stroke="#1E2A3B" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"'
ART = {
    "detective": (f'<svg viewBox="0 0 160 120" aria-hidden="true"><g {_S}>'
                  '<path d="M30 52h56v24a22 22 0 0 1-22 22h-12a22 22 0 0 1-22-22z" fill="#fff"/>'
                  '<path d="M86 60h7a9 9 0 0 1 0 18h-7" fill="none"/>'
                  '<path d="M46 42c-5-6 5-10 0-17M62 42c-5-6 5-10 0-17" fill="none"/>'
                  '<circle cx="112" cy="50" r="21" fill="#FFF3C7"/><path d="M127 65l17 17" stroke-width="9"/>'
                  '<path d="M104 46a9 9 0 0 1 9-8" fill="none" stroke="#fff" stroke-width="4"/></g></svg>'),
    "feet": (f'<svg viewBox="0 0 160 120" aria-hidden="true"><g {_S}>'
             '<ellipse cx="44" cy="74" rx="15" ry="24" fill="#fff"/><ellipse cx="78" cy="62" rx="12" ry="19" fill="#fff"/>'
             '<circle cx="112" cy="50" r="21" fill="#FFF3C7"/><path d="M127 65l17 17" stroke-width="9"/></g>'
             '<g fill="#fff" stroke="#1E2A3B" stroke-width="3"><circle cx="34" cy="42" r="5"/><circle cx="45" cy="39" r="5"/><circle cx="56" cy="43" r="4.5"/>'
             '<circle cx="70" cy="37" r="4"/><circle cx="79" cy="35" r="4"/><circle cx="88" cy="38" r="3.5"/></g>'
             '<path d="M104 46a9 9 0 0 1 9-8" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/></svg>'),
    "dice": (f'<svg viewBox="0 0 160 120" aria-hidden="true"><g {_S}>'
             '<rect x="24" y="34" width="54" height="54" rx="12" fill="#fff" transform="rotate(-12 51 61)"/>'
             '<rect x="84" y="26" width="54" height="54" rx="12" fill="#FFF3C7" transform="rotate(10 111 53)"/></g>'
             '<g fill="#1E2A3B"><circle cx="40" cy="52" r="5"/><circle cx="52" cy="62" r="5"/><circle cx="63" cy="72" r="5"/>'
             '<circle cx="100" cy="41" r="5"/><circle cx="123" cy="45" r="5"/><circle cx="97" cy="62" r="5"/><circle cx="120" cy="66" r="5"/></g></svg>'),
    "chart": (f'<svg viewBox="0 0 160 120" aria-hidden="true"><g {_S}>'
              '<path d="M30 20v80h106" fill="none"/><path d="M22 66l16-6-16-6 16-6" fill="none"/>'
              '<rect x="46" y="70" width="18" height="30" fill="#fff"/><rect x="74" y="56" width="18" height="44" fill="#fff"/>'
              '<rect x="102" y="26" width="18" height="74" fill="#FFF3C7"/></g>'
              '<circle cx="124" cy="24" r="13" fill="none" stroke="#fff" stroke-width="4" stroke-dasharray="6 5"/></svg>'),
    "trust": (f'<svg viewBox="0 0 160 120" aria-hidden="true"><g {_S}>'
              '<circle cx="46" cy="62" r="26" fill="#fff"/><circle cx="114" cy="62" r="26" fill="#FFF3C7"/>'
              '<path d="M38 70q8 7 16 0M106 72q8-6 16 0" fill="none"/>'
              '<circle cx="80" cy="30" r="12" fill="#FFC92E"/><path d="M62 30h-6M104 30h-6" fill="none"/></g>'
              '<g fill="#1E2A3B"><circle cx="38" cy="56" r="3.5"/><circle cx="54" cy="56" r="3.5"/><circle cx="106" cy="56" r="3.5"/><circle cx="122" cy="56" r="3.5"/></g></svg>'),
    "slots": (f'<svg viewBox="0 0 160 120" aria-hidden="true"><g {_S}>'
              '<rect x="24" y="26" width="98" height="76" rx="14" fill="#fff"/>'
              '<rect x="34" y="44" width="22" height="34" rx="6" fill="#FFF3C7"/><rect x="62" y="44" width="22" height="34" rx="6" fill="#FFF3C7"/>'
              '<rect x="90" y="44" width="22" height="34" rx="6" fill="#FFF3C7"/><path d="M122 60h12V28" fill="none"/></g>'
              '<circle cx="134" cy="24" r="8" fill="#FF4F8B" stroke="#1E2A3B" stroke-width="4"/>'
              '<g fill="#1E2A3B"><circle cx="45" cy="61" r="5"/><circle cx="73" cy="61" r="5"/></g>'
              '<path d="M97 56q4-6 8 0t-4 8v2" fill="none" stroke="#1E2A3B" stroke-width="3.5" stroke-linecap="round"/></svg>'),
    "news": (f'<svg viewBox="0 0 160 120" aria-hidden="true"><g {_S}>'
             '<rect x="26" y="22" width="84" height="80" rx="8" fill="#fff"/><path d="M38 38h60M38 52h44M38 64h52M38 76h36M38 88h48" fill="none"/>'
             '<circle cx="118" cy="40" r="22" fill="#FFC92E"/><path d="M118 28v12" fill="none"/></g>'
             '<circle cx="118" cy="51" r="3.5" fill="#1E2A3B"/></svg>'),
}
