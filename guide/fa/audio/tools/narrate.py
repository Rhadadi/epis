#!/usr/bin/env python3
"""Render the Persian narration scripts to MP3 with Persian text-to-speech voices.

    python3 narrate.py 01                 # one chapter
    python3 narrate.py --all --jobs 4     # every chapter, four at a time
    python3 narrate.py --phonemes "متن"   # show how a line will be pronounced
    python3 narrate.py --say "متن" out.wav --voice narrator   # one line to a WAV file
    python3 narrate.py --index            # rebuild tracks.js for the player from the MP3s

This is the Persian counterpart of guide/audio/tools/narrate.py. The English
edition uses Kokoro-82M, which has no Persian voice, so the Persian edition uses
voices trained on Persian speech:

  - narrator: Piper VITS voice fa_IR «ganji_adabi» (medium), a male voice
    recorded reading literary Persian (dataset: CC0);
  - quotations and the second speaker in a dialogue: Matcha-TTS voice
    «khadijah», a female voice, with the Vocos 22 kHz vocoder, as packaged for
    sherpa-onnx;
  - the first speaker in a dialogue: Piper VITS voice fa_IR «ganji» (medium),
    the narrator's speaker in an everyday rather than a literary reading
    (dataset: CC0), much as an audiobook narrator voices a character.
    (Other Persian voices were tried for this part and were harder to follow.)

Model files are looked up in $FA_TTS_DIR (default: tools/voices):
  fa_IR-ganji_adabi-medium.onnx(.json), fa_IR-ganji-medium.onnx(.json),
  matcha-khadijah.onnx, matcha-khadijah.tokens.txt, vocos-22khz-univ.onnx
They come from the sherpa-onnx "tts-models" release on GitHub
(vits-piper-fa_IR-*-medium, matcha-tts-fa_en-khadijah, vocos-22khz-univ).

Pronunciation. All voices were trained on the phonemes that espeak-ng produces
for Persian, so espeak-ng does the grapheme-to-phoneme step. Two things improve it:
  - lexicon.txt fixes words espeak-ng gets wrong (mostly names). Persian entries
    are compiled into espeak-ng's Persian dictionary, so the fix also reaches
    inflected forms (گتیه، گتیه‌ای، گتیهٔ). For this the Persian dictionary
    sources are downloaded once from the espeak-ng repository, at a pinned
    commit, and compiled with the `espeak-ng` program.
  - Words in Latin script (English and Latin terms the chapters give at first
    mention) are turned into Persian sounds, the way a Persian speaker says
    them: from lexicon.txt when listed there, otherwise from espeak-ng's
    English pronunciation mapped onto the Persian sound system.
And one change for natural speech: «و» between two words is read as the
linked «ـُ» (کتاب‌ُ دفتر) after a consonant, as Iranian readers do, instead of
a separate «وَ» each time.

Rendered sentences are cached in $NARRATE_CACHE (default: tools/.narrate-cache),
so after editing a script or the lexicon only the changed lines are rendered again.

Needs: onnxruntime, piper-tts (for its espeak-ng bridge), soundfile, numpy,
librosa (for the Matcha voice), and the espeak-ng and ffmpeg programs.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parent
SCRIPTS = AUDIO / "scripts"
MODELS = Path(os.environ.get("FA_TTS_DIR", HERE / "voices"))
CACHE = Path(os.environ.get("NARRATE_CACHE", HERE / ".narrate-cache"))
ESPEAK_WORK = Path(os.environ.get("FA_ESPEAK_DIR", HERE / ".espeak"))
SR = 22050

ALBUM = "تسلط بر معرفت‌شناسی (نسخهٔ صوتی)"

# espeak-ng's Persian dictionary sources, at a pinned commit
ESPEAK_COMMIT = "ba90c8e9f440ad544f674a790bb5f53878b6ffc5"
ESPEAK_SOURCES = {
    "fa_list": "33b451d3bbe0ed6cc84eb03428277be35e90bfaaa511fbb6ce15d699232a5843",
    "fa_rules": "6a5d75f7bddeb9634a11eb6a5a5aa1ad2e8b170be32c6a322930bc5874138203",
}

# name: (kind, model file)
VOICES = {
    "narrator": ("vits", "fa_IR-ganji_adabi-medium.onnx"),
    "quote": ("matcha", "matcha-khadijah.onnx"),
    "voice1": ("vits", "fa_IR-ganji-medium.onnx"),
    "voice2": ("matcha", "matcha-khadijah.onnx"),
    "voice3": ("vits", "fa_IR-ganji-medium.onnx"),
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
# Each voice's natural pace differs; this brings them to a common reading speed.
PACE = {"narrator": 1.15, "quote": 0.97, "voice1": 1.0, "voice2": 0.97, "voice3": 1.0}
SENTENCE_PAUSE = 0.34
CLAUSE_PAUSE = 0.12      # between the pieces of a sentence too long to render in one go
MAX_PHONEMES = 380       # longer sentences are split at a comma


# ---------------------------------------------------------------------------
# Pronunciation


ESPEAK_NAMES = [("tʃ", "tS"), ("dʒ", "dZ"), ("ɑ", "A"), ("ʃ", "S"), ("ʒ", "Z"), ("q", "q1"), ("ʔ", "?"),
                ("r", "R"), ("ɡ", "g"), ("ː", "")]
VOWELS = "aeiouɑ"


def stress_on_vowel(ipa):
    """espeak-ng, and so the voices, put the stress mark right before the vowel: kripˈki -> kripkˈi."""
    out, stress = "", ""
    for ch in ipa:
        if ch in "ˈˌ":
            stress = ch
            continue
        if stress and ch in VOWELS:
            out += stress
            stress = ""
        out += ch
    return out


def to_espeak(ipa):
    """IPA with Persian sounds to espeak-ng's Persian phoneme names; the stress mark moves onto the vowel."""
    out, stress = "", ""
    for ch in ipa:
        if ch in "ˈˌ":
            stress = "'" if ch == "ˈ" else ","
            continue
        if stress and ch in VOWELS:
            out += stress
            stress = ""
        out += ch
    for a, b in ESPEAK_NAMES:
        out = out.replace(a, b)
    return out


def load_lexicon():
    """lexicon.txt: `word <tab> /ipa/`.

    A single Persian word goes into espeak-ng's Persian dictionary (so it also
    works with suffixes and the ezafe); anything else (Latin script, or several
    Persian words joined by a space or ZWNJ, which espeak-ng looks up piece by
    piece) is replaced by its phonemes directly.
    """
    persian, ipa = {}, {}
    for line in (HERE / "lexicon.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        word, value = [x.strip() for x in line.split("\t", 1)]
        value = value.strip("/")
        if re.fullmatch(r"[\u0600-\u06FF]+", word):
            persian[word] = to_espeak(value)
        else:
            ipa[word] = stress_on_vowel(value)
    return persian, ipa


def fetch_espeak_sources():
    ESPEAK_WORK.mkdir(parents=True, exist_ok=True)
    src = ESPEAK_WORK / "dictsource"
    src.mkdir(exist_ok=True)
    for name, digest in ESPEAK_SOURCES.items():
        path = src / name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            continue
        url = f"https://raw.githubusercontent.com/espeak-ng/espeak-ng/{ESPEAK_COMMIT}/dictsource/{name}"
        data = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != digest:
            sys.exit(f"{name}: checksum mismatch for {url}")
        path.write_bytes(data)
    return src


def espeak_data(persian_lexicon):
    """A copy of piper's espeak-ng data with the Persian dictionary rebuilt from source plus our lexicon."""
    from piper.voice import ESPEAK_DATA_DIR
    extra = "".join(f"{w}\t{p}\n" for w, p in sorted(persian_lexicon.items()))
    key = hashlib.sha1((ESPEAK_COMMIT + extra).encode()).hexdigest()[:10]
    data = ESPEAK_WORK / f"data-{key}" / "espeak-ng-data"
    if (data / "fa_dict").exists():
        return data
    import fcntl
    ESPEAK_WORK.mkdir(parents=True, exist_ok=True)
    # Other renders may be running with an older dictionary, which espeak-ng reloads from
    # disk: build the new one beside it under a lock, and never delete a data folder here.
    with open(ESPEAK_WORK / "build.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (data / "fa_dict").exists():
            return data
        src = fetch_espeak_sources()
        (src / "fa_extra").write_text(extra, encoding="utf-8")
        tmp = ESPEAK_WORK / f"data-{key}.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(ESPEAK_DATA_DIR, tmp / "espeak-ng-data")
        env = dict(os.environ, ESPEAK_DATA_PATH=str(tmp))
        out = subprocess.run(["espeak-ng", "--compile=fa"], cwd=src, env=env, capture_output=True, text=True)
        if out.returncode != 0 or "fa_extra" not in out.stdout + out.stderr:
            sys.exit("espeak-ng --compile=fa failed:\n" + out.stdout + out.stderr)
        tmp.rename(data.parent)
    return data


# English (espeak-ng en-us) sounds mapped to the sounds of Persian, as a Persian
# speaker says an English word. The voices only know Persian sounds.
EN_TO_FA = [
    ("aɪə", "ɑje"), ("aɪ", "ɑj"), ("aʊ", "ɑu"), ("eɪ", "ej"), ("oʊ", "o"), ("ɔɪ", "oj"), ("əʊ", "o"),
    ("ɜːɹ", "er"), ("ɜː", "er"), ("ɚ", "er"), ("ɑːɹ", "ɑr"), ("ɔːɹ", "or"), ("ɪɹ", "ir"), ("ɛɹ", "er"),
    ("ʊɹ", "ur"), ("iə", "ije"), ("ʊə", "ue"),
    ("tʃ", "tʃ"), ("dʒ", "dʒ"), ("ŋɡ", "nɡ"), ("ŋk", "nk"), ("ŋ", "nɡ"),
    ("æ", "a"), ("ɑː", "ɑ"), ("ɑ", "ɑ"), ("ɒ", "ɑ"), ("ɔː", "o"), ("ɔ", "o"), ("ə", "e"), ("ɐ", "a"),
    ("ɛ", "e"), ("ɪ", "i"), ("ᵻ", "i"), ("ɨ", "i"), ("iː", "i"), ("uː", "u"), ("ʊ", "u"), ("ʌ", "a"),
    ("θ", "t"), ("ð", "d"), ("ɹ", "r"), ("ɾ", "t"), ("w", "v"), ("ʍ", "v"), ("ɫ", "l"), ("ʔ", ""),
    ("ç", "h"), ("c", "k"), ("y", "i"), ("ø", "o"), ("œ", "o"), ("ɣ", "q"), ("ʁ", "r"), ("χ", "x"),
    ("ɲ", "nj"), ("ʎ", "lj"), ("ɕ", "ʃ"), ("ʑ", "ʒ"), ("ʏ", "i"), ("ɯ", "u"), ("ɵ", "o"), ("ɘ", "e"),
    ("ɞ", "o"), ("ɤ", "o"), ("ɶ", "a"), ("ɜ", "e"), ("ː", ""), ("̩", ""), ("ʲ", ""), ("̃", "n"),
]
PERSIAN_SOUNDS = set("aeɑioudrntmbshʃkjvlzqfɡʔʒpx1ˈˌː ")


def persianize(ipa):
    out = unicodedata.normalize("NFD", ipa)
    for a, b in EN_TO_FA:
        out = out.replace(a, b)
    return "".join(c for c in out if c in PERSIAN_SOUNDS or c in ".,:;?!")


PUNCT = {"،": ",", ",": ",", "؛": ";", ";": ";", ":": ":", ".": ".", "!": "!", "؟": "?", "?": "?"}
LATIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž][A-Za-zÀ-ÖØ-öø-ÿĀ-ž'’\-]*(?:[ ][A-Za-zÀ-ÖØ-öø-ÿĀ-ž][A-Za-zÀ-ÖØ-öø-ÿĀ-ž'’\-]*)*")
CONSONANT_END = re.compile(r"[bdfhjklmnpqrstvxzɡʃʒʔ1]$")


class Pronouncer:
    def __init__(self):
        from piper import espeakbridge
        persian, self.ipa = load_lexicon()
        self.data = espeak_data(persian)
        self.bridge = espeakbridge
        espeakbridge.initialize(str(self.data))
        self.ipa_lower = {k.lower(): v for k, v in self.ipa.items()}
        keys = sorted(self.ipa_lower, key=len, reverse=True)
        self.latin_re = re.compile(r"(?<![\w'])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w'])",
                                   re.IGNORECASE) if keys else None
        persian_keys = sorted((k for k in self.ipa if not re.search(r"[A-Za-z]", k)), key=len, reverse=True)
        self.persian_re = re.compile(r"(?<![؀-ۿ‌])(" + "|".join(re.escape(k) for k in persian_keys) +
                                     r")(?![؀-ۿ])") if persian_keys else None

    def espeak(self, text, voice="fa"):
        self.bridge.set_voice(voice)
        clauses = []
        for phonemes, terminator, end_of_sentence in self.bridge.get_phonemes(text):
            phonemes = re.sub(r"\([^)]+\)", "", phonemes)
            clauses.append((phonemes, terminator, end_of_sentence))
        return clauses

    def english(self, words):
        key = words.lower()
        if key in self.ipa_lower:
            return self.ipa_lower[key]
        ps = " ".join(p for p, _, _ in self.espeak(words, "en-us"))
        return stress_on_vowel(persianize(ps).strip())

    def mark(self, text):
        """Replace Latin-script words and listed Persian words with [[phonemes]]."""
        if self.persian_re:
            text = self.persian_re.sub(lambda m: f"[[{self.ipa[m.group(1)]}]]", text)
        parts = re.split(r"(\[\[[^\]]*\]\])", text)
        return "".join(p if p.startswith("[[") else
                       LATIN.sub(lambda m: f" [[{self.english(m.group(0))}]] ", p) for p in parts)

    def __call__(self, text):
        """Text to a list of sentences, each a string of phonemes with punctuation."""
        text = unicodedata.normalize("NFC", text).replace("ي", "ی").replace("ك", "ک")
        text = text.replace("«", "").replace("»", "").replace("…", "،")
        # espeak-ng writes چ as t+ʃ, so ت‌ش across a joint would be heard as چ (معرفت‌شناسی): keep the joint audible
        text = re.sub(r"([تد])\u200c(?=[شژ])", r"\1 ", text)
        # the prefix ضد (ضدعقل‌گرایی، ضدِبخت): espeak-ng runs it into the next word with a stray vowel
        text = re.sub(r"(?<![\u0600-\u06FF])ضد(?=[\u0621-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06CC])", "ضد\u200c", text)
        text = re.sub(r"(?<![\u0600-\u06FF])ضدِ(?=[\u0621-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06CC])", "ضدِ ", text)
        text = self.mark(text)
        sentences, current = [], ""
        for part in re.split(r"(\[\[[^\]]*\]\])", text):
            if not part:
                continue
            if part.startswith("[["):
                current += part[2:-2].strip()
                continue
            m = re.match(r"^\s*([،,؛;:.!؟?]+)", part)
            if m and current:  # punctuation right after a [[...]] block: espeak-ng would read it as a word
                p = PUNCT[m.group(1)[0]]
                current = current.rstrip() + p + (" " if p in ",:;" else "")
                if p in ".!?":
                    sentences.append(current)
                    current = ""
                part = part[m.end():]
            if not part.strip():
                current += " " if part and current else ""
                continue
            lead = " " if part[:1].isspace() else ""
            clauses = self.espeak(part)
            for k, (ps, term, eos) in enumerate(clauses):
                if k == len(clauses) - 1 and term not in (".", "?", "!"):
                    eos = False  # the part ends before a [[...]] block, not at the end of a sentence
                piece = ps + term + (" " if term in (",", ":", ";") else "")
                current += (lead if k == 0 and current else "") + piece
                if eos:
                    sentences.append(current)
                    current = ""
            if part[-1:].isspace() and current and not current.endswith(" "):
                current += " "
        if current.strip():
            sentences.append(current)
        return [self.link_and(re.sub(r"\s+", " ", s).strip()) for s in sentences if s.strip()]

    @staticmethod
    def link_and(ps):
        """«و» after a consonant-final word is said as a linked «ـُ»: کتاب و دفتر -> ketɑbo daftar."""
        return re.sub(r"(\S*?)(ˌ?)(\S)\s+vˈa\s+(?=\S)",
                      lambda m: m.group(0) if not CONSONANT_END.search(m.group(3)) else
                      f"{m.group(1)}{m.group(2)}{m.group(3)}o ", ps)


# ---------------------------------------------------------------------------
# Voices


class VitsVoice:
    def __init__(self, model, threads):
        import onnxruntime as rt
        cfg = json.loads(Path(f"{model}.json").read_text(encoding="utf-8"))
        self.id_map = cfg["phoneme_id_map"]
        inf = cfg.get("inference", {})
        self.noise, self.noise_w = inf.get("noise_scale", 0.667), inf.get("noise_w", 0.8)
        self.session = session(model, threads)
        self.model_id = hashlib.sha1(Path(model).read_bytes()[:1 << 20]).hexdigest()[:8]

    def __call__(self, ids, speed):
        scales = np.array([self.noise, 1.0 / speed, self.noise_w], dtype=np.float32)
        x = np.array([ids], dtype=np.int64)
        audio = self.session.run(None, {"input": x, "input_lengths": np.array([x.shape[1]], dtype=np.int64),
                                        "scales": scales})[0]
        return audio.squeeze().astype(np.float32)


class MatchaVoice:
    def __init__(self, model, threads):
        self.acoustic = session(model, threads)
        self.vocoder = session(MODELS / "vocos-22khz-univ.onnx", threads)
        self.id_map = {}
        for line in Path(str(model).replace(".onnx", ".tokens.txt")).read_text(encoding="utf-8").splitlines():
            sym, idx = line[: line.rindex(" ")], int(line[line.rindex(" ") + 1:])
            self.id_map[sym if sym else " "] = [idx]
        self.model_id = hashlib.sha1(Path(model).read_bytes()[:1 << 20]).hexdigest()[:8]

    def __call__(self, ids, speed):
        import librosa
        x = np.array([ids], dtype=np.int64)
        mel, _ = self.acoustic.run(None, {"x": x, "x_lengths": np.array([x.shape[1]], dtype=np.int64),
                                          "scales": np.array([0.667, 1.0 / speed], dtype=np.float32)})
        mag, re_, im = self.vocoder.run(None, {"mels": mel})
        audio = librosa.istft(mag[0] * (re_[0] + 1j * im[0]), hop_length=256, win_length=1024, n_fft=1024,
                              window="hann", center=True)
        return audio.astype(np.float32)


def session(model, threads):
    import onnxruntime as rt
    opts = rt.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    opts.graph_optimization_level = rt.GraphOptimizationLevel.ORT_ENABLE_ALL
    return rt.InferenceSession(str(model), opts, providers=["CPUExecutionProvider"])


def to_ids(phonemes, id_map):
    """Piper's layout: start, then each phoneme followed by padding, then end."""
    ids = [id_map["^"][0], id_map["_"][0]]
    for ch in unicodedata.normalize("NFD", phonemes):
        if ch in id_map:
            ids += [id_map[ch][0], id_map["_"][0]]
    return ids + [id_map["$"][0]]


# ---------------------------------------------------------------------------
# Sounds


def tone(freq, dur, amp, decay):
    t = np.arange(int(dur * SR)) / SR
    env = np.exp(-t / decay) * np.minimum(1, t / 0.006)
    wave = (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
            + 0.12 * np.sin(2 * np.pi * 3.01 * freq * t))
    return (amp * env * wave).astype(np.float32)


def chime():
    """Two soft ascending notes, like a small bell (the same as the English edition's)."""
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


def split_long(ps):
    """Split a sentence longer than MAX_PHONEMES at commas, into pieces of reasonable length."""
    if len(ps) <= MAX_PHONEMES:
        return [ps]
    pieces, rest = [], ps
    while len(rest) > MAX_PHONEMES:
        cut = rest.rfind(", ", 0, MAX_PHONEMES)
        if cut < MAX_PHONEMES // 3:
            cut = rest.find(", ", MAX_PHONEMES)
        if cut < 0:
            break
        pieces.append(rest[: cut + 1].strip())
        rest = rest[cut + 2:]
    pieces.append(rest.strip())
    return [p for p in pieces if p]


def trim(audio, threshold=0.004, keep=0.04):
    """Cut leading and trailing near-silence the model leaves, keeping a little air."""
    idx = np.where(np.abs(audio) > threshold)[0]
    if len(idx) == 0:
        return audio[:0]
    a, b = max(0, idx[0] - int(keep * SR)), min(len(audio), idx[-1] + int(keep * SR))
    return audio[a:b]


class Narrator:
    def __init__(self, threads=1):
        self.say = Pronouncer()
        self.voices, loaded = {}, {}
        for name, (kind, file) in VOICES.items():
            path = MODELS / file
            if not path.exists():
                sys.exit(f"voice model not found: {path}")
            if file not in loaded:
                loaded[file] = (VitsVoice if kind == "vits" else MatchaVoice)(path, threads)
            self.voices[name] = loaded[file]

    def sentence(self, ps, voice_name, speed):
        voice = self.voices[voice_name]
        key = hashlib.sha1(f"{voice.model_id}|{speed:.3f}|{ps}".encode()).hexdigest()
        path = CACHE / key[:2] / f"{key}.flac"
        if path.exists():
            audio, _ = sf.read(path, dtype="float32")
            return audio
        audio = trim(voice(to_ids(ps, voice.id_map), speed))
        peak = float(np.max(np.abs(audio))) if len(audio) else 0
        if peak > 0:
            audio = audio / peak * 0.9  # voices differ in level; mastering sets the final loudness
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, audio, SR, format="FLAC", subtype="PCM_16")
        return audio

    def speak(self, text, role):
        voice_name, speed, _, _ = STYLE[role]
        speed *= PACE[voice_name]
        out = []
        for k, ps in enumerate(self.say(text)):
            if k:
                out.append(silence(SENTENCE_PAUSE))
            for j, piece in enumerate(split_long(ps)):
                if j:
                    out.append(silence(CLAUSE_PAUSE))
                out.append(self.sentence(piece, voice_name, speed))
        return np.concatenate(out) if out else silence(0)


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
                 "comment=Narrated with Persian text-to-speech voices (Piper ganji_adabi and ganji, Matcha-TTS khadijah)."]
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


def narrate_one(script_path, out_dir, threads=1):
    narrator = Narrator(threads)
    script = script_path.read_text(encoding="utf-8")
    name = script_path.stem

    def log(msg):
        print(f"[{name}] {msg}", flush=True)
    audio, title, sections = render(script, narrator, log)
    out = out_dir / f"{name}.mp3"
    duration = master(audio, out, title, int(name[:2]), 16, sections)
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
        "// Generated by tools/narrate.py --index. Track list and section markers for the Persian player.\n"
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
    ap.add_argument("--say", nargs=2, metavar=("TEXT", "WAV"))
    ap.add_argument("--voice", default="say", help="role for --say (say, quote, voice1, voice2...)")
    ap.add_argument("--index", action="store_true", help="only rebuild tracks.js")
    args = ap.parse_args()

    if args.phonemes:
        for s in Pronouncer()(args.phonemes):
            print(s)
        return
    if args.say:
        n = Narrator(args.threads)
        sf.write(args.say[1], n.speak(args.say[0], args.voice), SR)
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
    Pronouncer()  # build the espeak-ng dictionary once, before any workers start
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
