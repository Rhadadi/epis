"""prov2.py SPEC... : write deeper/data/<chapter>/<section>.json from compact specs.

Spec format (one file may hold several pages):
  == <chapter>/<section>
  Q: a research question
  @key | locator | exact excerpt [| note: ...]       excerpt is found in the key's corpus documents automatically
  @key | locator | ref:secondary | note text          a work cited from secondary reports (no excerpt)
  @key | locator | ref:catalogue | note text
  A @key: annotation shown under the reference
  ok-quote: start of a quotation on the page that is not from a cited source (an example, a title)
Checks: every cited key has evidence and nothing else is listed; every excerpt is in the key's documents;
every quotation on the page is found in a document cited in the same paragraph (or allowed with ok-quote)."""
import json, os, re, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_lib import c, ROOT, norm, fold, sources, keydocs, chunks_of

TODAY = datetime.date.today().isoformat()
METHOD = ("Questions were researched with an evidence-only retrieval tool over one corpus of open-access and public-domain texts "
          "(see corpus.json). Each excerpt was checked word for word against the corpus passage it cites when this file was "
          f"written; corpus_chunk numbers that passage in the corpus snapshot of {TODAY}.")
SRC = sources()
VARIANTS = [lambda e: e, lambda e: e.replace("'", "’"), lambda e: re.sub(r'"([^"]*)"', r"“\1”", e),
            lambda e: re.sub(r'"([^"]*)"', r"“\1”", e.replace("'", "’"))]

def locate(key, excerpt):
    ids = keydocs(key, SRC)
    if not ids:
        raise SystemExit(f"@{key}: no corpus document for this source")
    for var in VARIANTS:
        e = var(excerpt)
        n = norm(e)
        for cid, text in chunks_of(ids):
            if n in norm(text):
                return cid, e
    f = fold(excerpt)
    hint = next((cid for cid, text in chunks_of(ids) if f[:40] in fold(text)), None)
    raise SystemExit(f"@{key}: excerpt not found{' (start found in chunk %s)' % hint if hint else ''}: {excerpt[:90]}")

def layer_of(page):
    """key -> ordered list of the headings (H3, or H2 when no H3) under which it is cited."""
    used, h2, h3 = {}, "", ""
    for line in page.splitlines():
        if line.startswith("## "):
            h2, h3 = line[3:].strip(), ""
        elif line.startswith("### "):
            h3 = line[4:].strip()
        for k in re.findall(r"@([\w:.-]+)", line):
            used.setdefault(k, [])
            label = h3 or h2 or "In short"
            if label not in used[k]:
                used[k].append(label)
    return used

_doctext = {}
def doctext(ids):
    key = tuple(sorted(ids))
    if key not in _doctext:
        _doctext[key] = " ".join(fold(t) for _, t in chunks_of(ids))
    return _doctext[key]

def attributed_quotes(para):
    """(quote, keys) for each quotation followed, in the same sentence, by a citation."""
    marks = [m.start() for m in re.finditer(r'"', para)]
    out = []
    for s, e in zip(marks[0::2], marks[1::2]):
        q = para[s + 1:e]
        m = re.search(r"\[(@[^\[\]]+)\]", para[e + 1:])
        if not m:
            continue
        between = re.sub(r'"[^"]*"', "", para[e + 1:e + 1 + m.start()])
        if len(between) > 300 or re.search(r"[.!?:;](\s|$)", between):
            continue
        out.append((q, re.findall(r"@([\w:.-]+)", m.group(1))))
    return out

def check_quotes(page, ok):
    errs = []
    body = page.split("\n---\n", 1)[1]
    titles = {fold(s.get("title", "")) for s in SRC.values()}
    for para in re.split(r"\n\s*\n|\n(?=- |\d+\. |\| )", body):
        for q, keys in attributed_quotes(para):
            if len(q) < 12 or any(q.startswith(o) for o in ok) or fold(q) in titles:
                continue
            ids = set().union(*[keydocs(k, SRC) for k in keys])
            if not ids:
                continue  # cited only from works not in the corpus
            text = doctext(ids)
            for frag in re.split(r"\s*(?:\.\.\.|…|\[[^\]]*\])\s*", q):
                frag = frag.strip(" ,;:")
                if len(frag) >= 12 and fold(frag) not in text:
                    errs.append(f"quotation not found in {', '.join('@' + k for k in keys)}: \"{frag[:80]}\"")
    return errs

def run(block):
    lines = block.strip().splitlines()
    chapter, section = lines[0].strip().split("/")
    page = open(f"{ROOT}/deeper/src/{chapter}/{section}.md").read()
    qs, ev, ann, ok = [], {}, {}, []
    for ln in lines[1:]:
        ln = ln.rstrip()
        if not ln.strip() or ln.startswith("#"):
            continue
        if ln.startswith("Q:"):
            qs.append(ln[2:].strip()); continue
        if ln.startswith("ok-quote:"):
            ok.append(ln[9:].strip()); continue
        m = re.match(r"A @([\w:.-]+):\s*(.+)", ln)
        if m:
            ann[m.group(1)] = m.group(2).strip(); continue
        m = re.match(r"@([\w:.-]+)\s*\|\s*([^|]+?)\s*\|\s*(.+)$", ln)
        if not m:
            raise SystemExit(f"{section}: bad spec line: {ln[:80]}")
        key, loc, rest = m.groups()
        if key not in SRC:
            raise SystemExit(f"{section}: @{key} is not in sources.json")
        r = re.match(r"ref:(secondary|catalogue)\s*\|\s*(.+)", rest)
        if r:
            ev.setdefault(key, []).append({"locator": loc, "basis": r.group(1), "note": r.group(2).strip()}); continue
        note = None
        if " | note:" in rest:
            rest, note = rest.split(" | note:", 1)
        cid, exact = locate(key, rest.strip())
        item = {"locator": loc, "basis": "full text", "excerpt": exact, "corpus_chunk": cid}
        if note:
            item["note"] = note.strip()
        ev.setdefault(key, []).append(item)
    cited = set(re.findall(r"@([\w:.-]+)", page))
    missing, unused = cited - set(ev), set(ev) - cited
    errs = [f"cited without evidence: @{k}" for k in sorted(missing)] + [f"evidence for a source not cited: @{k}" for k in sorted(unused)]
    errs += check_quotes(page, ok)
    if errs:
        raise SystemExit(f"{section}:\n  " + "\n  ".join(errs))
    used = layer_of(page)
    data = {"chapter": chapter, "section": section, "updated": TODAY, "method": METHOD, "questions": qs,
            "sources": [{"key": k, "used_for": used.get(k, []), "evidence": ev[k], **({"annotation": ann[k]} if k in ann else {})}
                        for k in sorted(ev, key=lambda k: list(used).index(k) if k in used else 999)]}
    os.makedirs(f"{ROOT}/deeper/data/{chapter}", exist_ok=True)
    json.dump(data, open(f"{ROOT}/deeper/data/{chapter}/{section}.json", "w"), ensure_ascii=False, indent=2)
    print(f"{section}: {len(ev)} sources, {sum(len(v) for v in ev.values())} evidence items")

if __name__ == "__main__":
    for path in sys.argv[1:]:
        text = open(path).read()
        for block in re.split(r"^== ", text, flags=re.M)[1:]:
            run(block)
