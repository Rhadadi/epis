"""grepc.py 'ids' 'regex' [width]: print sentences of the given chunks that match regex (case-insensitive).
ids: comma-separated ids or ranges, e.g. 680-689,699"""
import re, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from corpus_lib import c
ids = []
for a in sys.argv[1].split(","):
    lo, _, hi = a.partition("-")
    ids += range(int(lo), int(hi or lo) + 1)
rx = re.compile(sys.argv[2], re.I)
w = int(sys.argv[3]) if len(sys.argv) > 3 else 400
for i in ids:
    r = c.execute("SELECT ch.locator, ch.text FROM chunks ch WHERE ch.id=?", (i,)).fetchone()
    if not r: continue
    t = re.sub(r"\s+", " ", r["text"])
    for s in re.split(r"(?<=[.!?])\s+(?=[A-Z“\"(])", t):
        if rx.search(s): print(f"[{i} {r['locator'][:22]}] {s[:w]}")
