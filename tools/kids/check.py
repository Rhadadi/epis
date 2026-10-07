#!/usr/bin/env python3
"""Check the children's section (kids/): run after the build (tools/deeper/check.sh does).

For every published unit: the structure the build also enforces, reading level per level and language, the
new-word budget, bilingual game data, the story's source record, the narration sync (if any), and, from the
built pages, the safety rules: no account/notes/AI/learning scripts, a content-security policy, no forms or
frames, and no link to another website that does not go through the "ask a grown-up" screen.
Exit status 1 on any problem."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kidslib as K  # noqa: E402
import site_kids  # noqa: E402

LIMITS = {  # reading level: English Flesch–Kincaid grade; Persian average sentence length (words)
    "explorers": {"fk": 4.5, "fa_sentence": 12.0, "new_words": 5},
    "investigators": {"fk": 7.5, "fa_sentence": 18.0, "new_words": 8},
}
MEDIA_CAP_MB = 90
FORBIDDEN_SCRIPTS = ("account.js", "ai.js", "ai-config.js", "notes.js", "learn.js")


def prose_of(text):
    """The prose a child reads on a lesson page: every block's text except word lists and game/quiz ids; no tables."""
    def keep(m):
        return "" if m.group(1) in ("words", "check") else m.group(3)
    text = K.BLOCK.sub(keep, text)
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("|"))


def check_unit(u, words):
    uid, errs = u["id"], []
    errs += site_kids.unit_problems(uid)
    if errs:
        return errs
    meta = K.unit_meta(uid)
    for s in meta.get("shots", []):
        if not s.get("alt") or not (s.get("fa") or {}).get("alt"):
            errs.append(f"shot {s['id']}: needs alt text in English and Persian")
    stories = K.read_json(K.KIDS / "stories.json")
    rec = stories.get(meta.get("story"))
    if not rec:
        errs.append(f"story {meta.get('story')!r} has no record in kids/stories.json")
    else:
        for k in ("source", "public_domain", "verified"):
            if not rec.get(k):
                errs.append(f"kids/stories.json {meta['story']}: missing {k}")
    for lang in K.LANGS:
        st = K.story(uid, lang)
        story_text = "\n\n".join(ln["text"] for ln in st["lines"])
        for level in K.LEVELS:
            _, text = K.front_matter((K.unit_dir(uid) / f"{level}.{lang}.md").read_text(encoding="utf-8"))
            prose = prose_of(text) + ("\n\n" + story_text if level == "explorers" else "")
            lim = LIMITS[level]
            if lang == "en":
                fk = K.flesch_kincaid(prose)
                if fk > lim["fk"]:
                    errs.append(f"{level}.en.md: reading level {fk:.1f} is above grade {lim['fk']}")
            else:
                if re.search(r"[يك]", text):
                    errs.append(f"{level}.fa.md: Arabic ي or ك (use ی and ک)")
                avg, _ = K.persian_level(prose)
                if avg > lim["fa_sentence"]:
                    errs.append(f"{level}.fa.md: sentences average {avg:.1f} words (limit {lim['fa_sentence']})")
            ids = []
            for k, arg, inner in K.lesson_blocks(text):
                if k == "words":
                    ids += [w.strip() for w in re.split(r"[,\s]+", inner.strip()) if w.strip()]
                if k in ("tryit", "check"):
                    errs += [f"kids/games/{arg}.json: {e}" for e in game_problems(arg)]
            if len(ids) > lim["new_words"]:
                errs.append(f"{level}.{lang}.md: {len(ids)} new words (limit {lim['new_words']})")
            for w in ids:
                if w not in words:
                    errs.append(f"{level}.{lang}.md: word {w!r} is not in kids/words.json")
        if re.search(r"[يك]", (K.unit_dir(uid) / "story.fa.md").read_text(encoding="utf-8")) and lang == "fa":
            errs.append("story.fa.md: Arabic ي or ك (use ی and ک)")
        sync = site_kids.load_sync(uid, lang)
        if sync:
            errs += sync_problems(uid, lang, sync, st)
    return sorted(set(errs))


def game_problems(gid):
    g = K.game(gid)
    errs = [f"no Persian for {p}" for p in K.missing_fa(g)]
    if g.get("engine") == "sorter":
        bins = {b["id"] for b in g.get("buckets", [])}
        for c in g.get("cards", []):
            if c.get("bucket") not in bins:
                errs.append(f"card {c.get('text', '')[:30]!r} goes to unknown bucket {c.get('bucket')!r}")
            for lv in c.get("levels", []):
                if lv not in K.LEVELS:
                    errs.append(f"unknown level {lv!r}")
        for lv in K.LEVELS:
            cards = site_kids.for_level(g, lv)["cards"]
            used = {c["bucket"] for c in cards}
            shown = {b["id"] for b in site_kids.for_level(g, lv)["buckets"]}
            if not used <= shown:
                errs.append(f"{lv}: a card goes to a bucket that level doesn't show")
    elif g.get("engine") == "quiz":
        for it in g.get("items", []):
            n = len(it.get("choices", []))
            if not (0 <= it.get("correct", -1) < n):
                errs.append(f"question {it.get('q', '')[:30]!r}: correct answer out of range")
            fa = (it.get("fa") or {}).get("choices", [])
            if len(fa) != n:
                errs.append(f"question {it.get('q', '')[:30]!r}: {n} English choices but {len(fa)} Persian")
        for lv in K.LEVELS:
            if not site_kids.for_level(g, lv)["items"]:
                errs.append(f"{lv}: no questions for this level")
    else:
        errs.append(f"unknown engine {g.get('engine')!r}")
    return errs


def sync_problems(uid, lang, sync, st):
    errs = []
    times = {ln["id"]: ln for ln in sync.get("lines", [])}
    for ln in st["lines"]:
        tm = times.get(ln["id"])
        if not tm or tm.get("text") != ln["text"]:
            errs.append(f"sync {uid}.{lang}: line {ln['id']} changed since it was narrated (run tools/kids/narrate.py)")
            break
        if len(tm.get("w", [])) != len(K.words_of(ln["text"])):
            errs.append(f"sync {uid}.{lang}: line {ln['id']} has {len(tm.get('w', []))} word times for {len(K.words_of(ln['text']))} words")
    if not (K.ROOT / "assets" / "kids" / "audio" / sync["file"]).exists():
        errs.append(f"sync {uid}.{lang}: audio file {sync['file']} is missing")
    return errs


def check_books():
    errs = []
    for b in K.read_json(K.KIDS / "books.json"):
        if not b.get("catalogue") or not (b.get("verified") or {}).get("on"):
            errs.append(f"kids/books.json {b.get('id')}: needs a catalogue link and verified.on")
        if len((b.get("fa") or {}).get("questions", [])) != len(b.get("questions", [])):
            errs.append(f"kids/books.json {b.get('id')}: Persian questions don't match the English ones")
        errs += [f"kids/books.json {b.get('id')}: no Persian for {p}" for p in K.missing_fa(b) if not p.endswith(".title")]
    return errs


def check_built():
    errs = []
    pages = list((K.ROOT / "kids").rglob("*.html")) + list((K.ROOT / "fa" / "kids").rglob("*.html"))
    if not pages:
        return ["no built kids pages (run tools/site/build.py)"]
    for p in pages:
        h = p.read_text(encoding="utf-8")
        rel = p.relative_to(K.ROOT)
        for s in FORBIDDEN_SCRIPTS:
            if re.search(r'src="[^"]*/' + re.escape(s), h):
                errs.append(f"{rel}: loads {s}")
        if 'http-equiv="Content-Security-Policy"' not in h:
            errs.append(f"{rel}: no content-security policy")
        if re.search(r"<(iframe|form|embed|object)\b", h, re.I):
            errs.append(f"{rel}: has a frame, form or embedded object")
        if re.search(r'<script[^>]+src="https?:', h):
            errs.append(f"{rel}: loads a script from another site")
        for m in re.finditer(r'<a\b[^>]*href="(https?:[^"]+)"[^>]*>', h):
            if "data-leave" not in m.group(0):
                errs.append(f"{rel}: link to {m.group(1)} without the ask-a-grown-up screen (data-leave)")
    return errs


def media_mb():
    total = sum(f.stat().st_size for f in (K.ROOT / "assets" / "kids").rglob("*") if f.is_file())
    for base in (K.ROOT / "kids", K.ROOT / "fa" / "kids"):
        total += sum(f.stat().st_size for f in base.rglob("*.html"))
    return total / 1e6


def main():
    words = {w["id"] for w in K.read_json(K.KIDS / "words.json")}
    errs = []
    live = [u for u in K.units()["units"] if site_kids.published(u)]
    for u in live:
        errs += [f"{u['id']}: {e}" for e in check_unit(u, words)]
    errs += check_books()
    errs += check_built()
    mb = media_mb()
    if mb > MEDIA_CAP_MB:
        errs.append(f"kids media and pages take {mb:.1f} MB (cap {MEDIA_CAP_MB} MB: move large media to the media site)")
    if errs:
        print("kids: problems:\n  " + "\n  ".join(errs))
        sys.exit(1)
    print(f"kids: OK, {len(live)} published unit(s), {mb:.1f} MB")


if __name__ == "__main__":
    main()
