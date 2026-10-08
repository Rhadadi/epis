"""Scene decks, build side (the browser side is assets/scenes/deck.js and puppets.js).

A deck is a list of scenes, written as JSON with English at the top level and Persian under "fa" (the same
convention as the games). This module checks scenes against assets/scenes/vocab.json and writes a deck's HTML:
a plain list of the scenes (what you get without JavaScript, and in print) plus the JSON that deck.js turns into the
stage. Kids' units, Baloney Detector and the guide each expand their own special scenes (story, words, games, …)
into ordinary scenes first and then call render().

Scene: {id, bg, pic{src,srcset,alt}, actors[{id,who,x,y,s,face,anim,say,flip,z}], props[{id,what,x,y,s,anim,z}], label,
        text (string or list), lines[{role,who,t,w[[word,b,e]…]}], list[], cards[{word,def,img,eg}], links[{t,href}],
        ask{q,who,options[{t,ok,why,face}]}, game (id; the box is passed to render), audio[b,e], anchor, end, nostage, next}"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VOCAB = json.loads((ROOT / "assets" / "scenes" / "vocab.json").read_text(encoding="utf-8"))
TEXT_KEYS = {"text", "label", "say", "q", "t", "why", "next", "list", "def", "word", "eg"}


def esc(s):
    return html.escape(str(s), quote=True)


def rich(s):
    """The tiny markup of scene text: **bold** and *italic* (everything else is escaped)."""
    import re
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)


def missing_fa(obj, path=""):
    """Paths of English text with no Persian under the nearest "fa" (same idea as the games' check)."""
    out = []
    if isinstance(obj, list):
        for i, x in enumerate(obj):
            out += missing_fa(x, f"{path}[{i}]")
    elif isinstance(obj, dict):
        fa = obj.get("fa") if isinstance(obj.get("fa"), dict) else {}
        for k, v in obj.items():
            if k == "fa":
                continue
            if k in TEXT_KEYS and isinstance(v, (str, list)) and v and k not in fa:
                if isinstance(v, str) and not v.strip():
                    continue
                out.append(f"{path}.{k}")
            elif isinstance(v, (dict, list)) and k not in ("fa",):
                out += missing_fa(v, f"{path}.{k}")
    return out


def validate(scenes, need_text=True):
    """Problems in a list of picked (one-language) scenes (need_text=False: stages, which only draw)."""
    errs, seen = [], set()
    for i, sc in enumerate(scenes):
        w = f"scene {sc.get('id', i + 1)}"
        sid = sc.get("id", f"stage{i + 1}" if not need_text else None)
        if not sid:
            errs.append(f"{w}: no id")
        elif sid in seen:
            errs.append(f"{w}: duplicate id")
        seen.add(sid)
        if sc.get("bg") and sc["bg"] not in VOCAB["bgs"]:
            errs.append(f"{w}: unknown background {sc['bg']!r}")
        ids = set()
        for a in sc.get("actors", []):
            if a.get("who") not in VOCAB["actors"]:
                errs.append(f"{w}: unknown character {a.get('who')!r}")
            if a.get("face", "happy") not in VOCAB["faces"]:
                errs.append(f"{w}: unknown face {a.get('face')!r}")
            if a.get("anim", "none") not in VOCAB["anims"]:
                errs.append(f"{w}: unknown animation {a.get('anim')!r}")
            for k in ("id", "x", "y"):
                if a.get(k) is None:
                    errs.append(f"{w}: actor without {k}")
            if a.get("id") in ids:
                errs.append(f"{w}: two things with id {a.get('id')!r}")
            ids.add(a.get("id"))
        for p in sc.get("props", []):
            if p.get("what") not in VOCAB["props"]:
                errs.append(f"{w}: unknown prop {p.get('what')!r}")
            if p.get("anim", "none") not in VOCAB["anims"]:
                errs.append(f"{w}: unknown animation {p.get('anim')!r}")
            if p.get("id") in ids:
                errs.append(f"{w}: two things with id {p.get('id')!r}")
            ids.add(p.get("id"))
        for t in [*sc.get("actors", []), *sc.get("props", [])]:
            for k in ("x", "y"):
                if t.get(k) is not None and not (-10 <= t[k] <= 110):
                    errs.append(f"{w}: {t.get('id')} {k}={t[k]} is off the stage")
        a = sc.get("ask")
        if a:
            oks = sum(1 for o in a.get("options", []) if o.get("ok"))
            if oks != 1:
                errs.append(f"{w}: a question needs exactly one right option")
        if need_text and not any(sc.get(k) for k in ("text", "lines", "list", "cards", "ask", "game", "links")):
            errs.append(f"{w}: nothing to read")
    return errs


def _li(sc):
    """One scene as plain HTML (no JavaScript, print)."""
    parts = []
    if sc.get("label"):
        parts.append(f'<p class="dlabel">{esc(sc["label"])}</p>')
    if sc.get("pic"):
        parts.append(f'<img src="{esc(sc["pic"]["src"])}" alt="{esc(sc["pic"].get("alt", ""))}" loading="lazy">')
    for ln in sc.get("lines", []):
        who = f'<b class="who">{esc(ln["who"])}</b> ' if ln.get("who") else ""
        txt = " ".join(w[0] for w in ln["w"]) if ln.get("w") else ln.get("t", "")
        parts.append(f'<p>{who}{esc(txt)}</p>')
    t = sc.get("text")
    for x in ([t] if isinstance(t, str) else t or []):
        parts.append(f"<p>{rich(x)}</p>")
    if sc.get("list"):
        parts.append("<ul>" + "".join(f"<li>{rich(x)}</li>" for x in sc["list"]) + "</ul>")
    if sc.get("cards"):
        parts.append("<ul>" + "".join(f'<li><b>{esc(c["word"])}</b>: {rich(c["def"])}</li>' for c in sc["cards"]) + "</ul>")
    if sc.get("ask"):
        parts.append(f'<p><b>{esc(sc["ask"].get("q", ""))}</b></p><ul>' + "".join(f'<li>{esc(o["t"])}</li>' for o in sc["ask"]["options"]) + "</ul>")
    if sc.get("links"):
        parts.append("<ul>" + "".join(f'<li><a href="{esc(l["href"])}">{esc(l["t"])}</a></li>' for l in sc["links"]) + "</ul>")
    return parts


def render(scenes, boxes=None, ui=None, audio_src=None, attrs=""):
    """The deck's HTML. boxes: {scene id: html of a game box} (rendered inside the plain list; deck.js moves them)."""
    boxes = boxes or {}
    lis = []
    for sc in scenes:
        lis.append(f'<li data-scene="{esc(sc["id"])}">' + "".join(_li(sc)) + boxes.get(sc["id"], "") + "</li>")
    data = {"scenes": scenes, "ui": ui or {}}
    if audio_src:
        data["audio"] = {"src": audio_src}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (f'<section class="deck" data-deck {attrs}><ol class="dlist">{"".join(lis)}</ol>'
            f'<script type="application/json" class="dscript">{payload}</script></section>')
