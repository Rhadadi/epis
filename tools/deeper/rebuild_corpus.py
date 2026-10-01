"""rebuild_corpus.py [--check-hosts | --report | --dry-run] [--only HOST]: re-acquire the research corpus listed in deeper/data/corpus.json.

The corpus texts are not redistributed in this repository (the SEP and IEP entries and several articles are not
openly licensed for redistribution), so a fresh machine fetches them again from their own sites. Stanford
Encyclopedia entries are fetched from the same archived edition the pages cite, so the text matches. Passage
(chunk) numbers will differ from the ones recorded in the existing provenance files; those numbers belong to the
snapshot they were checked against and need not be regenerated.

Needs the search-bot checkout (SEARCHBOT_DIR), an embedding server (search-bot's scripts/embed_server.py, or
lexical_embed_server.py here when the model cannot be downloaded), the settings in sb.env.example, and network
access to the hosts listed in deeper/HANDOFF.md; --check-hosts tests them all first. A run ends with --report:
every document of corpus.json that is not in the corpus database is listed by name, and the exit status is 1
if any is missing (the per-batch downloads tolerate failures, so a quiet run alone proves nothing). SEARCHBOT_OPENALEX_KEY is needed only for the
handful of articles fetched through OpenAlex; without it they are reported as catalogue-only and skipped."""
import csv, json, os, subprocess, sys, tempfile
from urllib.parse import urlparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE))
docs = json.load(open(f"{ROOT}/deeper/data/corpus.json"))["documents"]


def target(d):
    url, host = d["url"], urlparse(d["url"]).netloc
    meta = {"title": d["title"], "authors": [a for a in d.get("authors", "").split("; ") if a], "year": d.get("year", ""),
            "license": d.get("license", "").lower() if d.get("license", "").startswith("CC") else d.get("license", "")}
    if host in ("plato.stanford.edu", "iep.utm.edu", "en.wikisource.org") or d.get("held"):
        return {"url": url, "kind": "html", **meta, "doi": d.get("doi", "")}
    if host == "www.gutenberg.org":
        return {"gutenberg": url.rstrip("/").rsplit("/", 1)[-1]}
    if host == "archive.org" and "/details/" in url:
        return {"ia": url.rstrip("/").rsplit("/", 1)[-1], "title": d["title"], "license": "public-domain"}
    if host == "archive.org":
        return {"url": url, "kind": "txt", **meta}
    if host == "www.ebi.ac.uk":  # Europe PMC full-text XML
        return {"url": url, "kind": "xml", **meta, "doi": d.get("doi", "")}
    if d.get("doi"):
        return {"openalex": d["doi"]}
    return {"url": url, **meta}


PROBES = [  # one real request per host the rebuild uses
    ("SEP entries", "https://plato.stanford.edu/archives/fall2026/entries/sorites-paradox/"),
    ("IEP entries", "https://iep.utm.edu/fallacy/"),
    ("Project Gutenberg", "https://www.gutenberg.org/cache/epub/5827/pg5827.txt"),
    ("Internet Archive", "https://archive.org/download/inquiryintohum00reid/inquiryintohum00reid_djvu.txt"),
    ("Wikisource", "https://en.wikisource.org/wiki/Popular_Science_Monthly/Volume_12/November_1877/Illustrations_of_the_Logic_of_Science_I"),
    ("Europe PMC", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC1182327/fullTextXML"),
    ("OpenAlex", "https://api.openalex.org/works/doi:10.2478/disp-2005-0017"),
    ("Crossref", "https://api.crossref.org/works/10.2478/disp-2005-0017"),
    ("Open Library", "https://openlibrary.org/isbn/9780199665808.json"),
    ("Python packages", "https://pypi.org/simple/sqlite-vec/"),
]


def check_hosts():
    import urllib.request
    ua = os.environ.get("SEARCHBOT_USER_AGENT", "search-bot/1.0")
    bad = 0
    for label, url in PROBES:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": ua}), timeout=30) as r:
                r.read(1024)
                status = f"ok ({r.status})"
        except Exception as e:  # HTTPError carries the status; proxies refuse with 403
            status = f"BLOCKED: {getattr(e, 'code', '') or ''} {getattr(e, 'reason', e)}".strip()
            bad += 1
        print(f"{label:18} {urlparse(url).netloc:24} {status}")
    print("all reachable" if not bad else f"{bad} host(s) unreachable: allow them in the sandbox's network settings")
    return bad


def report():
    """Compare corpus.json with the corpus database; list what is missing. Returns the number missing."""
    import re
    from corpus_lib import c, canon, norm
    have = [dict(r) for r in c.execute("SELECT d.title, d.url, d.doi, count(ch.id) AS n FROM docs d "
                                        "LEFT JOIN chunks ch ON ch.doc_id = d.id GROUP BY d.id")]
    by_url = {canon(d["url"]): d for d in have}
    by_doi = {(d["doi"] or "").lower(): d for d in have if d["doi"]}
    by_title = {norm(d["title"]): d for d in have}
    missing = []
    for d in docs:
        hit = by_url.get(canon(d["url"])) or by_doi.get((d.get("doi") or "").lower()) or by_title.get(norm(d["title"]))
        if not hit or not hit["n"]:
            missing.append(d)
    chunks = c.execute("SELECT count(*) FROM chunks").fetchone()[0]
    print(f"corpus database: {len(have)} documents, {chunks} passages; corpus.json lists {len(docs)}")
    for d in missing:
        why = "needs SEARCHBOT_OPENALEX_KEY" if target(d).get("openalex") and not os.environ.get("SEARCHBOT_OPENALEX_KEY") else ""
        print(f"MISSING  {d['title'][:70]}  <{d['url']}>  {why}".rstrip())
    print("complete" if not missing else f"{len(missing)} document(s) missing")
    return len(missing)


def main():
    if "--check-hosts" in sys.argv:
        sys.exit(1 if check_hosts() else 0)
    if "--report" in sys.argv:
        sys.exit(1 if report() else 0)
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    targets = [(d, target(d)) for d in docs if not only or urlparse(d["url"]).netloc == only]
    if "--dry-run" in sys.argv:
        for d, t in targets:
            print(json.dumps(t, ensure_ascii=False)[:160])
        print(len(targets), "targets")
        return
    # batches of 20, so one failure does not stop the rest and progress is visible
    for i in range(0, len(targets), 20):
        batch = [t for _, t in targets[i:i + 20]]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(batch, f)
        print(f"== batch {i // 20 + 1}: {len(batch)} targets", flush=True)
        subprocess.run([sys.executable, f"{HERE}/acquire_json.py", f.name], check=False)
        os.unlink(f.name)
    restore_metadata()
    sys.exit(1 if report() else 0)


def restore_metadata():
    """Targets fetched by URL lose the journal and edition lines; copy them back from corpus.json."""
    from corpus_lib import TOPIC_DIR
    path = f"{TOPIC_DIR}/oa_metadata.csv"
    if not os.path.exists(path):
        return
    by_url = {d["url"]: d for d in docs}
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    fields = list(rows[0].keys()) if rows else []
    for r in rows:
        d = by_url.get(r["link"])
        if d:
            r["journal"] = r["journal"] or (d.get("source") if d.get("source") != urlparse(d["url"]).netloc else "")
            r["publisher"] = r["publisher"] or d.get("edition", "")
            r["authors"] = r["authors"] or d.get("authors", "")
            r["year"] = r["year"] or d.get("year", "")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("metadata restored for", sum(1 for r in rows if r["link"] in by_url), "of", len(rows), "documents")


if __name__ == "__main__":
    main()
