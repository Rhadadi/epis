"""acquire_json.py FILE: targets as a JSON list."""
import sys, json, os
os.environ["EPIS_CREATE_CORPUS"] = "1"  # the first acquisition creates the corpus database
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_lib import c
from searchbot import db, llm, oa
db.init(c, llm.embed_dim())
T = json.load(open(sys.argv[1]))
def ev(kind, msg, **kw): print(kind, "|", msg, flush=True)
got, cat = oa.acquire_round(c, "epistemology", "", ev, targets=T, sources=(), max_new=0)
print(f"== done: got {got}; catalogue only: {[x.get('title') for x in cat]}", flush=True)
