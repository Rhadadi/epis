"""Episodes of the kids' site: short animated films the child plays inside (kids/episodes/<id>.json, media from
tools/video/episode.py, player assets/games/episode.js). Each is published at kids/watch/<id>/ (Explorers) and
kids/watch/<id>/investigators.html, like the arcade games."""
import html
import json

import kidslib as K

LIST = K.KIDS / "episodes" / "list.json"
MEDIA = K.ROOT / "assets" / "kids" / "episodes"
LEVEL_FILE = {"explorers": "index.html", "investigators": "investigators.html"}


def live():
    """The episodes to publish, in order: listed, and with their media made."""
    if not LIST.exists():
        return []
    out = []
    for e in K.read_json(LIST)["episodes"]:
        ep = K.read_json(K.KIDS / "episodes" / f"{e['id']}.json")
        m = MEDIA / ep["id"] / "media.json"
        if m.exists() and all(c["id"] in json.loads(m.read_text(encoding="utf-8"))["clips"] for c in ep["clips"]):
            out.append({**e, "ep": ep})
    return out


def loc(x, lang):
    """{"en": …, "fa": …} pairs anywhere in the episode become the one language."""
    if isinstance(x, dict):
        if set(x) <= {"en", "fa"} and "en" in x:
            return x.get(lang, x["en"])
        return {k: loc(v, lang) for k, v in x.items()}
    if isinstance(x, list):
        return [loc(v, lang) for v in x]
    return x


def data_of(ep, level, lang, root, kids_root):
    """What the player needs, in one language and for one level, with the media URLs."""
    media = json.loads((MEDIA / ep["id"] / "media.json").read_text(encoding="utf-8"))
    base = f"{root}assets/kids/episodes/{ep['id']}/"
    cast = K.read_json(K.KIDS / "cast.json")
    names = {r: K.pick(cast[r], lang)["name"] for r in ep["voices"][lang] if r in cast}
    clips = {}
    for cid, m in media["clips"].items():
        v = m["voice"][lang]
        clips[cid] = {"video": f"{base}{cid}.mp4", "first": f"{base}{cid}.first.webp", "last": f"{base}{cid}.last.webp",
                      "dur": m["dur"], "voice": {"src": f"{base}{cid}.{lang}.mp3", "dur": v["dur"], "lines": v["lines"]}}
    lines = {k: {"who": ln["who"], "t": ln[lang], "src": f"{base}{k}.{lang}.mp3", "dur": media["lines"][k][lang]["dur"]}
             for k, ln in ep["lines"].items()}
    steps = []
    for s in ep["steps"]:
        if s.get("levels") and level not in s["levels"]:
            continue
        s = loc(s, lang)
        if s.get("do") == "finish":
            s["card"] = {"title": s["card"]["title"], "text": s["card"][level]}
            if s.get("next"):
                n = s["next"]
                s["next"] = {"t": n["t"], "href": f'{kids_root}arcade/{n["game"]}/{"" if level == "explorers" else LEVEL_FILE[level]}',
                             "img": f'{root}assets/kids/art/{n["img"].split("/")[-1]}-800.webp' if n.get("img") else None}
        steps.append(s)
    used = {s["clip"] for s in steps if s.get("clip")}
    p = K.pick(ep, lang)
    return {"id": ep["id"], "title": p["title"], "hook": p["hook"], "names": names, "steps": steps,
            "lines": lines, "clips": {k: v for k, v in clips.items() if k in used}}


def problems(ep):
    """What is wrong with an episode file (for tools/kids/check.py)."""
    errs = []
    clips = {c["id"] for c in ep["clips"]}
    ids = {s["id"] for s in ep["steps"]}
    for c in ep["clips"]:
        for ln in c["lines"]:
            if not ln.get("en") or not ln.get("fa"):
                errs.append(f"{ep['id']}: clip {c['id']} has a line without both languages")
    for k, ln in ep["lines"].items():
        if not ln.get("en") or not ln.get("fa"):
            errs.append(f"{ep['id']}: line {k} needs English and Persian")
    for s in ep["steps"]:
        if s.get("clip") and s["clip"] not in clips:
            errs.append(f"{ep['id']}: step {s['id']} plays unknown clip {s['clip']}")
        for key in ("say", "after", "miss"):
            if s.get(key) and s[key] not in ep["lines"]:
                errs.append(f"{ep['id']}: step {s['id']} says unknown line {s[key]}")
        for o in s.get("options", []):
            if o.get("go") and o["go"] not in ids:
                errs.append(f"{ep['id']}: step {s['id']} goes to unknown step {o['go']}")
            if o.get("say") and o["say"] not in ep["lines"]:
                errs.append(f"{ep['id']}: step {s['id']} option {o['id']} says unknown line {o['say']}")
        if s.get("rewind") and s["rewind"] not in ids:
            errs.append(f"{ep['id']}: step {s['id']} rewinds to unknown step {s['rewind']}")
        if s.get("do") == "choose" and not any(o.get("right") or not o.get("retry") for o in s["options"]):
            errs.append(f"{ep['id']}: step {s['id']} has no way on")
        if s.get("do") == "drag" and sorted(c["to"] for c in s["cards"]) != list(range(len(s["targets"]))):
            errs.append(f"{ep['id']}: step {s['id']} cards do not match targets one to one")
    return errs


def page_body(b, e, level, root, kids_root):
    ep = e["ep"]
    data = data_of(ep, level, b.LANG, root, kids_root)
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    p = K.pick(ep, b.LANG)
    nojs = html.escape(b.L("This film needs JavaScript to play.", "برای پخشِ این فیلم جاوااسکریپت لازم است."))
    return (f'<main id="main" class="pepisode"><h1 class="sr-h">{html.escape(p["title"])}</h1>'
            f'<div class="kgame" data-game="{ep["id"]}" data-engine="episode" data-unit="watch" data-level="{level}">'
            f'<p class="knojs">{nojs}</p><script type="application/json">{blob}</script></div></main>')
