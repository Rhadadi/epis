"""readdoc.py ID-RANGE [WIDTH]: print consecutive corpus passages with their overlaps removed, for reading a
section in full (e.g. readdoc.py 48983-49008)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_lib import c
lo, _, hi = sys.argv[1].partition("-")
prev = ""
for r in c.execute("SELECT id, locator, text FROM chunks WHERE id BETWEEN ? AND ? ORDER BY id", (int(lo), int(hi or lo))):
    t = re.sub(r"\s+", " ", r["text"])
    k = next((n for n in range(min(len(prev), 600), 20, -1) if t.startswith(prev[-n:])), 0)
    print(f"[{r['id']} {r['locator'][:24]}] {t[k:]}")
    prev = t
