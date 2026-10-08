#!/usr/bin/env python3
"""Narrate a kids unit's story with ElevenLabs, one voice per role, keeping the time of every word.

    python3 tools/kids/narrate.py u01-how-do-you-know --dry-run        # characters and voices; nothing generated
    python3 tools/kids/narrate.py u01-how-do-you-know                  # both languages
    python3 tools/kids/narrate.py u01-how-do-you-know --lang fa

The story (kids/src/<unit>/story.<lang>.md) becomes a row of segments, one per run of lines in the same voice
(kids/voices.json); each segment is generated with the timestamps endpoint, which gives the time of every
character, so every word on the page can light up as it is read. Same-voice segments are stitched (request
IDs), so a voice keeps its tone across the story. Between segments: a short silence, longer where the picture
changes. Generated segments are kept in tools/kids/.eleven-kids/ (not committed) by a hash of their text and
voice, so running again costs nothing unless a line changed.

Writes assets/kids/audio/<unit>.<lang>.mp3 (mono, 32 kbit/s) and assets/kids/sync/<unit>.<lang>.json:
{v, file, lang, duration, narration{engine, model, voices}, shots{id: start}, lines[{id, role, text, b, e, w[[b, e]…]}]}

Reuses the guide's narrator (guide/fa/audio/tools/eleven_narrate.py: call, subscription, voice_settings,
speak_timed), imported read-only. Needs ELEVENLABS_API_KEY in the environment (never written anywhere), the
requests package and ffmpeg. Before generating, the subscription is read and nothing is made unless the
remaining credits cover it."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kidslib as K  # noqa: E402

ROOT = K.ROOT
STATE = HERE / ".eleven-kids"
AUDIO = ROOT / "assets" / "kids" / "audio"
SYNC = ROOT / "assets" / "kids" / "sync"
GAP, SHOT_GAP, LEAD = 0.45, 0.9, 0.3
WEB = ["-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "32k"]
MAX_CHARS = 1500


def narrator_module():
    spec = importlib.util.spec_from_file_location("eleven_narrate", ROOT / "guide" / "fa" / "audio" / "tools" / "eleven_narrate.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for name in ("call", "subscription", "voice_settings", "speak_timed"):
        if not callable(getattr(m, name, None)):
            raise SystemExit(f"eleven_narrate.py no longer has {name}(); update tools/kids/narrate.py")
    return m


def segments_of(story, voices):
    """Runs of consecutive lines in the same voice (and the same picture), each at most MAX_CHARS long."""
    segs = []
    for ln in story["lines"]:
        vid = voices.get(ln["role"], voices["narrator"])["id"]
        last = segs[-1] if segs else None
        if last and last["voice"] == vid and last["shot"] == ln["shot"] and sum(len(x["text"]) + 2 for x in last["lines"]) + len(ln["text"]) <= MAX_CHARS:
            last["lines"].append(ln)
        else:
            segs.append({"voice": vid, "shot": ln["shot"], "lines": [ln]})
    for s in segs:
        s["text"] = "\n\n".join(x["text"] for x in s["lines"])
    return segs


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def word_times(text, alignment, total):
    """(start, end) of every whitespace-separated word of text, in seconds from the segment's start: from the
    character times when they match the text, otherwise in proportion to the characters (approximate)."""
    spans, pos = [], 0
    for w in text.split():
        i = text.index(w, pos)
        spans.append((i, i + len(w) - 1))
        pos = i + len(w)
    chars = (alignment or {}).get("characters")
    starts = (alignment or {}).get("character_start_times_seconds")
    ends = (alignment or {}).get("character_end_times_seconds")
    if chars and len(chars) == len(text):
        return [(starts[a], ends[b]) for a, b in spans], False
    n = max(1, len(text))
    return [(total * a / n, total * (b + 1) / n) for a, b in spans], True


def narrate(uid, lang, args, en, voices_all, level=None):
    """level None: the story alone (kids/audio/<unit>.<lang>.mp3); a level: the whole scene deck of that level (story and
    lessons, <unit>.<level>.<lang>.mp3), which is what the unit pages play."""
    voices = voices_all[lang]
    story = K.story(uid, lang)
    name = f"{uid}.{lang}" if not level else f"{uid}.{level}.{lang}"
    order = None
    if level:
        lines, order = K.deck_script(uid, level, lang)
        story = {"title": story["title"], "lines": lines, "shots": order}
    segs = segments_of(story, voices)
    chars = sum(len(s["text"]) for s in segs)
    print(f"{name}: {len(story['lines'])} lines, {len(segs)} segments, {chars} characters")
    STATE.mkdir(exist_ok=True)
    todo = []
    for s in segs:
        s["key"] = hashlib.sha1(json.dumps([voices_all["model"], s["voice"], s["text"]], ensure_ascii=False).encode()).hexdigest()[:16]
        if not (STATE / f"{s['key']}.mp3").exists():
            todo.append(s)
    need = sum(len(s["text"]) for s in todo)
    print(f"  to generate: {len(todo)} segments, {need} characters")
    if args.dry_run:
        return
    if need:
        sub = en.subscription()
        print(f"  credits: {sub['remaining']} remaining of {sub['limit']}")
        if sub["remaining"] < need * 1.1 + 200:
            raise SystemExit("  not enough credits left; nothing generated")
    en.MODEL = voices_all["model"]
    settings, previous = {}, {}
    for i, s in enumerate(segs):
        mp3, meta = STATE / f"{s['key']}.mp3", STATE / f"{s['key']}.json"
        if s in todo:
            if s["voice"] not in settings:
                settings[s["voice"]] = en.voice_settings(s["voice"])
            nxt = segs[i + 1]["text"] if i + 1 < len(segs) and segs[i + 1]["voice"] == s["voice"] else None
            audio, alignment, rid, cost = en.speak_timed(s["text"], s["voice"], settings[s["voice"]], seed=7,
                                                         previous=previous.get(s["voice"], []), next_text=nxt)
            mp3.write_bytes(audio)
            meta.write_text(json.dumps({"alignment": alignment, "request_id": rid, "cost": cost}), encoding="utf-8")
            print(f"  segment {i + 1}/{len(segs)}: {len(s['text'])} characters, cost {cost}")
        info = json.loads(meta.read_text(encoding="utf-8"))
        if info.get("request_id"):
            previous.setdefault(s["voice"], []).append(info["request_id"])
    # join: lead silence, segments, gaps (longer where the picture changes); times from the decoded pieces
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        pieces, t, lines, shots, approx = [], 0.0, [], {}, False

        def silence(sec):
            p = tmp / f"sil-{sec:.2f}.wav"
            if not p.exists():
                ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{sec:.2f}", "-c:a", "pcm_s16le", str(p))
            return p
        pieces.append(silence(LEAD))
        t += LEAD
        for i, s in enumerate(segs):
            if i:
                g = SHOT_GAP if s["shot"] != segs[i - 1]["shot"] else GAP
                pieces.append(silence(g))
                t += g
            wav = tmp / f"seg{i:03d}.wav"
            ffmpeg("-i", str(STATE / f"{s['key']}.mp3"), "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(wav))
            dur = seconds(wav)
            alignment = json.loads((STATE / f"{s['key']}.json").read_text(encoding="utf-8"))["alignment"]
            wt, rough = word_times(s["text"], alignment, dur)
            approx |= rough
            if s["shot"] not in shots:
                shots[s["shot"]] = round(t - (GAP if i else 0), 3)
            k = 0
            for ln in s["lines"]:
                n = len(ln["text"].split())
                w = [[round(t + a, 3), round(t + b, 3)] for a, b in wt[k:k + n]]
                k += n
                lines.append({"id": ln["id"], "role": ln["role"], "text": ln["text"], "b": w[0][0], "e": w[-1][1], "w": w})
            pieces.append(wav)
            t += dur
        pieces.append(silence(0.6))
        listing = tmp / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in pieces), encoding="utf-8")
        AUDIO.mkdir(parents=True, exist_ok=True)
        SYNC.mkdir(parents=True, exist_ok=True)
        out = AUDIO / f"{name}.mp3"
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), *WEB, "-metadata", f"title={story['title']}",
               "-metadata", "artist=How Do You Know?", str(out))
    sync = {"v": 1, "file": out.name, "lang": lang, "duration": round(seconds(out), 2), "approx": approx,
            "narration": {"engine": "ElevenLabs", "model": voices_all["model"],
                          "voices": {r: v["name"] for r, v in voices.items() if any(ln["role"] == r for ln in story["lines"])}},
            "shots": shots, "lines": lines}
    if order:
        sync["order"] = order
        sync["level"] = level
    (SYNC / f"{name}.json").write_text(json.dumps(sync, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)} ({sync['duration']:.1f} s, {out.stat().st_size // 1024} KB){' — approximate word times' if approx else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("unit")
    ap.add_argument("--lang", choices=["en", "fa", "both"], default="both")
    ap.add_argument("--level", choices=["explorers", "investigators", "deck", "story"], default="story",
                    help="story: the story alone; explorers / investigators: that level's whole scene deck; deck: both levels")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    voices_all = K.read_json(K.KIDS / "voices.json")
    en = None if args.dry_run else narrator_module()
    levels = [None] if args.level == "story" else (list(K.LEVELS) if args.level == "deck" else [args.level])
    for lang in (K.LANGS if args.lang == "both" else (args.lang,)):
        for level in levels:
            narrate(args.unit, lang, args, en, voices_all, level)


if __name__ == "__main__":
    main()
