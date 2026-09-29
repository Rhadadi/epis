#!/usr/bin/env python3
"""Write the transcript of each Persian narration: what the audio says, word for word, as Markdown.

    python3 make_transcript.py          # every chapter
    python3 make_transcript.py 01 05    # some chapters

The transcripts (../transcripts/NN-*.md) are made from the narration scripts,
so they follow the audio line by line: section titles become headings,
quotations block quotes, and the lines of a dialogue carry the speaker's label
from the chapter (الف, ب), which the audio does not say. Pauses, chimes and the
thinking time in the quiz are not written down.
Latin, German and French expressions keep their own spelling here; the audio
says them as lexicon.txt spells them in Persian letters.

When a chapter's MP3 is listed in ../tracks.js, the transcript starts with its
length and the start time of each section. When the chapter has two narrators
(its ../sync/NN-*.json names two voices), the list also says which voice reads
each section.
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


VOICE_NAMES = {"main": "صدای مردانه", "second": "صدای زنانه"}
TWO_VOICES = ("راویان: دو صدای ساختگی، یکی مردانه و یکی زنانه. صدای مردانه فصل را آغاز می‌کند و می‌بندد، "
              "و بخش‌ها به نوبت میانِ دو صدا می‌چرخند. نقل‌قول را صدایی می‌خواند که راویِ آن بخش نیست؛ "
              "در گفت‌وگوها «الف» صدای مردانه است و «ب» صدای زنانه؛ و در آزمونِ شفاهیِ پایانِ فصل "
              "صدای زنانه می‌پرسد و صدای مردانه پاسخ می‌دهد.")


def narrators(name):
    """The voice that reads each section title (and the opening, under ""), for a chapter with two narrators."""
    path = AUDIO / "sync" / f"{name}.json"
    if not path.exists():
        return {}
    sync = json.loads(path.read_text(encoding="utf-8"))
    if len(sync.get("narration", {}).get("voices", {})) < 2 or not sync["lines"]:
        return {}
    who = {"": sync["lines"][0].get("voice")}
    for line in sync["lines"]:
        if line["kind"] == "section":
            who.setdefault(line["text"], line.get("voice"))
    return who


def transcript(script_path, track):
    cues = parse(script_path.read_text(encoding="utf-8"))
    name = script_path.stem
    title = next((t for k, t in cues if k == "title"), name)
    out = [f"# {title}", ""]
    out.append(f"متنِ روایتِ صوتیِ این فصل، همان‌طور که شنیده می‌شود. متنِ نوشتاری: [{title.split(':')[0]}](../../{name}.md).")
    out.append("")
    if track:
        who = narrators(name)
        out.append(f"فایلِ صوتی: [{name}.mp3](../{name}.mp3)، {length(track['duration'])}.")
        out.append("")
        if who:
            out += [TWO_VOICES, ""]
        for i, s in enumerate(track["sections"]):
            voice = VOICE_NAMES.get(who.get("" if i == 0 else s["title"]))
            out.append(f"- {clock(s['start'])} {'آغاز' if i == 0 else s['title']}" + (f" ({voice})" if voice else ""))
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
        elif kind.startswith("voice"):  # the speaker's label from the chapter; it is not spoken
            out += [f"**{ {'voice1': 'الف', 'voice2': 'ب'}.get(kind, 'ج') }:** {text}", ""]
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
