"""find.py QUERY [TITLE-LIKE] [N] [WIDTH]: FTS search, compact output (bibliographies excluded)."""
import sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from corpus_lib import c
q = sys.argv[1]; like = sys.argv[2] if len(sys.argv) > 2 else "%"; n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
w = int(sys.argv[4]) if len(sys.argv) > 4 else 1200
for r in c.execute("""SELECT ch.id, ch.locator, d.title, ch.text FROM chunks_fts f JOIN chunks ch ON ch.id=f.chunk_id JOIN docs d ON d.id=ch.doc_id
                      WHERE chunks_fts MATCH ? AND d.title LIKE ? AND ch.locator NOT LIKE '%Bibliograph%' AND ch.locator NOT LIKE '%Works Cited%' AND ch.locator NOT LIKE '%Sources%' AND ch.locator NOT LIKE '%Literature%' AND ch.locator NOT LIKE '%References%' AND ch.locator NOT LIKE '%Primary Texts%'
                      ORDER BY rank LIMIT ?""", (q, like, n)):
    body = re.sub(r"\s+", " ", r["text"])[:w]
    print(f"[{r['id']}] {r['title'][:34]} | {r['locator'][:40]}")
    print(body + "\n")
