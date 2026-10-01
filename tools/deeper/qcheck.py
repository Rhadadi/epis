"""qcheck.py PAGE.md: for each "quote" followed (in the same paragraph) by [@key...], report where it occurs in the key's chunks."""
import re, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from corpus_lib import c, fold, keydocs, chunks_of
src = open(sys.argv[1]).read()
for para in re.split(r"\n\s*\n", src):
    for m in re.finditer(r"[\"“]([^\"”]{12,})[\"”]", para):
        rest = para[m.end():]
        cm = re.search(r"\[@([\w\-]+)", rest)
        if not cm: continue
        keys = re.findall(r"@([\w\-]+)", rest[cm.start():].split("]")[0])
        q = fold(m.group(1))
        hits = []
        for k in keys:
            for cid, t in chunks_of(keydocs(k)):
                if q in fold(t):
                    loc = c.execute("SELECT locator FROM chunks WHERE id=?", (cid,)).fetchone()[0]
                    hits.append(f"{k}:{cid}:{loc[:30]}")
        print(("OK  " if hits else "MISS") + f" {m.group(1)[:70]!r} -> {keys} {hits[:2]}")
