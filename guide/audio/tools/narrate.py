#!/usr/bin/env python3
"""Render narration scripts to MP3 with the Kokoro-82M text-to-speech model.

    python3 narrate.py 01                 # one chapter
    python3 narrate.py --all --jobs 4     # every chapter, four at a time
    python3 narrate.py --phonemes "Text"  # show how a line will be pronounced
    python3 narrate.py --index            # rebuild tracks.js for the player from the MP3s

Needs: onnxruntime, kokoro-onnx, misaki, spacy, textblob, soundfile, numpy,
num2words, espeak-ng and ffmpeg. The model and voices are looked up in
$KOKORO_DIR (default: tools/kokoro): kokoro-v1.0.onnx, kokoro-v1.0.int8.onnx or
kokoro-quantized.onnx, and voices-v1.0.bin or voices-v1.0.npz (both are NumPy
archives of the Kokoro v1.0 voice packs). Rendered sentences are cached in
$NARRATE_CACHE (default: tools/.narrate-cache), so after editing a script or the
lexicon only the changed lines are synthesized again.

What makes the reading sound less mechanical:
  - pronunciation comes from misaki, the grapheme-to-phoneme system Kokoro was
    trained with, fed with part-of-speech tags so that "a", "the", "read",
    "lead" and so on come out right, plus a lexicon for names and foreign terms;
  - quotations and each side of a dialogue get their own voice;
  - pacing varies: headings are slower, set-off examples a touch slower,
    list items get shorter gaps than paragraphs, sentences and clauses get
    real pauses, and review questions get silence to think in;
  - a soft chime marks new sections and a quieter bell marks lesson boxes.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parent
SCRIPTS = AUDIO / "scripts"
KOKORO_DIR = Path(os.environ.get("KOKORO_DIR", HERE / "kokoro"))
CACHE = Path(os.environ.get("NARRATE_CACHE", HERE / ".narrate-cache"))
SR = 24000

ALBUM = "Mastering Epistemology (Audio Edition)"

# Voices are Kokoro v1.0 voice packs. British voices (bf_, bm_) get British
# pronunciation.
VOICES = {
    "narrator": "af_heart",
    "quote": "am_michael",
    "voice1": "am_puck",
    "voice2": "bf_emma",
    "voice3": "am_fenrir",
}

# role: (voice, speed, seconds of silence before, seconds after)
STYLE = {
    "say":        ("narrator", 1.00, 0.00, 0.75),
    "item":       ("narrator", 1.00, 0.00, 0.50),
    "aside":      ("narrator", 0.95, 0.00, 0.50),
    "opening":    ("narrator", 0.90, 0.30, 0.00),
    "section":    ("narrator", 0.94, 0.45, 0.95),
    "subsection": ("narrator", 0.95, 0.85, 0.60),
    "quote":      ("quote",    0.95, 0.20, 0.40),
    "attr":       ("narrator", 1.00, 0.00, 0.40),
    "cue":        ("narrator", 0.97, 0.20, 0.30),
    "label":      ("narrator", 1.00, 0.10, 0.25),
    "voice1":     ("voice1",   1.00, 0.00, 0.40),
    "voice2":     ("voice2",   1.00, 0.00, 0.40),
    "voice3":     ("voice3",   1.00, 0.00, 0.40),
    "question":   ("narrator", 0.97, 0.00, 0.20),
    "answer":     ("narrator", 1.00, 0.00, 0.75),
}
SENTENCE_PAUSE = 0.32
CLAUSE_PAUSE = 0.10


# ---------------------------------------------------------------------------
# Pronunciation


ACRONYMS = {"AI", "US", "UK", "BCE", "CE", "BC", "AD", "IQ", "DNA", "RCT", "RCTs", "JTB", "IBE",
            "NASA", "COVID", "HIV", "AIDS", "MMR", "IPCC", "TV", "UN", "EU", "CIA", "FBI", "WHO",
            "CEO", "PhD", "OK", "NNP", "UFO", "UFOs", "GDP", "IVF", "BMJ", "NHS", "SAT", "MRI"}


def load_lexicon():
    """lexicon.txt: `word <tab> /phonemes/` or `word <tab> respelling`."""
    lex = {}
    for line in (HERE / "lexicon.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        word, value = [x.strip() for x in line.split("\t", 1)]
        lex[word] = value
    return lex


class TaggedNLP:
    """Stands in for a spaCy pipeline: spaCy's tokenizer plus the Pattern tagger
    bundled with TextBlob, with fixes for the tags misaki cares about most."""

    PUNCT = {".": ".", "!": ".", "?": ".", "…": ".", ",": ",", ";": ":", ":": ":",
             "—": ":", "–": ":", "(": "-LRB-", ")": "-RRB-"}

    def __init__(self):
        import spacy
        from textblob.en import parser
        self.blank = spacy.blank("en")
        self.parser = parser

    def __call__(self, text):
        doc = self.blank(text)
        words = [t.text for t in doc]
        tags = [t for _, t in self.parser.find_tags(words)] if words else []
        quote_open = True
        for k, tok in enumerate(doc):
            w, tag = tok.text, tags[k]
            nxt_tag = tags[k + 1] if k + 1 < len(tags) else "."
            nxt = words[k + 1] if k + 1 < len(words) else "."
            if w in ("-", "–") and k > 0 and not doc[k - 1].whitespace_ and tok.whitespace_ == "":
                tag = "HYPH"  # inside a compound such as non-black: no pause
            elif w in self.PUNCT:
                tag = self.PUNCT[w]
            elif w in ('"', "“", "”"):
                tag = "``" if (w == "“" or (w == '"' and quote_open)) else "''"
                quote_open = not quote_open if w == '"' else (w == "“")
            elif w in ("A", "a") and (nxt_tag.startswith(("VB", "MD")) or nxt in (
                    ".", ",", ";", ":", "?", "!", ")", "and", "or", "is", "was", "has", "'s")):
                tag = "NNP"  # a letter used as a name or variable
            elif len(w) == 1 and w.isupper() and w not in ("I", "A"):
                tag = "NNP"
            tok.tag_ = tag
        return doc


def strip_accents(word):
    word = word.replace("ʿ", "").replace("ʾ", "").replace("ø", "o").replace("æ", "ae")
    return "".join(c for c in unicodedata.normalize("NFKD", word) if not unicodedata.combining(c))


class Pronouncer:
    def __init__(self):
        from misaki import en, espeak
        self.lex = load_lexicon()
        self.g2p = {}
        nlp = TaggedNLP()
        for british in (False, True):
            g = object.__new__(en.G2P)
            g.version = None
            g.british = british
            g.nlp = nlp
            g.lexicon = en.Lexicon(british)
            g.fallback = espeak.EspeakFallback(british=british)
            g.unk = ""
            self.g2p[british] = g
        self.golds = self.g2p[False].lexicon.golds
        self.lex = {k.lower(): v for k, v in self.lex.items()}
        keys = sorted(self.lex, key=len, reverse=True)
        self.lex_re = re.compile(r"(?<![\w'])(" + "|".join(re.escape(k) for k in keys) + r")('s|')?(?![\w'])",
                                 re.IGNORECASE)

    def prepare(self, text):
        """Apply the lexicon, then make the rest of the text safe for misaki."""
        def sub(m):
            value = self.lex[m.group(1).lower()]
            poss = m.group(2) or ""
            if value.startswith("/"):
                ps = value.strip("/")
                if poss == "'s":
                    ps += "ɪz" if ps[-1] in "szʃʒʧʤ" else ("s" if ps[-1] in "ptkfθ" else "z")
                return f"[{m.group(1)}{poss}](/{ps}/)"
            return value + poss
        text = self.lex_re.sub(sub, text)
        parts = re.split(r"(\[[^\]]*\]\(/[^)]*/\))", text)
        for i in range(0, len(parts), 2):
            p = strip_accents(parts[i])
            p = re.sub(r"\b([A-Z]{3,})\b", lambda m: m.group(1) if m.group(1) in ACRONYMS or
                       m.group(1).lower() not in self.golds else m.group(1).lower(), p)
            parts[i] = p
        return "".join(parts)

    def __call__(self, text, british=False):
        ps, _ = self.g2p[british](self.prepare(text))
        return re.sub(r"\s+", " ", ps).strip()


# ---------------------------------------------------------------------------
# Sounds


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


class Narrator:
    def __init__(self, threads=1):
        import onnxruntime as rt
        from kokoro_onnx import Kokoro
        names = ("kokoro-v1.0.onnx", "kokoro-v1.0.int8.onnx", "kokoro-quantized.onnx")
        model = next((KOKORO_DIR / n for n in names if (KOKORO_DIR / n).exists()), None)
        voices = next((KOKORO_DIR / n for n in ("voices-v1.0.npz", "voices-v1.0.bin")
                       if (KOKORO_DIR / n).exists()), None)
        if model is None or voices is None:
            sys.exit(f"Kokoro model or voices not found in {KOKORO_DIR}")
        opts = rt.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = rt.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess = rt.InferenceSession(str(model), opts, providers=["CPUExecutionProvider"])
        self.kokoro = Kokoro.from_session(sess, str(voices))
        self.model_id = hashlib.sha1(model.read_bytes()[:1 << 20]).hexdigest()[:8]
        self.say = Pronouncer()

    def speak(self, text, role):
        voice_key, speed, _, _ = STYLE[role]
        voice = VOICES[voice_key]
        ps = self.say(text, british=voice[:1] == "b")
        if not ps:
            return silence(0)
        key = hashlib.sha1(f"{self.model_id}|{voice}|{speed}|{SENTENCE_PAUSE}|{CLAUSE_PAUSE}|{ps}"
                           .encode()).hexdigest()
        path = CACHE / key[:2] / f"{key}.flac"
        if path.exists():
            audio, _ = sf.read(path, dtype="float32")
            return audio
        audio, sr = self.kokoro.create(ps, voice=voice, speed=speed, is_phonemes=True,
                                       sentence_pause=SENTENCE_PAUSE, clause_pause=CLAUSE_PAUSE)
        assert sr == SR
        audio = audio.astype(np.float32)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, audio, SR, format="FLAC", subtype="PCM_16")
        return audio


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


def render(script, narrator, log=None):
    """Script text to (audio, title, sections), where sections are (title, seconds)."""
    pieces, sections, title = [silence(0.8)], [], ""
    length = [len(pieces[0])]

    def add(a):
        pieces.append(a)
        length[0] += len(a)

    cues = parse(script)
    for n, (kind, text) in enumerate(cues):
        if log and n % 25 == 0:
            log(f"{n}/{len(cues)}")
        if kind == "title":
            title = text
        elif kind == "pause":
            add(silence(float(text)))
        elif kind == "think":
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
            add(narrator.speak(text, kind))
            add(silence(after))
        else:
            raise ValueError(f"unknown cue @{kind}")
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
             f"{chain},loudnorm=I=-18:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
            capture_output=True, text=True, check=True).stderr
        stats = json.loads(measure[measure.rindex("{"):measure.rindex("}") + 1])
        norm = (f"{chain},loudnorm=I=-18:TP=-1.5:LRA=11:linear=true:"
                f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
                f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}")
        duration = len(audio) / SR
        meta = Path(tmp) / "meta.txt"
        lines = [";FFMETADATA1", f"title={title}", f"album={ALBUM}", "artist=Mastering Epistemology",
                 f"track={track}/{total}", "genre=Audiobook",
                 "comment=Narrated with the Kokoro-82M text-to-speech model (Apache-2.0)."]
        for k, (name, start) in enumerate(sections):
            stop = sections[k + 1][1] if k + 1 < len(sections) else duration
            lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}",
                      f"END={int(stop * 1000)}", f"title={name}"]
        meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-i", str(meta),
             "-map", "0:a", "-map_metadata", "1", "-map_chapters", "1", "-af", norm + ",aresample=24000",
             "-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "40k", "-id3v2_version", "3",
             str(out_mp3)], check=True)
    return duration


def track_info(script_path):
    return int(script_path.name[:2])


def narrate_one(script_path, out_dir, threads=1):
    narrator = Narrator(threads)
    script = script_path.read_text(encoding="utf-8")
    name = script_path.stem

    def log(msg):
        print(f"[{name}] {msg}", flush=True)
    audio, title, sections = render(script, narrator, log)
    out = out_dir / f"{name}.mp3"
    duration = master(audio, out, title, track_info(script_path), 16, sections)
    log(f"done: {duration / 60:.1f} min")
    return out


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
        "// Generated by tools/narrate.py --index. Track list and section markers for index.html.\n"
        f"window.TRACKS = {body};\n", encoding="utf-8")
    return tracks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chapters", nargs="*", help="chapter numbers, e.g. 01 05")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--threads", type=int, default=1, help="ONNX threads per job")
    ap.add_argument("--out", default=str(AUDIO))
    ap.add_argument("--phonemes", metavar="TEXT")
    ap.add_argument("--index", action="store_true", help="only rebuild tracks.js")
    args = ap.parse_args()

    if args.phonemes:
        print(Pronouncer()(args.phonemes))
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
    scripts.sort(key=lambda p: p.stat().st_size, reverse=True)  # longest first
    if args.jobs == 1:
        for s in scripts:
            narrate_one(s, out_dir, args.threads)
    else:
        with ProcessPoolExecutor(args.jobs) as pool:
            futures = {pool.submit(narrate_one, s, out_dir, args.threads): s for s in scripts}
            for f in as_completed(futures):
                f.result()
    build_index(out_dir)


if __name__ == "__main__":
    main()
