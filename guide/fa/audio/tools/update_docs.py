#!/usr/bin/env python3
"""After rendering: bring the Persian docs in line with the narration that exists (../tracks.js).

    python3 update_docs.py

- ../README.md: the table of chapters and their lengths, with a note while
  some chapters are still to come;
- each narrated chapter's "**صوت:**" line in guide/fa/NN-*.md: its length,
  without "روایت به انگلیسی";
- guide/fa/README.md: what it says about the audio edition.
"""

import json
import re
from pathlib import Path

AUDIO = Path(__file__).resolve().parent.parent
FA = AUDIO.parent
DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
CHAPTERS = 16


def fa(n):
    return str(n).translate(DIGITS)


def length(sec):
    m = round(sec / 60)
    h, m = divmod(m, 60)
    return (f"{fa(h)} ساعت و {fa(m)} دقیقه" if m else f"{fa(h)} ساعت") if h else f"{fa(m)} دقیقه"


def hours(sec):
    """Roughly, in words: «نوزده ساعت», «هجده ساعت و نیم»."""
    words = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده", "یازده", "دوازده", "سیزده",
             "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده", "بیست", "بیست و یک", "بیست و دو"]
    half = round(sec / 1800)
    h, rest = divmod(half, 2)
    return f"{words[h]} ساعت" + (" و نیم" if rest else "")


def main():
    js = (AUDIO / "tracks.js").read_text(encoding="utf-8")
    tracks = json.loads(js[js.index("["):js.rindex("]") + 1])
    done = len(tracks)
    total = sum(t["duration"] for t in tracks)

    rows = ["| | فصل | مدت |", "|---|---|---|"]
    for t in tracks:
        title = t["title"].split(": ", 1)[-1]
        rows.append(f"| {fa(int(t['file'][:2]))} | [{title}]({t['file']}) | {length(t['duration'])} |")
    table = "\n".join(rows) + f"\n\nجمع: {length(total)}."
    if done < CHAPTERS:
        table = (f"> **در حالِ ساخت.** روایتِ فارسی فصل‌به‌فصل ساخته و منتشر می‌شود: تا اینجا {fa(done)} فصل از "
                 f"{fa(CHAPTERS)} فصل آماده است. در پخش‌کننده، فصل‌های دیگر فعلاً با روایتِ انگلیسی پخش می‌شوند.\n\n" + table)
    readme = AUDIO / "README.md"
    s = readme.read_text(encoding="utf-8")
    s = re.sub(r"<!-- tracks -->.*?(?=\n---\n)", lambda m: "<!-- tracks -->\n" + table + "\n", s, flags=re.S)
    readme.write_text(s, encoding="utf-8")

    for t in tracks:
        page = FA / (t["file"][:-4] + ".md")
        s = page.read_text(encoding="utf-8")
        line = (f"**صوت:** [شنیدنِ این فصل](audio/{t['file']}) ({length(t['duration'])}) · "
                f"[باز کردن در پخش‌کننده](audio/index.html#{t['file'][:2]})")
        s2 = re.sub(r"^\*\*صوت:\*\* .*$", line, s, count=1, flags=re.M)
        assert s2 != s or line in s, page
        page.write_text(s2, encoding="utf-8")

    guide = FA / "README.md"
    s = guide.read_text(encoding="utf-8")
    if done >= CHAPTERS:
        about = f"همهٔ فصل‌ها نسخهٔ صوتیِ فارسی هم دارند، روی‌هم حدودِ {hours(total)}."
        kind = "به زبانِ فارسی"
    else:
        about = (f"همهٔ فصل‌ها نسخهٔ صوتی هم دارند. روایتِ فارسی فصل‌به‌فصل آماده می‌شود: تا اینجا {fa(done)} فصل از "
                 f"{fa(CHAPTERS)} فصل روایتِ فارسی دارد و بقیه فعلاً روایتِ انگلیسی.")
        kind = "به زبانِ فارسی (یا، تا وقتی روایتِ فارسیِ آن آماده شود، به زبانِ انگلیسی)"
    s = re.sub(r"^همهٔ فصل‌ها نسخهٔ صوتی.*?(?= می‌توانید از \*\*\[پخش‌کنندهٔ صوتی\])", about, s, count=1, flags=re.M)
    s = re.sub(r"^(- \*\*صوت\*\*: هر فصل یک نسخهٔ صوتی ).*?( دارد که برای شنیدن بازنویسی شده است)",
               lambda m: m.group(1) + kind + m.group(2), s, count=1, flags=re.M)
    guide.write_text(s, encoding="utf-8")
    print(f"{done} chapters, {length(total)}")


if __name__ == "__main__":
    main()
