"""srcadd.py: add verified entries to deeper/data/sources.json.
  corpus <doc_id> [key]         from the corpus record (SEP, IEP, open-access articles, public-domain books)
  doi <doi> [key]               from the Crossref record
  isbn <isbn> <key> [json]      from the Open Library edition record (json overrides fields, e.g. original_year)
  raw <key> <json>              a hand-made entry (must carry a verified note)
Prints the keys added; refuses to overwrite an existing key."""
import json, re, sys, os, datetime, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_lib import c, SOURCES_PATH
import requests
TODAY = datetime.date.today().isoformat()
S = json.load(open(SOURCES_PATH))

def ascii_low(s):
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower())

def person(p):
    p = p.strip()
    if "," in p:
        return p
    bits = p.split()
    return f"{bits[-1]}, {' '.join(bits[:-1])}" if len(bits) > 1 else p

def mkkey(authors, year, fallback):
    fam = [ascii_low(a.split(",")[0]) for a in authors if a.strip()]
    if not fam:
        base = fallback
    elif len(fam) == 1:
        base = fam[0]
    elif len(fam) == 2:
        base = f"{fam[0]}-{fam[1]}"
    else:
        base = f"{fam[0]}-etal"
    return f"{base}{year or ''}"

def add(key, entry):
    if key in S:
        raise SystemExit(f"{key} already exists: {S[key].get('title')}")
    S[key] = entry
    print("added", key, "|", entry.get("title"), entry.get("year", ""))

def from_corpus(doc_id, key=None):
    d = dict(c.execute("SELECT * FROM docs WHERE id=?", (doc_id,)).fetchone())
    authors = []
    for a in (d["authors"] or "").split(";"):
        parts = [x.strip() for x in a.split(",") if x.strip()]
        if len(parts) > 2:  # "Family, Given, Given2 Family2, ..." (SEP entries with three or more authors)
            authors += [f"{parts[0]}, {parts[1]}"] + [person(x.removeprefix("and ")) for x in parts[2:]]
        elif parts:
            authors.append(person(a))
    url = d["url"]
    if "plato.stanford.edu" in url:
        m = re.match(r"(.+? Edition), ed\. (.+)", d["publisher"] or "")
        eds = [person(e) for e in re.split(r",\s*|\s+and\s+|\s*&\s*", m.group(2))] if m else []
        e = {"type": "entry", "authors": authors, "year": int(d["year"]), "title": d["title"],
             "container": "The Stanford Encyclopedia of Philosophy", "edition": m.group(1) if m else "", "editors": eds,
             "url": url, "access": "free",
             "verified": f"Citation details from the encyclopedia's own citation record for the archived {m.group(1) if m else 'edition'}; full text read, {TODAY}"}
    elif "iep.utm.edu" in url:
        e = {"type": "entry", "authors": authors, "title": d["title"], "container": "Internet Encyclopedia of Philosophy",
             "url": url, "access": "free", "verified": f"Full text read; the entry is undated, {TODAY}"}
        if not authors:
            e["org"] = "Internet Encyclopedia of Philosophy"
    elif d["doi"]:
        e = crossref(d["doi"])
        e["url"] = url; e["access"] = "open"
        e["verified"] = f"Crossref record for the DOI; open-access full text read ({d['license']}), {TODAY}"
    else:
        raise SystemExit(f"doc {doc_id}: use raw for books ({d['title']})")
    slug = re.sub(r".*/entries/|.*iep\.utm\.edu/", "", url).strip("/").split("/")[0]
    key = key or (mkkey(authors, e.get("year"), slug) if authors else f"{slug}-iep")
    add(key, e)

def crossref(doi):
    r = requests.get(f"https://api.crossref.org/works/{doi}", timeout=30)
    r.raise_for_status()
    m = r.json()["message"]
    authors = [f"{a.get('family','')}, {a.get('given','')}".strip(", ") for a in m.get("author", [])]
    year = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
    t = {"journal-article": "article", "book-chapter": "chapter", "book": "book", "monograph": "book"}.get(m.get("type"), "article")
    e = {"type": t, "authors": authors, "year": year, "title": (m.get("title") or [""])[0]}
    cont = (m.get("container-title") or [""])[0]
    if cont: e["container"] = cont
    for f, k in (("volume", "volume"), ("issue", "issue"), ("page", "pages")):
        if m.get(f): e[k] = m[f].replace("-", "–")
    if t in ("book", "chapter") and m.get("publisher"): e["publisher"] = m["publisher"]
    e["doi"] = m["DOI"]; e["access"] = "subscription"; e["verified"] = f"Crossref record for the DOI, {TODAY}"
    return e

def from_isbn(isbn, key, over):
    r = requests.get(f"https://openlibrary.org/isbn/{isbn}.json", timeout=30); r.raise_for_status()
    b = r.json()
    names = []
    for a in b.get("authors", []):
        ar = requests.get(f"https://openlibrary.org{a['key']}.json", timeout=30).json()
        names.append(person(ar.get("name", "")))
    year = re.search(r"\d{4}", b.get("publish_date", ""))
    e = {"type": "book", "authors": names, "year": int(year.group()) if year else None, "title": b.get("title", ""),
         "publisher": ", ".join(b.get("publishers", [])), "isbn": isbn, "verified": f"Open Library edition record for the ISBN, {TODAY}"}
    if b.get("subtitle"): e["title"] += ": " + b["subtitle"]
    if b.get("publish_places"): e["place"] = b["publish_places"][0]
    e.update(over)
    add(key, e)

if __name__ == "__main__":
    cmd, *a = sys.argv[1:]
    if cmd == "corpus":
        from_corpus(int(a[0]), a[1] if len(a) > 1 else None)
    elif cmd == "doi":
        e = crossref(a[0]); add(a[1] if len(a) > 1 else mkkey(e["authors"], e["year"], "x"), e)
    elif cmd == "isbn":
        from_isbn(a[0], a[1], json.loads(a[2]) if len(a) > 2 else {})
    elif cmd == "raw":
        e = json.loads(a[1]); assert e.get("verified"), "raw entries need a verified note"; add(a[0], e)
    json.dump(dict(sorted(S.items())), open(SOURCES_PATH, "w"), ensure_ascii=False, indent=2)
