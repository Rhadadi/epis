"""Static link and anchor check over every generated page (python3 tools/site/check_links.py; exit 1 on a broken link)."""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[2]
SKIP = {"node_modules", "tools", ".git"}

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = set(); self.refs = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a: self.ids.add(a["id"])
        if tag == "a" and "name" in a: self.ids.add(a["name"])
        for k in ("href", "src", "poster", "data-audio", "data-thumb"):
            if a.get(k): self.refs.append((tag, k, a[k]))
        for k in ("srcset", "imagesrcset"):
            if a.get(k):
                for part in a[k].split(","):
                    u = part.strip().split(" ")[0]
                    if u: self.refs.append((tag, k, u))

# hidden directories (.git, a .venv with its packages' test pages) are not part of the site
pages = [p for p in ROOT.rglob("*.html")
         if not SKIP & set(p.relative_to(ROOT).parts) and not any(x.startswith(".") for x in p.relative_to(ROOT).parts)]
parsed = {}
for p in pages:
    x = P(); x.feed(p.read_text(encoding="utf-8")); parsed[p] = x

bad = []; checked = 0
for p, x in parsed.items():
    base = ROOT if p.name == "404.html" and p.parent == ROOT else p.parent
    for tag, k, u in x.refs:
        if re.match(r"^[a-z][a-z0-9+.-]*:", u) or u.startswith("//"):
            continue
        s = urlsplit(u)
        if not s.path:
            target = p
        else:
            target = (ROOT / s.path.lstrip("/")) if s.path.startswith("/") else (base / unquote(s.path))
            target = target.resolve()
            if target.is_dir() or s.path.endswith("/"):
                target = target / "index.html"
        checked += 1
        if not target.exists():
            bad.append(f"{p.relative_to(ROOT)}: {k}={u} -> missing {target}"); continue
        if s.fragment and target.suffix == ".html" and k == "href" and target not in (ROOT / "map/index.html", ROOT / "review/index.html", ROOT / "fa/review/index.html"):
            t = parsed.get(target)
            if t is None:
                t = P(); t.feed(target.read_text(encoding="utf-8")); parsed[target] = t
            if unquote(s.fragment) not in t.ids:
                bad.append(f"{p.relative_to(ROOT)}: {u} -> no #{s.fragment} in {target.relative_to(ROOT)}")

# Every explorer node must have a concept page.
src = (ROOT / "assets/data/concepts.js").read_text(encoding="utf-8")
data = json.loads(src[src.index("{"):src.rindex("}") + 1])
ids = list(data["N"])
missing = [i for i in ids if not (ROOT / "concepts" / f"{i}.html").exists()]
print(f"pages {len(pages)}, references checked {checked}, nodes {len(ids)}, missing concept pages {missing}")
print("\n".join(bad[:80]) or "no broken links or anchors")
print(f"broken: {len(bad)}")

sys.exit(1 if bad else 0)
