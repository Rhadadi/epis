#!/usr/bin/env python3
"""The narrated layer is frozen: the chapter text the audio was made from, the audio, its line timings
and its scripts. This keeps a SHA-256 manifest of those files (tools/site/frozen.sha256) and fails when
any of them has changed, appeared or gone missing, so that work on the site (the scholarly companions,
for instance) cannot quietly put the narration out of step with its text.

    python3 tools/site/frozen.py            check; exit 1 on any difference
    python3 tools/site/frozen.py --update   rewrite the manifest (only after a deliberate change to the
                                            narrated text or audio, re-recorded to match)

Generated pages under guide/audio/ (index.html, about.html, feed.xml) are rebuilt by build.py and are
not part of the frozen layer."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("frozen.sha256")
CHAPTERS = [f"{n:02d}-*.md" for n in range(1, 17)]
PATTERNS = (
    [f"guide/{c}" for c in CHAPTERS] + [f"guide/fa/{c}" for c in CHAPTERS] +
    ["guide/audio/*.mp3", "guide/audio/tracks.js", "guide/audio/sync/*.json", "guide/audio/scripts/*.txt",
     "guide/fa/audio/*.mp3", "guide/fa/audio/tracks.js", "guide/fa/audio/sync/*.json", "guide/fa/audio/scripts/*.txt",
     "guide/fa/audio/narration/*.txt", "guide/fa/audio/transcripts/*"])


def current():
    files = sorted({p for pat in PATTERNS for p in ROOT.glob(pat) if p.is_file()})
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def main():
    now = current()
    if "--update" in sys.argv:
        MANIFEST.write_text("".join(f"{h}  {f}\n" for f, h in now.items()), encoding="utf-8")
        print(f"frozen: manifest rewritten, {len(now)} files")
        return 0
    if not MANIFEST.exists():
        print("frozen: no manifest; run with --update once to create it")
        return 1
    want = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        h, _, f = line.partition("  ")
        want[f] = h
    changed = [f for f in want if f in now and now[f] != want[f]]
    missing = [f for f in want if f not in now]
    added = [f for f in now if f not in want]
    for label, items in (("changed", changed), ("missing", missing), ("new", added)):
        for f in items:
            print(f"frozen: {label}: {f}")
    if changed or missing or added:
        print(f"frozen: FAILED ({len(changed)} changed, {len(missing)} missing, {len(added)} new of {len(want)})")
        return 1
    print(f"frozen: OK, {len(want)} narrated files unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
