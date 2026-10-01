"""verify_specs.py SPEC...: check every excerpt in the specs against the corpus without writing anything.
Use it to confirm, on a new machine or after a corpus rebuild, that published provenance still holds."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_lib import keydocs, chunks_of, fold, sources
S = sources(); ok = bad = 0
for spec in sys.argv[1:]:
    page = None
    for line in open(spec, encoding="utf-8"):
        if line.startswith("== "):
            page = line[3:].strip()
        m = re.match(r"@([\w\-]+) \| ([^|]+) \| (.+?)(?: \| note:.*)?$", line.strip())
        if not m or m.group(3).startswith("ref:"):
            continue
        f = fold(m.group(3))
        if any(f in fold(t) for _, t in chunks_of(keydocs(m.group(1), S))):
            ok += 1
        else:
            bad += 1
            print(f"MISS {page} @{m.group(1)} {m.group(2).strip()}: {m.group(3)[:70]}")
print(f"excerpts found: {ok}, missing: {bad}")
sys.exit(1 if bad else 0)
