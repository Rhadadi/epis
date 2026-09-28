#!/usr/bin/env python3
"""Write the transcript of each Persian narration: what the audio says, word for word, as Markdown.

    python3 make_transcript.py          # every chapter
    python3 make_transcript.py 01 05    # some chapters

The transcripts (../transcripts/NN-*.md) are made from the narration scripts,
so they follow the audio line by line: section titles become headings,
quotations block quotes and the speakers of a dialogue lines that start with a
dash. Pauses, chimes and the thinking time in the quiz are not written down.
Latin, German and French expressions keep their own spelling here; the audio
says them as lexicon.txt spells them in Persian letters.

When a chapter's MP3 is listed in ../tracks.js, the transcript starts with its
length and the start time of each section.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parent
sys.path.insert(0, str(HERE))
from narrate import parse  # noqa: E402

OUT = AUDIO / "transcripts"
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(n):
    return str(n).translate(FA)


def clock(sec):
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    return fa(f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}")


def length(sec):
    m = round(sec / 60)
    h, m = divmod(m, 60)
    return (f"{fa(h)} ساعت و {fa(m)} دقیقه" if m else f"{fa(h)} ساعت") if h else f"{fa(m)} دقیقه"


def tracks():
    path = AUDIO / "tracks.js"
    if not path.exists():
        return {}
    js = path.read_text(encoding="utf-8")
    return {t["file"][:-4]: t for t in json.loads(js[js.index("["):js.rindex("]") + 1])}


def transcript(script_path, track):
    cues = parse(script_path.read_text(encoding="utf-8"))
    name = script_path.stem
    title = next((t for k, t in cues if k == "title"), name)
    out = [f"# {title}", ""]
    out.append(f"متنِ روایتِ صوتیِ این فصل، همان‌طور که شنیده می‌شود. متنِ نوشتاری: [{title.split(':')[0]}](../../{name}.md).")
    out.append("")
    if track:
        out.append(f"فایلِ صوتی: [{name}.mp3](../{name}.mp3)، {length(track['duration'])}.")
        out.append("")
        out += [f"- {clock(s['start'])} {'آغاز' if i == 0 else s['title']}" for i, s in enumerate(track["sections"])]
        out.append("")
    out += ["---", ""]
    prev = None
    for kind, text in cues:
        if kind in ("title", "pause", "think", "chime") or not text:
            continue
        if kind == "section":
            out += [f"## {text}", ""]
        elif kind == "subsection":
            out += [f"### {text}", ""]
        elif kind in ("opening", "cue", "label"):
            out += [f"**{text}**", ""]
        elif kind == "quote":
            out += [f"> {text}", ""]
        elif kind == "attr":
            if prev == "quote":  # the source goes inside the quotation's block
                out[-1:] = [">", f"> — {text}", ""]
            else:
                out += [f"— {text}", ""]
        elif kind.startswith("voice"):
            out += [f"— {text}", ""]
        else:  # say, item, aside, question, answer
            out += [text, ""]
        prev = kind
    return "\n".join(out).rstrip() + "\n"


def main():
    wanted = set(sys.argv[1:])
    known = tracks()
    OUT.mkdir(exist_ok=True)
    for s in sorted((AUDIO / "scripts").glob("[01][0-9]-*.txt")):
        if wanted and s.name[:2] not in wanted:
            continue
        (OUT / f"{s.stem}.md").write_text(transcript(s, known.get(s.stem)), encoding="utf-8")
        print(f"transcripts/{s.stem}.md")


if __name__ == "__main__":
    main()
