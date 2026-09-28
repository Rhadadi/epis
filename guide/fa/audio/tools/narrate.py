#!/usr/bin/env python3
"""Render the Persian narration scripts to MP3 with Microsoft Azure AI Speech.

    python3 narrate.py 01                 # one chapter
    python3 narrate.py --all --jobs 6     # every chapter, six requests at a time
    python3 narrate.py --say "متن" out.wav --role quote   # one line to a WAV file
    python3 narrate.py --index            # rebuild tracks.js for the player from the MP3s

This is the Persian counterpart of guide/audio/tools/narrate.py and reads the
same script format (see make_script.py). The narration uses Azure's Iranian
Persian neural voice fa-IR-FaridNeural. Azure has one other Persian voice
(Dilara), but it does not sound Iranian, so Farid reads everything:
quotations and the two speakers of a dialogue get a slightly different pitch
and pace, so the ear can still tell them apart.

Needs: the environment variables AZURE_SPEECH_KEY and AZURE_SPEECH_REGION,
the Python packages requests, soundfile and numpy, and ffmpeg. The key is read
from the environment only; it is never written anywhere.

Each cue (a paragraph, a heading, a list item) is one request, so Azure can
phrase whole paragraphs naturally. Rendered cues are cached in $NARRATE_CACHE
(default: tools/.narrate-cache), so after editing a script only the changed
lines are sent again.

lexicon.txt gives spoken forms for words the voice would otherwise misread,
mostly Latin, German and French expressions, which are written in Persian
letters so that they are said the way an Iranian reader says them.
"""

import argparse
import hashlib
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parent
SCRIPTS = AUDIO / "scripts"
CACHE = Path(os.environ.get("NARRATE_CACHE", HERE / ".narrate-cache"))
SR = 24000

ALBUM = "تسلط بر معرفت‌شناسی (نسخهٔ صوتی)"
VOICE = "fa-IR-FaridNeural"

# role: (pitch, rate, seconds of silence before, seconds after)
STYLE = {
    "say":        ("+0%", "+0%", 0.00, 0.75),
    "item":       ("+0%", "+0%", 0.00, 0.50),
    "aside":      ("+0%", "-5%", 0.00, 0.50),
    "opening":    ("+0%", "-10%", 0.30, 0.00),
    "section":    ("+0%", "-6%", 0.45, 0.95),
    "subsection": ("+0%", "-5%", 0.85, 0.60),
    "quote":      ("-6%", "-4%", 0.20, 0.40),
    "attr":       ("+0%", "+0%", 0.00, 0.40),
    "cue":        ("+0%", "-3%", 0.20, 0.30),
    "label":      ("+0%", "+0%", 0.10, 0.25),
    "voice1":     ("+7%", "+3%", 0.00, 0.40),
    "voice2":     ("-9%", "-3%", 0.00, 0.40),
    "voice3":     ("+3%", "+0%", 0.00, 0.40),
    "question":   ("+0%", "-3%", 0.00, 0.20),
    "answer":     ("+0%", "+0%", 0.00, 0.75),
}


# ---------------------------------------------------------------------------
# Text to SSML


def load_lexicon():
    """lexicon.txt: `word <tab> spoken form`, one per line."""
    lex = {}
    for line in (HERE / "lexicon.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].rstrip()
        if line.strip():
            word, spoken = [x.strip() for x in line.split("\t", 1)]
            lex[word.lower()] = spoken
    return lex


LEXICON = load_lexicon()
_keys = sorted(LEXICON, key=len, reverse=True)
LEX_RE = re.compile(r"(?<![\w'])(" + "|".join(re.escape(k) for k in _keys) + r")(?![\w'])", re.IGNORECASE) if _keys else None


def ssml(text, role):
    pitch, rate, _, _ = STYLE[role]
    body = html.escape(text, quote=False)
    if LEX_RE:
        body = LEX_RE.sub(lambda m: f'<sub alias="{html.escape(LEXICON[m.group(1).lower()])}">{m.group(1)}</sub>', body)
    return ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="fa-IR">'
            f'<voice name="{VOICE}"><prosody pitch="{pitch}" rate="{rate}">{body}</prosody></voice></speak>')


# ---------------------------------------------------------------------------
# Azure


def synthesize(doc):
    """SSML to 24 kHz mono float audio, with retries for throttling and network errors."""
    import requests
    key, region = os.environ.get("AZURE_SPEECH_KEY"), os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        sys.exit("set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION")
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
               "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm", "User-Agent": "mastering-epistemology-audio"}
    for attempt in range(8):
        try:
            r = requests.post(url, data=doc.encode("utf-8"), headers=headers, timeout=180)
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  network error ({e.__class__.__name__}), retrying in {wait}s", flush=True)
            time.sleep(wait)
            continue
        if r.status_code == 200:
            audio, sr = sf.read(io.BytesIO(r.content), dtype="float32")
            assert sr == SR
            return audio
        if r.status_code in (429, 500, 502, 503, 504):
            wait = float(r.headers.get("Retry-After") or 2 ** attempt)
            time.sleep(min(wait, 60))
            continue
        raise RuntimeError(f"Azure TTS error {r.status_code}: {r.text[:300]}")
    raise RuntimeError("Azure TTS: too many retries")


def trim(audio, threshold=0.003, keep=0.05):
    """Cut the silence Azure leaves at both ends, keeping a little air; pauses are ours to set."""
    idx = np.where(np.abs(audio) > threshold)[0]
    if len(idx) == 0:
        return audio[:0]
    a, b = max(0, idx[0] - int(keep * SR)), min(len(audio), idx[-1] + int(keep * SR))
    return audio[a:b]


def speak(text, role):
    doc = ssml(text, role)
    key = hashlib.sha1(doc.encode()).hexdigest()
    path = CACHE / key[:2] / f"{key}.flac"
    if path.exists():
        audio, _ = sf.read(path, dtype="float32")
        return audio
    audio = trim(synthesize(doc))
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, SR, format="FLAC", subtype="PCM_16")
    return audio


# ---------------------------------------------------------------------------
# Sounds (the same as the English edition's)


def tone(freq, dur, amp, decay):
    t = np.arange(int(dur * SR)) / SR
    env = np.exp(-t / decay) * np.minimum(1, t / 0.006)
    wave = (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
            + 0.12 * np.sin(2 * np.pi * 3.01 * freq * t))
    return (amp * env * wave).astype(np.float32)


def chime():
    """Two soft ascending notes, like a small bell."""
    a = tone(659.25, 1.5, 0.075, 0.35)
    b = tone(987.77, 1.5, 0.06, 0.40)
    out = np.zeros(int(1.75 * SR), dtype=np.float32)
    out[: len(a)] += a
    start = int(0.16 * SR)
    out[start: start + len(b)] += b[: len(out) - start]
    return out


def bell():
    return tone(1318.5, 0.8, 0.08, 0.22)


def silence(sec):
    return np.zeros(int(round(sec * SR)), dtype=np.float32)


# ---------------------------------------------------------------------------
# Rendering


def parse(script):
    cues = []
    for line in script.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^@(\w+)(?:\s+(.*))?$", line)
        if m:
            cues.append((m.group(1), (m.group(2) or "").strip()))
        else:
            cues.append(("say", line))
    return cues


def render(script, jobs=4, log=None):
    """Script text to (audio, title, sections), where sections are (title, seconds)."""
    cues = parse(script)
    for kind, _ in cues:
        if kind not in STYLE and kind not in ("title", "pause", "think", "chime"):
            raise ValueError(f"unknown cue @{kind}")
    spoken = [(k, t) for k, t in cues if k in STYLE and t]
    with ThreadPoolExecutor(jobs) as pool:  # fetch every line first, several at a time
        results = dict(zip(spoken, pool.map(lambda c: speak(c[1], c[0]), spoken)))
    if log:
        log(f"{len(spoken)} lines")

    pieces, sections, title = [silence(0.8)], [], ""
    length = [len(pieces[0])]

    def add(a):
        pieces.append(a)
        length[0] += len(a)

    for kind, text in cues:
        if kind == "title":
            title = text
        elif kind in ("pause", "think"):
            add(silence(float(text)))
        elif kind == "chime":
            add(chime())
        elif kind in STYLE:
            _, _, before, after = STYLE[kind]
            if kind == "section":
                add(silence(0.9))
                sections.append((text, length[0] / SR))
                add(chime())
            elif kind == "opening":
                sections.append((text, 0.0))
            elif kind == "cue":
                add(silence(0.25))
                add(bell())
            add(silence(before))
            if text:
                add(results[(kind, text)])
            add(silence(after))
    add(silence(1.5))
    return np.concatenate(pieces), title, sections


def master(audio, out_mp3, title, track, total, sections):
    """Loudness-normalize (two-pass EBU R128), encode MP3, tag, add chapter markers."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "raw.wav"
        sf.write(wav, audio, SR, subtype="FLOAT")
        chain = "highpass=f=60"
        measure = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af",
             f"{chain},loudnorm=I=-18:TP=-2:LRA=11:print_format=json", "-f", "null", "-"],
            capture_output=True, text=True, check=True).stderr
        stats = json.loads(measure[measure.rindex("{"):measure.rindex("}") + 1])
        norm = (f"{chain},loudnorm=I=-18:TP=-2:LRA=11:linear=true:"
                f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
                f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']},"
                "alimiter=limit=0.79:level=false")
        duration = len(audio) / SR
        meta = Path(tmp) / "meta.txt"
        lines = [";FFMETADATA1", f"title={title}", f"album={ALBUM}", "artist=تسلط بر معرفت‌شناسی",
                 f"track={track}/{total}", "genre=Audiobook", "language=fas",
                 "comment=Narrated with the Microsoft Azure AI Speech neural voice fa-IR-FaridNeural."]
        for k, (name, start) in enumerate(sections):
            stop = sections[k + 1][1] if k + 1 < len(sections) else duration
            lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}",
                      f"END={int(stop * 1000)}", f"title={name}"]
        meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-i", str(meta),
             "-map", "0:a", "-map_metadata", "1", "-map_chapters", "1", "-af", norm + f",aresample={SR}",
             "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "40k", "-id3v2_version", "3",
             str(out_mp3)], check=True)
    return duration


def narrate_one(script_path, out_dir, jobs):
    name = script_path.stem

    def log(msg):
        print(f"[{name}] {msg}", flush=True)
    audio, title, sections = render(script_path.read_text(encoding="utf-8"), jobs, log)
    duration = master(audio, out_dir / f"{name}.mp3", title, int(name[:2]), 16, sections)
    log(f"done: {duration / 60:.1f} min")


def build_index(out_dir):
    """Write tracks.js for the player page from the MP3s' tags and chapter markers."""
    tracks = []
    for mp3 in sorted(out_dir.glob("[01][0-9]-*.mp3")):
        probe = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_chapters", str(mp3)],
            capture_output=True, text=True, check=True).stdout)
        tags = probe["format"].get("tags", {})
        tracks.append({
            "file": mp3.name,
            "text": f"../{mp3.stem}.md",
            "title": tags.get("title", mp3.stem),
            "duration": round(float(probe["format"]["duration"]), 1),
            "sections": [{"title": c["tags"]["title"], "start": round(float(c["start_time"]), 1)}
                         for c in probe.get("chapters", [])],
        })
    body = json.dumps(tracks, indent=1, ensure_ascii=False)
    (out_dir / "tracks.js").write_text(
        "// Generated by tools/narrate.py --index. Track list and section markers for the Persian player.\n"
        f"window.TRACKS = {body};\n", encoding="utf-8")
    return tracks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chapters", nargs="*", help="chapter numbers, e.g. 01 05")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--jobs", type=int, default=4, help="requests to Azure at a time")
    ap.add_argument("--out", default=str(AUDIO))
    ap.add_argument("--say", nargs=2, metavar=("TEXT", "WAV"))
    ap.add_argument("--role", default="say", help="role for --say (say, quote, voice1, voice2...)")
    ap.add_argument("--index", action="store_true", help="only rebuild tracks.js")
    args = ap.parse_args()

    if args.say:
        sf.write(args.say[1], speak(args.say[0], args.role), SR)
        return
    out_dir = Path(args.out)
    if args.index:
        build_index(out_dir)
        return
    scripts = sorted(SCRIPTS.glob("[01][0-9]-*.txt"))
    if not args.all:
        scripts = [s for s in scripts if s.name[:2] in args.chapters]
    if not scripts:
        sys.exit("no scripts selected")
    for s in scripts:
        narrate_one(s, out_dir, args.jobs)
    build_index(out_dir)


if __name__ == "__main__":
    main()
