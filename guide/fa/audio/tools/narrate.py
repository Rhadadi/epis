#!/usr/bin/env python3
"""Render the Persian narration scripts to MP3 with Gooya Bozorg, a Persian Chatterbox model.

    python3 narrate.py 01                  # one chapter
    python3 narrate.py --all               # every chapter
    python3 narrate.py --say "متن" out.wav --role quote   # one line to a WAV file
    python3 narrate.py 01 --plan           # show how the script is cut up, render nothing
    python3 narrate.py --index             # rebuild tracks.js for the player from the MP3s

This is the Persian counterpart of guide/audio/tools/narrate.py and reads the
same script format (see make_script.py).

The voice is Gooya Bozorg v1.5 (huggingface.co/Reza2kn/Gooya-Bozorg-v1.5), a
byte-identical repackaging of Thomcles/Chatterbox-TTS-Persian-Farsi: Resemble
AI's Chatterbox multilingual model fine-tuned on Persian, licensed CC BY-NC 4.0
(non-commercial use, with attribution). It clones the voice of a short
reference recording. voice/narrator.flac is ten seconds of the Iranian narrator
of the Mana-TTS dataset (huggingface.co/datasets/MahtaFetrat/Mana-TTS, file
559-81.wav), which is public domain (CC0). Chatterbox also adds Resemble AI's
inaudible watermark to what it generates.

To run faster on an ordinary processor, two parts of the model are swapped
for lighter ones: the speech decoder is the two-step "meanflow" decoder of
Chatterbox Turbo (huggingface.co/ResembleAI/chatterbox-turbo, MIT licence),
which turns the same speech tokens into sound, and the Persian text-to-token
model runs with 8-bit weights. Together they halve the rendering time, and a
speech recogniser understands the result as well as the original setup's.

Needs: the chatterbox-tts package (with torch), soundfile, numpy and ffmpeg,
and the Gooya weights folder (its inference.py, ve.safetensors,
t3_fa.safetensors, s3gen.safetensors, grapheme_mtl_merged_expanded_v1.json) in
$GOOYA_DIR. The Turbo decoder is downloaded from Hugging Face, or read from
$MEANFLOW_DECODER. A GPU is used when there is one. On a four-core CPU the
model still runs about three times slower than real time, so a chapter takes
a few hours there.

Long paragraphs are cut into pieces of a few sentences, the length the model
reads well. Each piece is checked: if its length does not fit the amount of
text (the model skipped words or ran on), it is generated again with another
seed. Pieces are cached in $NARRATE_CACHE (default: tools/.narrate-cache), so
an interrupted run carries on where it stopped and editing a script only
re-renders the changed lines.

lexicon.txt gives spoken forms for words the voice would otherwise misread,
mostly Latin, German and French expressions, which are written in Persian
letters so that they are said the way an Iranian reader says them.
"""

import argparse
import functools
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf

os.environ.setdefault("TQDM_DISABLE", "1")  # the model draws a progress bar for every sentence

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parent
SCRIPTS = AUDIO / "scripts"
CACHE = Path(os.environ.get("NARRATE_CACHE", HERE / ".narrate-cache"))
REFERENCE = HERE / "voice" / "narrator.flac"
SR = 24000

ALBUM = "تسلط بر معرفت‌شناسی (نسخهٔ صوتی)"
MODEL = "gooya-bozorg-v1.5+turbo-meanflow-decoder"
CFG_WEIGHT = 0.5      # the model's defaults, as in the approved sample
TEMPERATURE = 0.8
MAX_CHARS = 220       # longest piece of text read in one go
PIECE_GAP = 0.30      # seconds between the pieces of one paragraph
TRIES = 4             # generations per piece before keeping the best one

# role: (exaggeration, pitch in semitones, tempo, seconds of silence before, seconds after)
# Exaggeration is Chatterbox's expressiveness setting (0.5 is neutral). There is
# one narrator, so the two speakers of a dialogue are told apart by a small
# pitch shift, and quotations by a slightly slower pace.
STYLE = {
    "say":        (0.50, 0.0, 1.00, 0.00, 0.75),
    "item":       (0.50, 0.0, 1.00, 0.00, 0.50),
    "aside":      (0.50, 0.0, 0.97, 0.00, 0.50),
    "opening":    (0.50, 0.0, 0.95, 0.30, 0.00),
    "section":    (0.50, 0.0, 0.96, 0.45, 0.95),
    "subsection": (0.50, 0.0, 0.97, 0.85, 0.60),
    "quote":      (0.50, 0.0, 0.96, 0.20, 0.40),
    "attr":       (0.50, 0.0, 1.00, 0.00, 0.40),
    "cue":        (0.50, 0.0, 0.97, 0.20, 0.30),
    "label":      (0.50, 0.0, 1.00, 0.10, 0.25),
    "voice1":     (0.60, 1.5, 1.02, 0.00, 0.40),
    "voice2":     (0.45, -1.5, 0.98, 0.00, 0.40),
    "voice3":     (0.55, 0.8, 1.00, 0.00, 0.40),
    "question":   (0.50, 0.0, 0.97, 0.00, 0.20),
    "answer":     (0.50, 0.0, 1.00, 0.00, 0.75),
}


# ---------------------------------------------------------------------------
# Text


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


def respell(text):
    return LEX_RE.sub(lambda m: LEXICON[m.group(1).lower()], text) if LEX_RE else text


def sentences(text):
    out, start = [], 0
    for m in re.finditer(r'[.!?؟]+[»"]?(?=\s|$)', text):
        out.append(text[start:m.end()].strip())
        start = m.end()
    out.append(text[start:].strip())
    return [s for s in out if s]


def split_long(s):
    """Cut a sentence longer than MAX_CHARS at semicolons, then commas, then a space."""
    if len(s) <= MAX_CHARS:
        return [s]
    for sep in ("؛ ", "، ", ": ", ", "):
        parts = s.split(sep)
        if len(parts) == 1:
            continue
        out, cur = [], ""
        for i, p in enumerate(parts):
            piece = p + (sep.strip() if i < len(parts) - 1 else "")
            if cur and len(cur) + 1 + len(piece) > MAX_CHARS:
                out.append(cur)
                cur = piece
            else:
                cur = f"{cur} {piece}".strip()
        out.append(cur)
        return [y for x in out for y in split_long(x)]
    mid = len(s) // 2
    cut = min((i for i, c in enumerate(s) if c == " "), key=lambda i: abs(i - mid), default=None)
    if cut is None:
        return [s]
    return split_long(s[:cut]) + split_long(s[cut + 1:])


def pieces(text):
    """A cue's text as the pieces the model reads: whole sentences, grouped up to MAX_CHARS."""
    out = []
    for s in (y for x in sentences(respell(text)) for y in split_long(x)):
        if out and len(out[-1]) + 1 + len(s) <= MAX_CHARS and out[-1][-1] in ".!?؟»\"":
            out[-1] = f"{out[-1]} {s}"
        else:
            out.append(s)
    # A piece cut at a semicolon or comma keeps a rising, unfinished tone.
    return [re.sub(r"[،؛:]$", ",", p) for p in out]


def letters(text):
    return sum(1 for c in text if unicodedata.category(c).startswith("L"))


# ---------------------------------------------------------------------------
# The model (loaded once in each worker process)


_TTS = None


def load(threads):
    global _TTS
    import torch
    if threads:
        torch.set_num_threads(threads)
    model_dir = os.environ.get("GOOYA_DIR")
    if not model_dir or not (Path(model_dir) / "t3_fa.safetensors").exists():
        sys.exit("set GOOYA_DIR to a folder with the Gooya Bozorg v1.5 files (huggingface.co/Reza2kn/Gooya-Bozorg-v1.5)")
    sys.path.insert(0, model_dir)
    from inference import load_model  # Gooya's loader
    from chatterbox.models.s3gen import S3Gen
    from safetensors.torch import load_file
    device = "cuda" if torch.cuda.is_available() else "cpu"
    _TTS = load_model(Path(model_dir), device)
    decoder = os.environ.get("MEANFLOW_DECODER")
    if not decoder:
        from huggingface_hub import hf_hub_download
        decoder = hf_hub_download("ResembleAI/chatterbox-turbo", "s3gen_meanflow.safetensors")
    s3gen = S3Gen(meanflow=True)
    s3gen.load_state_dict(load_file(decoder), strict=True)
    decode = s3gen.inference

    def inference(speech_tokens, **kw):  # like Turbo, pass on speech tokens only, no control tokens
        return decode(speech_tokens=speech_tokens[speech_tokens < 6561], **kw)
    s3gen.inference = inference
    _TTS.s3gen = s3gen.to(device).eval()
    if int8():
        _TTS.t3.tfmr = torch.ao.quantization.quantize_dynamic(_TTS.t3.tfmr, {torch.nn.Linear}, dtype=torch.qint8)
    _TTS.prepare_conditionals(str(REFERENCE), exaggeration=0.5)
    assert _TTS.sr == SR


@functools.cache
def int8():
    """8-bit weights on a CPU only; a GPU is fast enough without them."""
    import torch
    return not torch.cuda.is_available()


@functools.cache
def setup():
    """What, besides the text, decides how a piece sounds."""
    return [MODEL + ("+int8" if int8() else ""), hashlib.sha1(REFERENCE.read_bytes()).hexdigest(), CFG_WEIGHT, TEMPERATURE]


def cache_key(text, exaggeration):
    spec = json.dumps(setup() + [text, exaggeration], ensure_ascii=False)
    return hashlib.sha1(spec.encode()).hexdigest()


def cache_path(key):
    return CACHE / key[:2] / f"{key}.flac"


def trim(audio, threshold=0.004, keep=0.05):
    """Cut the silence at both ends, keeping a little air; pauses are ours to set."""
    idx = np.where(np.abs(audio) > threshold)[0]
    if len(idx) == 0:
        return audio[:0]
    a, b = max(0, idx[0] - int(keep * SR)), min(len(audio), idx[-1] + int(keep * SR))
    return audio[a:b]


def longest_gap(audio, frame=0.05, threshold=0.004):
    n = int(frame * SR)
    if len(audio) < n:
        return 0.0
    quiet = np.abs(audio[: len(audio) // n * n]).reshape(-1, n).max(axis=1) < threshold
    run = best = 0
    for q in quiet:
        run = run + 1 if q else 0
        best = max(best, run)
    return best * frame


def misfit(text, audio):
    """How far a take's length is from what the text needs (0 is spot on), and whether it is acceptable."""
    dur = len(audio) / SR
    expected = 0.25 + letters(text) / 8.5  # the narrator reads about 8.5 letters a second
    if dur == 0:
        return math.inf, False
    score = abs(math.log(dur / expected))
    ok = 0.6 * expected - 0.3 <= dur <= 1.6 * expected + 0.8 and longest_gap(audio) < 1.6
    return score, ok


def generate(job):
    """Worker: generate one piece, retrying with new seeds if it looks wrong, and cache it."""
    import torch
    text, exaggeration, key = job
    best = None
    for attempt in range(TRIES):
        torch.manual_seed(int(key[:8], 16) + attempt)
        try:
            wav = _TTS.generate(text=text, language_id=None, exaggeration=exaggeration,
                                cfg_weight=CFG_WEIGHT, temperature=TEMPERATURE)
        except Exception as e:  # a bad draw; try another seed
            print(f"  generation failed ({e.__class__.__name__}: {e}), retrying: {text[:60]}", flush=True)
            continue
        audio = trim(wav.squeeze(0).cpu().numpy().astype(np.float32))
        score, ok = misfit(text, audio)
        if best is None or score < best[1]:
            best = (audio, score, ok)
        if ok:
            break
    if best is None:
        raise RuntimeError(f"could not generate: {text}")
    path = cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    sf.write(tmp, best[0], SR, format="FLAC", subtype="PCM_16")
    os.replace(tmp, path)
    return key, len(best[0]) / SR, best[2], attempt + 1, text


def run_jobs(jobs, workers, threads, log):
    """Generate every uncached piece, in several processes when asked."""
    if not jobs:
        return
    start, done, spoken = time.time(), 0, 0.0

    def report(result):
        nonlocal done, spoken
        _, dur, ok, tries, text = result
        done += 1
        spoken += dur
        if not ok:
            log(f"  kept a doubtful take after {tries} tries: {text[:60]}…")
        if done % 10 == 0 or done == len(jobs):
            elapsed = time.time() - start
            eta = elapsed / done * (len(jobs) - done)
            log(f"  {done}/{len(jobs)} pieces, {spoken / 60:.1f} min of speech in {elapsed / 60:.0f} min"
                f" (about {eta / 3600:.1f} h left)")

    if workers <= 1:
        if _TTS is None:
            load(threads)
        for job in jobs:
            report(generate(job))
        return
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(workers, initializer=load, initargs=(threads,)) as pool:
        for result in pool.imap_unordered(generate, jobs):
            report(result)


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


def shape(audio, semitones, tempo):
    """Shift pitch and change pace with ffmpeg (resampling for pitch, WSOLA for pace)."""
    if not semitones and tempo == 1.0 or not len(audio):
        return audio
    ratio = 2 ** (semitones / 12)
    chain = f"asetrate={round(SR * ratio)},aresample={SR},atempo={tempo / ratio:.5f}"
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
         "-af", chain, "-f", "f32le", "-ar", str(SR), "-ac", "1", "-"],
        input=audio.astype(np.float32).tobytes(), capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


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
    for kind, _ in cues:
        if kind not in STYLE and kind not in ("title", "pause", "think", "chime"):
            raise ValueError(f"unknown cue @{kind}")
    return cues


def plan(cues):
    """Each spoken cue as a list of (piece text, exaggeration, cache key)."""
    out = {}
    for kind, text in cues:
        if kind in STYLE and text and (kind, text) not in out:
            exaggeration = STYLE[kind][0]
            out[(kind, text)] = [(p, exaggeration, cache_key(p, exaggeration)) for p in pieces(text)]
    return out


def speak(parts, kind):
    _, semitones, tempo, _, _ = STYLE[kind]
    audio = []
    for i, (_, _, key) in enumerate(parts):
        if i:
            audio.append(silence(PIECE_GAP))
        audio.append(sf.read(cache_path(key), dtype="float32")[0])
    return shape(np.concatenate(audio), semitones, tempo)


def render(script, workers, threads, log):
    """Script text to (audio, title, sections), where sections are (title, seconds)."""
    cues = parse(script)
    parts = plan(cues)
    jobs = {key: (text, ex, key) for ps in parts.values() for text, ex, key in ps}
    todo = [job for key, job in jobs.items() if not cache_path(key).exists()]
    log(f"{len(parts)} lines, {len(jobs)} pieces, {len(todo)} to generate")
    run_jobs(todo, workers, threads, log)

    out, sections, title = [silence(0.8)], [], ""
    length = [len(out[0])]

    def add(a):
        out.append(a)
        length[0] += len(a)

    for kind, text in cues:
        if kind == "title":
            title = text
        elif kind in ("pause", "think"):
            add(silence(float(text)))
        elif kind == "chime":
            add(chime())
        elif kind in STYLE:
            _, _, _, before, after = STYLE[kind]
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
                add(speak(parts[(kind, text)], kind))
            add(silence(after))
    add(silence(1.5))
    return np.concatenate(out), title, sections


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
                 "comment=Narrated with Gooya Bozorg v1.5 (Chatterbox Persian, CC BY-NC 4.0),"
                 " voice cloned from the CC0 Mana-TTS narrator."]
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


def narrate_one(script_path, out_dir, workers, threads):
    name = script_path.stem

    def log(msg):
        print(f"[{name}] {msg}", flush=True)
    audio, title, sections = render(script_path.read_text(encoding="utf-8"), workers, threads, log)
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
    ap.add_argument("--workers", type=int, default=0,
                    help="model processes (default: 1 on a GPU, one per two CPU cores otherwise)")
    ap.add_argument("--out", default=str(AUDIO))
    ap.add_argument("--say", nargs=2, metavar=("TEXT", "WAV"))
    ap.add_argument("--role", default="say", help="role for --say (say, quote, voice1, voice2...)")
    ap.add_argument("--plan", action="store_true", help="only show how the scripts are cut into pieces")
    ap.add_argument("--index", action="store_true", help="only rebuild tracks.js")
    args = ap.parse_args()

    workers = args.workers
    if not workers:
        import torch
        workers = 1 if torch.cuda.is_available() else max(1, (os.cpu_count() or 2) // 2)
    threads = max(1, (os.cpu_count() or 1) // workers)

    if args.say:
        parts = [(p, STYLE[args.role][0], cache_key(p, STYLE[args.role][0])) for p in pieces(args.say[0])]
        run_jobs([p for p in parts if not cache_path(p[2]).exists()], 1, os.cpu_count(), print)
        sf.write(args.say[1], speak(parts, args.role), SR)
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
    if args.plan:
        for s in scripts:
            parts = plan(parse(s.read_text(encoding="utf-8")))
            ps = [p for v in parts.values() for p in v]
            chars = sum(len(p[0]) for p in ps)
            cached = sum(cache_path(p[2]).exists() for p in ps)
            print(f"{s.stem}: {len(ps)} pieces, {chars} characters, about "
                  f"{sum(0.25 + letters(p[0]) / 8.5 for p in ps) / 60:.0f} min of speech, {cached} cached")
        return
    for s in scripts:
        narrate_one(s, out_dir, workers, threads)
    if len(list(out_dir.glob("[01][0-9]-*.mp3"))) == 16:
        build_index(out_dir)
    else:
        print("tracks.js is written once all 16 chapters exist (or run --index)")


if __name__ == "__main__":
    main()
