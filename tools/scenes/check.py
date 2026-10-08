#!/usr/bin/env python3
"""Check the guide's scene decks (scenes/home.json, scenes/chapters/NN.json): Persian for every text, known drawings, every
chapter number real, scenes well formed, and no game boxes (decks on the guide only talk and ask). Exit status 1 on any problem."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenes as SC  # noqa: E402

ROOT = SC.ROOT


def main():
    errs, n = [], 0
    files = [ROOT / "scenes" / "home.json", *sorted((ROOT / "scenes" / "chapters").glob("*.json"))]
    for f in files:
        if not f.exists():
            continue
        n += 1
        rel = f.relative_to(ROOT)
        raw = SC.json.loads(f.read_text(encoding="utf-8"))["scenes"]
        if f.parent.name == "chapters":
            m = re.fullmatch(r"(\d\d)\.json", f.name)
            if not m or not list((ROOT / "guide").glob(f"{m.group(1)}-*.md")):
                errs.append(f"{rel}: no chapter with this number")
        errs += [f"{rel}: no Persian for {p}" for p in SC.missing_fa(raw)]
        for lang in ("en", "fa"):
            scenes = [SC.pick(x, lang) for x in raw]
            errs += [f"{rel} [{lang}]: {e}" for e in SC.validate(scenes)]
            errs += [f"{rel} [{lang}]: scene {x['id']} has a game (not allowed on the guide)" for x in scenes if x.get("game")]
            if lang == "fa":
                for x in scenes:
                    blob = str(x)
                    if re.search(r"[يك]", blob):
                        errs.append(f"{rel} [fa]: Arabic ي or ك in scene {x['id']} (use ی and ک)")
    if errs:
        print("scenes: problems:\n  " + "\n  ".join(errs))
        sys.exit(1)
    print(f"scenes: OK, {n} deck file(s)")


if __name__ == "__main__":
    main()
