#!/usr/bin/env python3
"""Write `of:` into the front matter of each Persian Deeper study page (deeper/src-fa/): the fingerprint of the English page it
translates. tools/site/build.py compares it and says when an English page has changed since its translation was written.

    python3 tools/deeper/fa_fingerprint.py [chapter-prefix ...]
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def body(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return text[m.end():] if m else text


def main(argv):
    n = 0
    for p in sorted((ROOT / "deeper" / "src-fa").glob("[01][0-9]-*/*.md")):
        if argv and not any(p.parent.name.startswith(a) for a in argv):
            continue
        en = ROOT / "deeper" / "src" / p.parent.name / p.name
        if not en.exists():
            print(f"no English page for {p.relative_to(ROOT)}")
            continue
        fp = hashlib.sha1(body(en.read_text(encoding="utf-8")).encode("utf-8")).hexdigest()[:10]
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        lines = [l for l in (m.group(1).splitlines() if m else []) if not l.startswith("of:")]
        new = "---\n" + "\n".join(lines + [f"of: {fp}"]) + "\n---\n" + body(text)
        if new != text:
            p.write_text(new, encoding="utf-8")
            n += 1
    print(f"fingerprints written in {n} file(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
