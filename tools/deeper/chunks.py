"""chunks.py IDS...: print corpus passages by id or range (e.g. 8445-8452)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_lib import c
for a in sys.argv[1:]:
    lo, _, hi = a.partition("-")
    for i in range(int(lo), int(hi or lo) + 1):
        r = c.execute("SELECT ch.id, ch.locator, d.title, ch.text FROM chunks ch JOIN docs d ON d.id=ch.doc_id WHERE ch.id=?", (i,)).fetchone()
        if r: print(f"\n[{r['id']}] {r['title'][:40]} | {r['locator']}\n{r['text']}")
