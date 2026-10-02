"""Regenerate deeper/data/corpus.json from the corpus metadata (oa_metadata.csv)."""
import csv, json, os, sys, datetime
from urllib.parse import urlparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_lib import ROOT, TOPIC_DIR, c
BASE = TOPIC_DIR
OUT = f"{ROOT}/deeper/data/corpus.json"
HOSTS = {"plato.stanford.edu": "The Stanford Encyclopedia of Philosophy", "www.gutenberg.org": "Project Gutenberg", "archive.org": "Internet Archive", "iep.utm.edu": "Internet Encyclopedia of Philosophy",
         "www.ebi.ac.uk": "Europe PMC"}
PARTIAL = {"Doxastic Deliberation": "repository record only; the article itself could not be fetched",
           "Choosing and refusing: doxastic voluntarism and folk psychology": "abstract only",
           "The misunderstood limits of folk science: an illusion of explanatory depth (open abstract and metadata)": "open abstract and metadata only"}
CATALOGUE_ONLY = {"The Scout Mindset: publisher description and excerpt"}
INDEX = {f: os.path.join(dp, f) for dp, _, fs in os.walk(f"{BASE}/oa") for f in fs}
docs = []
# only what was actually indexed: a download that yielded no passages (a login wall, a bare repository record)
# was never part of the research corpus
INDEXED = {os.path.basename(r["source_file"]) for r in c.execute("SELECT source_file FROM docs WHERE n_chunks > 0")}
for r in csv.DictReader(open(f"{BASE}/oa_metadata.csv")):
    if r["title"] in CATALOGUE_ONLY:
        print("retail metadata only, left out:", r["title"])
        continue
    if r["file"] not in INDEXED:
        print("not indexed, left out:", r["title"][:80])
        continue
    path = INDEX[r["file"]]
    url = r["link"] or (f"https://doi.org/{r['doi']}" if r["doi"] else "")
    d = {"title": r["title"], "authors": r["authors"], "year": r["year"],
         "source": r["journal"] or HOSTS.get(urlparse(url).netloc, urlparse(url).netloc)}
    if r["publisher"]: d["edition"] = r["publisher"]
    if r["doi"]: d["doi"] = r["doi"]
    if r["isbn"]: d["isbn"] = r["isbn"]
    d.update(url=url, license=r["license"].upper() if r["license"].lower().startswith("cc-") else r["license"],
             retrieved=datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc).date().isoformat())
    if urlparse(url).netloc == "api.crossref.org":
        d["format"] = "txt"  # retain the public metadata record, not a purported full article
    for k, v in PARTIAL.items():
        if r["title"].startswith(k): d["held"] = v
    docs.append(d)
# Partial records may be absent from a fresh rebuild: non-indexed repository
# records are deliberately excluded above. Check only titles actually held.
partial_titles = {k for k in PARTIAL if any(d["title"].startswith(k) for d in docs)}
assert sum("held" in d for d in docs) == len(partial_titles), "partial-holding titles not matched"
out = {"name": "search/epistemology",
       "note": (f"The texts the Deeper study pages were researched from: {len(docs)} documents, all open access, free to read "
                "or in the public domain. The corpus itself is not redistributed here. Where a document is held only in part, "
                "'held' says so; a page cites such a work only for what that part shows."),
       "documents": docs}
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1); open(OUT, "a").write("\n")
print(len(docs), "documents;", sorted({d["retrieved"] for d in docs}), sorted({d["license"] for d in docs}))
