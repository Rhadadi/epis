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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "play"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenes"))
import kidslib as K  # noqa: E402
import site_kids  # noqa: E402
import site_play  # noqa: E402
import scenes as SC  # noqa: E402

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


def deck_text(scenes):
    """What a child reads in a deck (one language, one level): scene text, lists, questions, words, bubbles."""
    out = []
    for sc in scenes:
        t = sc.get("text")
        out += [t] if isinstance(t, str) else list(t or [])
        out += sc.get("list", [])
        for a in sc.get("actors", []):
            out.append(a.get("say", ""))
        if sc.get("ask"):
            out.append(sc["ask"].get("q", ""))
            for o in sc["ask"]["options"]:
                out += [o["t"], o.get("why", "")]
        for c in sc.get("cards", []):
            out += [c.get("def", "")]
    out = [re.sub(r"[*_]", "", x) for x in out if x and x.strip()]
    return "\n\n".join(x if x.rstrip().endswith((".", "!", "?", "؟", ":", "…")) else x + "." for x in out)


def check_decks(uid):
    """Scene decks (kids/src/<unit>/deck.<level>.json): Persian for every text, known drawings, reading level."""
    errs = []
    for level in K.LEVELS:
        path = site_kids.deck_path(uid, level)
        if not path.exists():
            continue
        raw = K.read_json(path)["scenes"]
        errs += [f"{path.name}: no Persian for {p}" for p in SC.missing_fa(raw)]
        for lang in K.LANGS:
            scenes = [K.pick(x, lang) for x in raw if level in x.get("levels", [level])]
            plain = [x for x in scenes if not any(x.get(k) for k in ("story", "words", "game"))]
            errs += [f"{path.name} [{lang}]: {e}" for e in SC.validate(plain)]
            text = deck_text(plain)
            lim = LIMITS[level]
            if lang == "en":
                fk = K.flesch_kincaid(text)
                if fk > lim["fk"]:
                    errs.append(f"{path.name}: reading level {fk:.1f} is above grade {lim['fk']}")
            else:
                avg, _ = K.persian_level(text)
                if avg > lim["fa_sentence"]:
                    errs.append(f"{path.name}: sentences average {avg:.1f} words (limit {lim['fa_sentence']})")
                if re.search(r"[يك]", text):
                    errs.append(f"{path.name}: Arabic ي or ك (use ی and ک)")
    return errs


def check_unit(u, words):
    uid, errs = u["id"], []
    errs += check_decks(uid)
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
                if k in ("tryit", "check", "opener"):
                    errs += [f"{K.game_path(arg).relative_to(K.ROOT)}: {e}" for e in game_problems(arg)]
                    errs += [f"{K.game_path(arg).relative_to(K.ROOT)}: {e}" for e in case_level_problems(arg, level, lang)]
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


def case_text(g):
    """Everything a child reads in a case game (one language, one level), as plain sentences."""
    out = []
    for c in g.get("cases", []):
        out += [c.get("headline", ""), c.get("q", "")]
        out += [x for ch in c.get("choices", []) for x in (ch.get("text", ""), ch.get("why", ""))]
        out += [x for cl in c.get("clues", []) for x in (cl.get("title", ""), cl.get("text", ""))]
        out += [x for it in c.get("ideas", []) for x in (it.get("name", ""), it.get("text", ""))]
        out += [(c.get("surprise") or {}).get("text", ""), (c.get("surprise") or {}).get("after", ""), (c.get("sandbox") or {}).get("intro", "")]
    # a heading or choice without a full stop still ends a sentence
    return "\n\n".join(t if t.rstrip().endswith((".", "!", "?", "؟", ":")) else t + "." for t in out if t.strip())


def case_level_problems(gid, level, lang):
    g = K.game(gid)
    if g.get("engine") != "case":
        return []
    lim = LIMITS[level]
    text = case_text(site_kids.for_level(K.pick(g, lang), level))
    if not text:
        return [f"{level}: no cases for this level"]
    if lang == "en":
        fk = K.flesch_kincaid(text)
        return [f"{level}: reading level {fk:.1f} is above grade {lim['fk']}"] if fk > lim["fk"] else []
    avg, _ = K.persian_level(text)
    errs = [f"{level} (fa): sentences average {avg:.1f} words (limit {lim['fa_sentence']})"] if avg > lim["fa_sentence"] else []
    if re.search(r"[يك]", text):
        errs.append(f"{level} (fa): Arabic ي or ك (use ی and ک)")
    return errs


def game_problems(gid):
    g = K.game(gid)
    if g.get("engine") == "case":
        return [f"no Persian for {p}" for p in site_play.missing_fa(g)] + site_play.case_problems(g)
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
    elif g.get("engine") == "mystery":
        errs += mystery_problems(g)
    elif g.get("engine") == "builder":
        ids = {x["id"] for x in g.get("suspects", [])}
        for c in g.get("clues", []):
            if c.get("kind") != "neutral" and c.get("about") not in ids:
                errs.append(f"builder: clue {c.get('id')} is about {c.get('about')!r}, who is not a suspect")
        for lv, n in (g.get("take") or {}).items():
            if n > len(g.get("clues", [])):
                errs.append(f"builder: {lv} takes more clues than there are")
    elif g.get("engine") == "playground":
        if len(g.get("kids", [])) < 6:
            errs.append("playground: needs at least six kids")
        if not any(c.get("ok") for c in g.get("choices", [])):
            errs.append("playground: one choice must be the good answer")
    else:
        errs.append(f"unknown engine {g.get('engine')!r}")
    return errs


def mystery_problems(g):
    """A mission's structure: sources point at things on its stage and at answers it offers; the rules end with a default."""
    errs = []
    for k, r in enumerate(g.get("rounds", []), 1):
        w = f"round {k}"
        hyps = {h["id"] for h in r.get("hyps", [])}
        items = {x["id"] for x in r.get("stage", {}).get("actors", []) + r.get("stage", {}).get("props", [])}
        ids = [x["id"] for x in r.get("sources", [])]
        if len(set(ids)) != len(ids):
            errs.append(f"{w}: two sources with the same id")
        for x in r.get("sources", []):
            if x.get("target") not in items:
                errs.append(f"{w}: source {x['id']} points at {x.get('target')!r}, which is not on the stage")
            for h in x.get("pts", {}):
                if h not in hyps:
                    errs.append(f"{w}: source {x['id']} favours unknown answer {h!r}")
        if not 1 <= r.get("limit", 0) <= len(ids):
            errs.append(f"{w}: the limit must be between 1 and the number of sources")
        for ru in r.get("rules", []):
            if ru.get("best") not in hyps:
                errs.append(f"{w}: a rule's best answer {ru.get('best')!r} is not offered")
            if any(i not in ids for i in ru.get("if", [])):
                errs.append(f"{w}: a rule needs an unknown source")
            if ru.get("conf") not in (0, 1, 2):
                errs.append(f"{w}: confidence must be 0, 1 or 2")
        if not r.get("rules") or r["rules"][-1].get("if"):
            errs.append(f"{w}: the last rule must be the default (if: [])")
        if not any(h.get("unsure") for h in r.get("hyps", [])):
            errs.append(f"{w}: offer a 'not enough evidence yet' answer")
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
    for a in K.read_json(K.KIDS / "arcade.json")["games"]:
        errs += [f"kids/arcade.json {a['id']}: no Persian for {p}" for p in site_play.missing_fa(a)]
        errs += [f"arcade {a['id']}: {e}" for e in game_problems(a["id"])]
        for level in K.LEVELS:
            for lang in K.LANGS:
                errs += [f"arcade {a['id']}: {e}" for e in case_level_problems(a["id"], level, lang)]
    import episodes as EP
    for path in sorted((K.KIDS / "episodes").glob("*.json")):
        ep = K.read_json(path)
        if isinstance(ep, dict) and "steps" in ep:  # (the folder also holds the list and the frames' prompts)
            errs += [f"kids/episodes/{path.name}: {e}" for e in EP.problems(ep)]
    errs += check_books()
    errs += check_built()
    mb = media_mb()
    if mb > MEDIA_CAP_MB:
        errs.append(f"kids media and pages take {mb:.1f} MB (cap {MEDIA_CAP_MB} MB: move large media to the media site)")
    if errs:
        print("kids: problems:\n  " + "\n  ".join(errs))
        sys.exit(1)
    print(f"kids: OK, {len(live)} published unit(s), {len(EP.live())} episode(s), {mb:.1f} MB")


if __name__ == "__main__":
    main()
