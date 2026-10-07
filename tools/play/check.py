#!/usr/bin/env python3
"""Check Baloney Detector (play/): run after the build (tools/deeper/check.sh does).

For every live game in play/games.json: its data file exists, every English string has Persian, the cases are
well formed (choices with explanations, best answers that exist, known charts, simulations and controls). For
every card: Persian title and hook. From the built pages (play/, fa/play/): no account/notes/AI/learning
scripts, a content-security policy, no frames or forms, no scripts from other sites, and every live game has a
page. Exit status 1 on any problem."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_play as P  # noqa: E402

FORBIDDEN_SCRIPTS = ("account.js", "ai.js", "ai-config.js", "notes.js", "learn.js")


def main():
    errs = []
    cards = P.catalogue()
    ids = [c["id"] for c in cards]
    if len(set(ids)) != len(ids):
        errs.append("play/games.json: two cards share an id")
    for c in cards:
        errs += [f"play/games.json {c['id']}: no Persian for {x}" for x in P.missing_fa(c)]
        if c.get("live"):
            errs += [f"{c['id']}: {e}" for e in P.game_problems(c["id"])]
            for lang_dir in (P.ROOT / "play", P.ROOT / "fa" / "play"):
                if not (lang_dir / c["id"] / "index.html").exists():
                    errs.append(f"{c['id']}: no built page in {lang_dir.relative_to(P.ROOT)} (run tools/site/build.py)")
    pages = list((P.ROOT / "play").rglob("*.html")) + list((P.ROOT / "fa" / "play").rglob("*.html"))
    if not pages:
        errs.append("no built play pages (run tools/site/build.py)")
    for p in pages:
        h = p.read_text(encoding="utf-8")
        rel = p.relative_to(P.ROOT)
        for s in FORBIDDEN_SCRIPTS:
            if re.search(r'src="[^"]*/' + re.escape(s), h):
                errs.append(f"{rel}: loads {s}")
        if 'http-equiv="Content-Security-Policy"' not in h:
            errs.append(f"{rel}: no content-security policy")
        if re.search(r"<(iframe|form|embed|object)\b", h, re.I):
            errs.append(f"{rel}: has a frame, form or embedded object")
        if re.search(r'<script[^>]+src="https?:', h):
            errs.append(f"{rel}: loads a script from another site")
    if errs:
        print("play: problems:\n  " + "\n  ".join(errs))
        sys.exit(1)
    print(f"play: OK, {sum(1 for c in cards if c.get('live'))} live game(s), {len(cards)} cards")


if __name__ == "__main__":
    main()
