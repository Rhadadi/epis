"""Shared corpus helpers: normalisation, key -> corpus documents, chunk lookup."""
import json, os, re, sys
from pathlib import Path
ROOT = str(Path(__file__).resolve().parents[2])           # the epis checkout
SEARCHBOT_DIR = os.environ.get("SEARCHBOT_DIR") or sys.exit(
    "Set SEARCHBOT_DIR to your search-bot checkout (github.com/Rhadadi/search-bot, branch epis-evidence); see deeper/HANDOFF.md")
TOPIC_DIR = os.path.join(SEARCHBOT_DIR, "search", "epistemology")
if not os.path.isfile(os.path.join(SEARCHBOT_DIR, "searchbot", "oa.py")):
    sys.exit(f"{SEARCHBOT_DIR} is not a search-bot checkout with the open-access acquirer (branch epis-evidence)")
_DB = os.path.join(SEARCHBOT_DIR, "data", "searchbot.db")
if not os.environ.get("EPIS_CREATE_CORPUS") and not (os.path.isfile(_DB) and os.path.getsize(_DB) > 0):
    sys.exit(f"no corpus at {_DB}: build it first with tools/deeper/rebuild_corpus.py (see deeper/HANDOFF.md)")
sys.path.insert(0, SEARCHBOT_DIR)
from searchbot import db
c = db.connect()
SOURCES_PATH = f"{ROOT}/deeper/data/sources.json"
norm = lambda s: re.sub(r"\s+", " ", s.replace("­", "").replace("¬ ", "").replace("- ", "")).strip().lower()
QUOTES = str.maketrans({"’": "", "‘": "", "“": "", "”": "", "'": "", '"': "", "_": "", "*": "", "–": "-", "—": "-", "₂": "2"})
TEX = {r"\Box": "□", r"\Diamond": "◇", r"\forall": "∀", r"\exists": "∃", r"\rightarrow": "→", r"\leftrightarrow": "↔",
       r"\vee": "∨", r"\wedge": "∧", r"\amp": "&", r"\neg": "¬", r"\supset": "⊃", r"\vdash": "⊢", r"\sim": "~"}
def detex(s):
    """Inline LaTeX as it appears in SEP entries (\\(\\Box A\\)) to the plain symbols a page would use (□A)."""
    for k, v in TEX.items():
        s = s.replace(k, v)
    s = re.sub(r"\\math(?:bf|rm|it)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:bK|rA|rB|rC)\b", lambda m: m.group(0)[-1], s)
    s = s.replace("\\(", "").replace("\\)", "").replace("{", "").replace("}", "")
    return re.sub(r"\s*([□◇∀∃¬~])\s*", r"\1", re.sub(r"\s*(→|↔|∨|∧|⊃|⊢)\s*", r" \1 ", s))
fold = lambda s: re.sub(r"\s+", " ", norm(detex(s)).translate(QUOTES)).strip()

def sources():
    return json.load(open(SOURCES_PATH))

def canon(u):
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")

_docs = None
def docs():
    global _docs
    if _docs is None:
        _docs = [dict(r) for r in c.execute("SELECT id, title, url, doi FROM docs")]
    return _docs

def keydocs(key, src=None):
    s = (src or sources()).get(key)
    if not s:
        return set()
    want = {canon(s.get("url")), canon(f"doi.org/{s['doi']}") if s.get("doi") else None, canon(s.get("corpus_url"))} - {None, ""}
    ids = {d["id"] for d in docs() if canon(d["url"]) in want or (s.get("doi") and (d["doi"] or "").lower() == s["doi"].lower())}
    if not ids and s.get("title"):
        t = norm(s["title"])
        ids = {d["id"] for d in docs() if norm(d["title"]) == t}
    # a "corpus_doc" id would name a document in one machine's database only, so it is not honoured:
    # give the source the url (or "corpus_url") of the text in the corpus instead
    return ids

_chunk_cache = {}
def chunks_of(doc_ids):
    out = []
    for d in sorted(doc_ids):
        if d not in _chunk_cache:
            _chunk_cache[d] = [(r["id"], r["text"]) for r in c.execute("SELECT id, text FROM chunks WHERE doc_id=? ORDER BY id", (d,))]
        out += _chunk_cache[d]
    return out
