#!/usr/bin/env python3
"""Pauses after the headings of the published Persian audio.

The voices read a heading and the sentence after it as one stretch of speech,
so a section or subsection title often runs straight into its first sentence
with no pause at all. This gives every heading line of a published chapter
(../NN-*.mp3 with sync/NN-*.json) a pause after it, without narrating
anything again:

    section 1.0 s, subsection 0.8 s, cue and label 0.6 s,
    and a short named point (@item «...».) followed by its explanation 0.45 s

counting the silence already there. Where the heading is already followed by
silence, silent MP3 frames are put in the middle of it and nothing is
re-encoded. Where the voice runs on, the audio is cut at the quietest moment
between the heading's last word and the next one, found by forced alignment
with a Persian speech-recognition model (Aligner: the sync file's timestamps
are not exact enough), with a 10 ms fade either side of the pause; only that
stretch, out to quiet places on both sides, is encoded again, and MP3 frames are joined as in eleven_narrate.splice_frames
(silent donor frames carry the audio data the frames after a join borrow).
The sync file's times, the section markers and the duration move with the
audio; the sync file records the pauses ("heading_pauses"), and a chapter
that has them is left as it is.

    python3 heading_pauses.py --model DIR 01 02 ...    # add the pauses to these chapters
    python3 heading_pauses.py --model DIR --check 01   # only report the pause after each heading
    python3 heading_pauses.py --repair 01 02 ...       # make every join decodable by libmpg123 too

Needs numpy, torch, torchaudio and transformers, ffmpeg, and the model
m3hrdadfi/wav2vec2-large-xlsr-persian-v3 (Hugging Face) in DIR.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eleven_narrate import DELAY, FRAME, WEB, chain_reservoir, donor_frames, ffmpeg, mp3_frames, write_sync  # noqa: E402

AUDIO = Path(__file__).resolve().parent.parent
RATE = 24000
TARGET = {"section": 1.0, "subsection": 0.8, "cue": 0.6, "label": 0.6, "item": 0.45}
SHORT_ITEM = 45    # characters: an item this short, followed by its explanation, is a named point
QUIET = 0.01       # peak level of silence
FADE = (0.030, 0.006)  # seconds of fade out before a cut into speech, and in after it
SLACK = 0.03       # without the aligner: how far a cut may be from the word boundary the timestamps give


def target(h, n):
    """The pause a line h wants before the next line n (0: none)."""
    if h["kind"] == "item":
        return TARGET["item"] if len(h["text"]) <= SHORT_ITEM and n["kind"] == "say" and h["voice"] == n["voice"] else 0
    return TARGET.get(h["kind"], 0)


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def peaks(a, t0, t1, step=0.005):
    """Peak level of each step-long block of a from t0 to t1."""
    i0, i1, k = max(0, int(t0 * RATE)), min(len(a), int(t1 * RATE)), int(step * RATE)
    n = max(0, (i1 - i0) // k)
    return np.abs(a[i0:i0 + n * k]).reshape(n, k).max(axis=1) if n else np.zeros(0)


def silence_at(a, t, step=0.005):
    """The run of silence around time t: (start, end), or None where t is not silent."""
    if abs(a[int(t * RATE) - int(step * RATE) // 2:int(t * RATE) + int(step * RATE) // 2]).max(initial=0) >= QUIET:
        return None
    b = t
    while b > step and np.abs(a[int((b - step) * RATE):int(b * RATE)]).max() < QUIET:
        b -= step
    e = t
    while int((e + step) * RATE) < len(a) and np.abs(a[int(e * RATE):int((e + step) * RATE)]).max() < QUIET:
        e += step
    return b, e


class Aligner:
    """Where words start and end: CTC forced alignment with a Persian wav2vec2 model (letters of the Persian
    alphabet; m3hrdadfi/wav2vec2-large-xlsr-persian-v3 from Hugging Face). The sync file's timestamps can
    be 0.15 s out either way, more than the gap between two words, and now and then a second."""
    FOLD = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا", "ؤ": "و"})

    def __init__(self, model_dir):
        import torch
        import torchaudio
        from transformers import Wav2Vec2ForCTC
        self.torch, self.ta = torch, torchaudio
        self.vocab = json.loads((Path(model_dir) / "vocab.json").read_text(encoding="utf-8"))
        self.model = Wav2Vec2ForCTC.from_pretrained(model_dir).eval()

    def words(self, text):
        """The words of text in the model's letters; None for a word with other letters (Latin, digits),
        which the model cannot place."""
        t = re.sub(r"[\u064B-\u065F\u0670\u0654\u06D4]", "", text).translate(self.FOLD)
        out = []
        for w in re.split(r"[\s\-–—/]+", t):
            w = re.sub(r"[^\w\u200c]", "", w).strip("\u200c")
            if w:
                out.append(None if any(ch not in self.vocab or ch == "|" for ch in w) else w)
        return out

    def spans(self, a, t0, t1, words):
        """(start, end, confidence) of each word in a[t0:t1], which must hold these words and no others."""
        torch = self.torch
        x = torch.from_numpy(a[max(0, int(t0 * RATE)):int(t1 * RATE)].copy())
        y = self.ta.functional.resample(x, RATE, 16000)
        y = (y - y.mean()) / (y.std() + 1e-7)
        with torch.inference_mode():
            lp = torch.log_softmax(self.model(y[None]).logits, -1)
        tokens = [self.vocab[c] for w in words for c in w + "|"][:-1]
        ali, scores = self.ta.functional.forced_align(lp, torch.tensor([tokens]), blank=0)
        step = (t1 - t0) / lp.shape[1]
        out, cur = [], []
        for sp in self.ta.functional.merge_tokens(ali[0], scores[0].exp()) + [None]:
            if sp is None or sp.token == self.vocab["|"]:
                out.append((t0 + cur[0].start * step, t0 + cur[-1].end * step, float(np.mean([c.score for c in cur]))))
                cur = []
            else:
                cur.append(sp)
        return out

    def boundary(self, a, h, n, p=None):
        """The end of heading h's last word and the start of the next line's first word, or None where the
        words cannot be placed with confidence. The sync file's times can be a second out, so the audio
        aligned runs from the line before the heading (p) to the end of the next line (as much of them as
        the model can spell): a window that starts or ends inside other words would be forced onto them."""
        hw, nw = self.words(h["text"]), self.words(n["text"])
        if not hw or None in hw or not nw or nw[0] is None:
            return None
        nw = nw[:nw.index(None)] if None in nw else nw
        t1 = n["end"] + 0.3
        if len(nw) < len(self.words(n["text"])):  # up to a word the model cannot spell: that share of the line
            t1 = n["begin"] + (n["end"] - n["begin"]) * len(nw) / len(self.words(n["text"]))
        pw, t0 = [], h["begin"] - 0.3
        if p:
            words, said = self.words(p["text"]), max(0.1, p["end"] - p["begin"])
            j = len(words)
            while j > 0 and words[j - 1] is not None:  # the words after its last one the model cannot spell
                j -= 1
            if j < len(words):
                pw = words[j:][-max(1, int(len(words) * min(1.0, 8.0 / said))):]  # about 8 s at most
                t0 = p["end"] - said * len(pw) / len(words) - 0.3
        s = self.spans(a, t0, t1, pw + hw + nw)
        heading = s[len(pw):len(pw) + len(hw)]
        if min(c for _, _, c in heading) < 0.2:  # a word of the heading not found where the window says
            return None
        return heading[-1][1], s[len(pw) + len(hw)][0]


def find_cut(a, h, n, aligner, p=None):
    """Where to open the pause after heading h, and how much silence is already there: (time, seconds,
    whether the words were placed by the aligner). Between the heading's last word and the next line's
    first: the middle of the longest silence there, or else where the sound dips."""
    b = aligner.boundary(a, h, n, p) if aligner else None
    if b:
        he, nb = b
        lo, hi = min(he, nb - 0.02), nb + 0.01
    else:
        lo = max(h["begin"] + 0.6 * (h["end"] - h["begin"]), h["end"] - SLACK)
        hi = max(lo + 0.05, n["begin"] + SLACK)
    p = peaks(a, lo, hi)
    best, run, start = (0, 0), 0, 0
    for k, x in enumerate(p):
        if x < QUIET:
            run, start = (run + 1, start) if run else (1, k)
            best = max(best, (run, start))
        else:
            run = 0
    if best[0] >= 2:  # 10 ms of silence or more
        s = silence_at(a, lo + (best[1] + best[0] / 2) * 0.005)
        if s:
            return (s[0] + s[1]) / 2, s[1] - s[0], bool(b)
    # the voice runs on: cut just before the next word, where the sound dips. A CTC model marks a word's
    # first letter at or a little after the sound starts, and its last letter early, so the heading's
    # last sound may still be going on well after its last letter: a cut closer to the heading can leave
    # the end of its last vowel, alone, after the pause. Within the last 70 ms before the next word, where
    # there is a clear dip the cut goes at its start (a soft first sound, h or v, must follow the pause
    # whole); otherwise at the quietest moment.
    if b:
        lo, hi = min(max(he, nb - 0.07), nb - 0.02), nb + 0.01
    i0, i1 = int(lo * RATE), int(hi * RATE)
    win, hop = int(0.010 * RATE), int(0.0025 * RATE)
    e = np.array([10 * np.log10(float(np.mean(a[i:i + win] ** 2)) + 1e-12) for i in range(i0, max(i0 + 1, i1 - win), hop)])
    k = int(np.argmin(e))
    if b and len(e) > 4 and np.max(e) - e[k] >= 10:
        while k > 0 and e[k - 1] <= e.min() + 3:
            k -= 1
    return (i0 + k * hop + win // 2) / RATE, 0.0, bool(b)


def frame_at(t):
    """The frame whose audio starts at or just before time t (frame j holds (j-1)*FRAME - DELAY onward)."""
    return max(1, int((t + DELAY) / FRAME) + 1)


def start_of(j):
    return (j - 1) * FRAME - DELAY


def quiet_frame(a, j, level=QUIET, side=2):
    """Is the audio around the start of frame j silent, side frames either way (a decoder carries some of
    each frame into the next)?"""
    t = start_of(j)
    seg = a[max(0, int((t - side * FRAME) * RATE)):int((t + side * FRAME) * RATE)]
    return len(seg) > 0 and float(np.abs(seg).max()) < level


def plan(a, sync, aligner=None):
    """The pauses to add: [{line, cut, have, add, frame (a quiet frame to put silence before, or None),
    aligned}]."""
    lines, out = sync["lines"], []
    for i, (h, n) in enumerate(zip(lines, lines[1:])):
        want = target(h, n)
        if not want:
            continue
        cut, have, aligned = find_cut(a, h, n, aligner, lines[i - 1] if i else None)
        add = want - have
        if add < FRAME:
            continue
        if not have and not aligned:  # a cut into speech needs the words placed (a Latin word at the join)
            print(f"  left as it is: no pause after line {i + 1} «{h['text'][:40]}», its words could not be placed")
            continue
        j = frame_at(cut)
        near = [f for f in (j, j + 1, j - 1, j + 2) if quiet_frame(a, f) and abs(start_of(f) - cut) < have / 2]
        out.append({"line": i, "cut": cut, "have": have, "add": add, "frame": near[0] if near else None, "aligned": aligned})
    return out


def insert(path, sync, cuts, a):
    """Put the pauses into the MP3 at path (rewritten in place) and move the sync file's times."""
    old = path.read_bytes()
    fr = mp3_frames(old)
    audio_end = fr[-1][0] + fr[-1][1]
    off, length, _, _, room = fr[1]
    head = bytearray(old[off:off + length - room])
    head[2] &= ~0x02
    silent = bytes(head[:len(head) - 9]) + bytes(9) + bytes(72 * 48000 // RATE - len(head))  # no audio data: silence

    # the stretches to encode again: from a quiet frame before the first cut into speech to one after the
    # last, merging cuts that are close; a cut into silence inside such a stretch goes in with it
    work = []
    for c in sorted(cuts, key=lambda c: c["cut"]):
        if c["frame"] and not (work and work[-1]["type"] == "encode" and c["cut"] < start_of(work[-1]["f0"])):
            work.append({"type": "frames", "f0": c["frame"], "cuts": [c]})
            continue
        if work and work[-1]["type"] == "encode" and c["cut"] < start_of(work[-1]["f0"]) + 0.5:
            w = work[-1]
            w["cuts"].append(c)
        else:
            at = work[-1]["f0"] if work else 1
            fb = None
            for level in (QUIET, 2 * QUIET, 4 * QUIET):
                fb = next((j for j in range(frame_at(c["cut"] - FADE[0]) - 3, max(at, frame_at(c["cut"] - 10.0)) - 1, -1)
                           if quiet_frame(a, j, level, side=3)), None)
                if fb:
                    break
            if fb is None:
                raise SystemExit(f"{path.name}: no quiet place before {c['cut']:.2f} s")
            if work and work[-1]["type"] == "frames" and work[-1]["f0"] > fb:
                raise SystemExit(f"{path.name}: pauses at {c['cut']:.2f} s overlap")
            w = {"type": "encode", "fb": fb, "cuts": [c]}
            work.append(w)
        f0 = None
        for level in (QUIET, 2 * QUIET, 4 * QUIET):
            f0 = next((j for j in range(frame_at(c["cut"] + FADE[1]) + 3, min(len(fr), frame_at(c["cut"] + 15)))
                       if quiet_frame(a, j, level, side=3)), None)
            if f0:
                break
        if f0 is None:
            raise SystemExit(f"{path.name}: no quiet place after {c['cut']:.2f} s")
        w["f0"] = f0

    raw, at, extra, steps = [old[:fr[1][0]]], 1, 0.0, []
    tmp = path.parent / (path.stem + "-pauses")
    tmp.mkdir(exist_ok=True)
    fades = [np.sin(np.linspace(0, 1, int(f * RATE), dtype=np.float32) * np.pi / 2) ** 2 for f in FADE]
    for k, w in enumerate(work):
        f0 = w["f0"]
        donors, kd = donor_frames(old, fr, f0)
        if w["type"] == "frames":
            c = w["cuts"][0]
            n = max(kd, round(c["add"] / FRAME))
            raw += [old[fr[at][0]:fr[f0][0]], silent * (n - kd), donors]
            extra += n * FRAME
            steps.append((start_of(f0), extra))
            c["done"] = n * FRAME
        else:
            fb = w["fb"]
            # the stretch's audio, cut at each pause (faded out before it and in after it where the voice runs on)
            bounds = [(fb - 1) * FRAME] + [c["cut"] for c in w["cuts"]] + [start_of(f0)]
            pieces = [a[int(round(b * RATE)):int(round(e * RATE))].copy() for b, e in zip(bounds, bounds[1:])]
            parts, moved_here = [pieces[0]], extra
            for c, before, after in zip(w["cuts"], pieces, pieces[1:]):
                if not c["have"] and len(before) > len(fades[0]) and len(after) > len(fades[1]):
                    before[-len(fades[0]):] *= fades[0][::-1]
                    after[:len(fades[1])] *= fades[1]
                pause = int(round(c["add"] * RATE))
                parts += [np.zeros(pause, dtype=np.float32), after]
                moved_here += pause / RATE
                steps.append((c["cut"], moved_here))
                c["done"] = pause / RATE
            pcm = np.concatenate(parts)
            src, enc = tmp / f"{k}.f32", tmp / f"{k}.mp3"
            src.write_bytes(pcm.astype(np.float32).tobytes())
            ffmpeg("-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", str(src), *WEB, str(enc))
            new = enc.read_bytes()
            nf = mp3_frames(new)[1:]  # without its Xing/Info frame
            raw += [old[fr[at][0]:fr[fb][0]], new[nf[0][0]:nf[-1][0] + nf[-1][1]], donors]
            extra += (fb + len(nf) + kd - f0) * FRAME
            steps.append((start_of(f0), extra))
        at = f0
    raw.append(old[fr[at][0]:audio_end])

    def moved(t):
        return t + next((s for start, s in reversed(steps) if t >= start - 1e-6), 0.0)

    # tags and section markers as they are, the markers moved
    meta = tmp / "meta.txt"
    ffmpeg("-i", str(path), "-f", "ffmetadata", str(meta))
    text = re.sub(r"^(START|END)=(\d+)$", lambda m: f"{m.group(1)}={int(round(moved(int(m.group(2)) / 1000) * 1000))}",
                  meta.read_text(encoding="utf-8"), flags=re.M)
    meta.write_text(text, encoding="utf-8")
    joined, out = tmp / "joined.mp3", tmp / "out.mp3"
    joined.write_bytes(chain_reservoir(b"".join(raw))[0])
    ffmpeg("-i", str(joined), "-i", str(meta), "-map", "0:a", "-map_metadata", "1", "-map_chapters", "1", "-c", "copy",
           "-id3v2_version", "3", str(out))
    out.replace(path)
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()

    # the sync file: a heading ends by its cut and the next line starts after it, whatever the timestamps say
    lines = sync["lines"]
    for c in cuts:
        h, n = lines[c["line"]], lines[c["line"] + 1]
        h["end"] = min(h["end"], c["cut"])
        n["begin"] = max(n["begin"], c["cut"] + 1e-3)
    for l in lines:
        l["begin"], l["end"] = round(moved(l["begin"]), 3), round(moved(l["end"]), 3)
    for s in sync.get("segments", []):
        s["begin"], s["end"] = round(moved(s["begin"]), 3), round(moved(s["end"]), 3)
    sync["duration"] = round(moved(sync["duration"]), 3)
    return moved


def report(stem, a, sync, cuts):
    lines = sync["lines"]
    heads = sum(1 for h, n in zip(lines, lines[1:]) if target(h, n))
    kinds = {}
    for c in cuts:
        kinds[lines[c["line"]]["kind"]] = kinds.get(lines[c["line"]]["kind"], 0) + 1
    into = sum(1 for c in cuts if not c["have"])
    print(f"{stem}: {heads} headings, {len(cuts)} need a longer pause ({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))}); "
          f"{into} run straight into the next line, {sum(1 for c in cuts if c['frame'])} have silence to widen")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chapters", nargs="+", help="chapter numbers")
    ap.add_argument("--check", action="store_true", help="only report")
    ap.add_argument("--model", default=os.environ.get("HEADING_ALIGN_MODEL"),
                    help="the Persian wav2vec2 CTC model's directory (or HEADING_ALIGN_MODEL)")
    ap.add_argument("--repair", action="store_true",
                    help="only make the borrowed audio data of published chapters reachable frame by frame (chain_reservoir)")
    args = ap.parse_args()
    if args.repair:
        for n in args.chapters:
            path = next(AUDIO.glob(f"{int(n):02d}-*.mp3"))
            data, changed = chain_reservoir(path.read_bytes())
            if changed:
                tmp = path.with_suffix(".chain.mp3")
                tmp.write_bytes(data)
                out = path.with_suffix(".out.mp3")
                ffmpeg("-i", str(tmp), "-map", "0:a", "-map_metadata", "0", "-map_chapters", "0", "-c", "copy",
                       "-id3v2_version", "3", str(out))
                out.replace(path)
                tmp.unlink()
            print(f"{path.stem}: {changed} frames changed")
        return
    if not args.model:
        raise SystemExit("needs --model: a download of m3hrdadfi/wav2vec2-large-xlsr-persian-v3")
    aligner = Aligner(args.model)
    for n in args.chapters:
        found = sorted(AUDIO.glob(f"sync/{int(n):02d}-*.json"))
        if not found:
            raise SystemExit(f"chapter {n} is not published")
        sync_path = found[0]
        stem = sync_path.stem
        sync = json.loads(sync_path.read_text(encoding="utf-8"))
        if sync.get("heading_pauses") and not args.check:
            print(f"{stem}: has its pauses after headings")
            continue
        path = AUDIO / f"{stem}.mp3"
        a = decode(path)
        cuts = plan(a, sync, aligner)
        report(stem, a, sync, cuts)
        if args.check or not cuts:
            continue
        insert(path, sync, cuts, a)
        sync["heading_pauses"] = {**TARGET, "added": len(cuts)}
        write_sync(sync_path, sync)
        print(f"{stem}: {len(cuts)} pauses added; {sync['duration'] / 60:.1f} min")


if __name__ == "__main__":
    main()
