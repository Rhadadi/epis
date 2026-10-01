"""rebuild_corpus.py [--dry-run] [--only HOST]: re-acquire the research corpus listed in deeper/data/corpus.json.

The corpus texts are not redistributed in this repository (the SEP and IEP entries and several articles are not
openly licensed for redistribution), so a fresh machine fetches them again from their own sites. Stanford
Encyclopedia entries are fetched from the same archived edition the pages cite, so the text matches. Passage
(chunk) numbers will differ from the ones recorded in the existing provenance files; those numbers belong to the
snapshot they were checked against and need not be regenerated.

Needs the search-bot checkout (SEARCHBOT_DIR), its embedding server running, the settings in sb.env.example,
and network access to the hosts listed in deeper/HANDOFF.md. SEARCHBOT_OPENALEX_KEY is needed only for the
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


def main():
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
