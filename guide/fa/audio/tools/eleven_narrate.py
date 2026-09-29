#!/usr/bin/env python3
"""Narrate the Persian chapters with ElevenLabs, in two voices, carefully and resumably.

    python3 eleven_narrate.py --dry-run               # characters, requests and predicted credits; no generation
    python3 eleven_narrate.py --test                  # one request of exactly 1,000 characters from chapter 1
    python3 eleven_narrate.py --chapter 1 --sample 4000   # the start of chapter 1 (about 4,000 characters) as a preview
    python3 eleven_narrate.py --chapter 3             # narrate one chapter
    python3 eleven_narrate.py --all                   # narrate every chapter
    python3 eleven_narrate.py --all --resume          # the same; segments already made are never made again

The text is the one the Gooya narration speaks (scripts/NN-*.txt, as in
transcripts/). Two narrators share it, so the listener gets a break from each
voice: the main voice (male) opens the chapter; after that the sections
alternate, the second voice (female) taking the first section, the main voice
the next, and so on, each reading its own section title. A quotation is read
by the voice that is not narrating the section; in dialogues the first
speaker is the male voice and the second the female; in the quiz she asks,
there is time to think, and he answers; he also closes the chapter
(role_of below).

A chapter becomes a row of segments, each read by one voice: a new segment
starts where the voice changes, where a section starts, and at the quiz's
thinking time, and a long run is cut, only between paragraphs or sentences,
at about 5,000 characters, so a bad take costs little to redo. Between
segments come silence and, at each section, the same soft chime as the Gooya
edition; these are made here with ffmpeg and cost nothing. Each segment is
sent with the request IDs of the same voice's previous segments (ElevenLabs
request stitching), so voice, pace and intonation run on across the joins.

Segments are generated with the timestamps endpoint, which returns the time
of every character; from it come the start and end of each spoken line,
written to a sync file like the Gooya edition's (for read-along and EPUB 3
Media Overlays). Segments are saved separately and joined without re-encoding
into one MP3 per chapter, with the chapter's title, tags and a marker for
each section.

Everything about the voices is fixed in the manifest at the first generation:
voices, model, voice settings, output format. Later runs refuse to go on with
anything different, so the whole book sounds the same.

Money: before every chapter (and every segment) the subscription is read, and
nothing is generated unless the remaining credits cover it; usage beyond the
plan's credits (overage) is never used, even where the account allows it.

Needs: the requests package and ffmpeg; ELEVENLABS_API_KEY in the
environment (the key is only read from there and never written anywhere).
Voices and model can be changed with --voice, --voice2 and --model before the
first generation. State lives in tools/.eleven/: manifest.json, segments/ and
chapters/ (each chapter's MP3 and sync file, for review before publishing).
"""

import argparse
import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parent
SCRIPTS = AUDIO / "scripts"
STATE = Path(os.environ.get("ELEVEN_STATE", HERE / ".eleven"))
MANIFEST = STATE / "manifest.json"
TEST_RESULT = HERE / "eleven-test" / "manifest.json"  # the committed --test measurement
SEGMENTS = STATE / "segments"
CHAPTERS = STATE / "chapters"
API = "https://api.elevenlabs.io/v1"

MODEL = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_v4_turbo")
VOICES = {"main": "VKDkQOjcRZb7aNtJGaWt", "second": "ndcUYGFbbd96WXiZVVaQ"}
SCHEME = "alternate-sections-v1"  # who reads what; see role_of
OUTPUT = "mp3_44100_128"
MAX_SEGMENT, TARGET_SEGMENT = 6000, 5000
TEST_CHARS = 1000
GAP = 0.35         # seconds of silence where the voice changes
LONG_PAUSE = 1.5   # pauses at least this long (the quiz's thinking time) become silence between segments

ALBUM = "تسلط بر معرفت‌شناسی (نسخهٔ صوتی)"


def parse(script):
    """The narration script format (see make_script.py): `@cue text` lines, or plain lines to say."""
    cues = []
    for line in script.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^@(\w+)(?:\s+(.*))?$", line)
        cues.append((m.group(1), (m.group(2) or "").strip()) if m else ("say", line))
    return cues


# ---------------------------------------------------------------------------
# Text


def paragraphs(script_path):
    """The chapter as spoken paragraphs: [(kind, text)], in order."""
    return [(k, t.strip()) for k, t in parse(script_path.read_text(encoding="utf-8"))
            if k not in ("title", "pause", "think", "chime") and t]


def sentences(text):
    parts, start = [], 0
    for m in re.finditer(r'[.!?؟]+[»"]?(?=\s|$)', text):
        parts.append(text[start:m.end()].strip())
        start = m.end()
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def plan_chapter(script_path):
    """The chapter as a row of segments:
        {"type": "speech", "role": "main"|"second", "lines": [(kind, text), ...]}
        {"type": "silence", "seconds": x}   {"type": "chime"}
    plus its title and the section markers [(title, index of the first segment of the section)]."""
    title, segs, markers = "", [], []
    cur, pending = None, 0.0
    cues = parse(script_path.read_text(encoding="utf-8"))
    sections = [i for i, (k, _) in enumerate(cues) if k == "section"]
    quiz = {i for i in sections if any(k == "question" for k, _ in cues[i + 1:next((j for j in sections if j > i), len(cues))])}
    narrator, count = "main", 0

    def flush():
        nonlocal cur
        if cur:
            segs.append(cur)
        cur = None

    def pause(seconds):
        if segs and segs[-1]["type"] == "silence":
            segs[-1]["seconds"] = max(segs[-1]["seconds"], seconds)
        else:
            segs.append({"type": "silence", "seconds": seconds})

    for i, (kind, text) in enumerate(cues):
        if kind == "section":
            count += 1
            last = i == sections[-1] and not quiz & {i}
            narrator = "main" if i in quiz or last else ("second" if count % 2 else "main")
        if kind == "title":
            title = text
            continue
        if kind in ("pause", "think"):
            pending = max(pending, float(text))
            if pending >= LONG_PAUSE:
                flush()
                pause(pending)
                pending = 0.0
            continue
        if kind == "chime":
            flush()
            pause(max(pending, 0.3))
            segs.append({"type": "chime"})
            pending = 0.0
            continue
        if not text:
            continue
        role = role_of(kind, narrator)
        if kind == "section":
            flush()
            pause(0.9)
            markers.append((text, len(segs)))
            segs.append({"type": "chime"})
            pause(0.45)
            pending = 0.0
        elif kind == "opening":
            markers.append((text, 0))
        size = sum(len(t) + 2 for _, t in cur["lines"]) if cur else 0
        if cur and (cur["role"] != role or size + len(text) > MAX_SEGMENT or size >= TARGET_SEGMENT):
            voice_change = cur["role"] != role
            flush()
            if voice_change or pending:
                pause(max(pending, GAP if voice_change else 0.0))
        if not cur:
            cur = {"type": "speech", "role": role, "lines": []}
        cur["lines"].append((kind, text))
        pending = 0.0
    flush()
    pause(1.5)
    for s in segs:  # a paragraph too long for one request is cut between sentences
        if s["type"] == "speech" and len(seg_text(s)) > MAX_SEGMENT:
            raise SystemExit(f"a paragraph in {script_path.name} is longer than {MAX_SEGMENT} characters; split it in the script")
    return title, segs, markers


def role_of(kind, narrator):
    """Which voice reads a line, given the voice narrating the section."""
    other = "second" if narrator == "main" else "main"
    return {"quote": other, "voice1": "main", "voice2": "second", "voice3": other,
            "question": "second", "answer": "main"}.get(kind, narrator)


def seg_text(seg):
    return "\n\n".join(t for _, t in seg["lines"])


def test_text(paras, n=TEST_CHARS):
    """Exactly n characters of whole sentences from the chapter: a run of consecutive sentences whose
    length, joined by a space inside a paragraph and by one or two line breaks between paragraphs, is n."""
    sents = [(s, i) for i, (_, text) in enumerate(paras) for s in sentences(text)]
    for a in range(len(sents)):
        length, breaks, b = len(sents[a][0]), 0, a + 1  # the run sents[a:b], one character per join
        while True:
            if length <= n <= length + breaks and (breaks or length == n):
                extra, parts = n - length, [sents[a][0]]
                for k in range(a + 1, b):
                    if sents[k][1] != sents[k - 1][1]:
                        parts.append("\n\n" if extra > 0 else "\n")
                        extra -= extra > 0
                    else:
                        parts.append(" ")
                    parts.append(sents[k][0])
                text = "".join(parts)
                assert len(text) == n, len(text)
                return text
            if b >= len(sents) or length > n:
                break
            breaks += sents[b][1] != sents[b - 1][1]
            length += 1 + len(sents[b][0])
            b += 1
    raise SystemExit(f"no run of whole sentences in chapter 1 is exactly {n} characters long")


def script(n):
    found = sorted(SCRIPTS.glob(f"{int(n):02d}-*.txt"))
    if not found:
        raise SystemExit(f"no script for chapter {n}")
    return found[0]


# ---------------------------------------------------------------------------
# ElevenLabs


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        raise SystemExit("ELEVENLABS_API_KEY is not set in this environment")
    return k


def call(method, path, **kw):
    import requests
    headers = {"xi-api-key": key(), **kw.pop("headers", {})}
    for attempt in range(6):
        try:
            r = requests.request(method, API + path, headers=headers, timeout=600, **kw)
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  network error ({e.__class__.__name__}), retrying in {wait}s", flush=True)
            time.sleep(wait)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(60, 2 ** attempt))
            continue
        return r
    raise SystemExit(f"ElevenLabs {path}: too many retries")


def subscription():
    """The plan's credits: used, limit, remaining, and whether the account could go over (overage)."""
    r = call("GET", "/user/subscription")
    if r.status_code != 200:
        raise SystemExit(f"could not read the subscription: {r.status_code} {r.text[:300]}")
    s = r.json()
    used, limit = s.get("character_count", 0), s.get("character_limit", 0)
    return {"tier": s.get("tier"), "status": s.get("status"), "used": used, "limit": limit, "remaining": limit - used,
            "can_extend": s.get("can_extend_character_limit"), "allowed_to_extend": s.get("allowed_to_extend_character_limit"),
            "resets": s.get("next_character_count_reset_unix")}


def voice_settings(vid):
    r = call("GET", f"/voices/{vid}/settings")
    if r.status_code != 200:
        raise SystemExit(f"could not read the settings of voice {vid}: {r.status_code} {r.text[:300]}")
    return r.json()


def cost_of(headers):
    h = {k.lower(): v for k, v in headers.items()}
    cost = h.get("character-cost") or h.get("x-character-count")
    return h, h.get("request-id") or h.get("x-request-id"), int(cost) if cost and cost.isdigit() else None


def speak(text, vid, settings, seed):
    """One plain generation (used by --test). Returns (mp3 bytes, request id, character cost, headers)."""
    body = {"text": text, "model_id": MODEL, "voice_settings": settings, "seed": seed}
    r = call("POST", f"/text-to-speech/{vid}", params={"output_format": OUTPUT}, json=body, headers={"Accept": "audio/mpeg"})
    if r.status_code != 200:
        raise RuntimeError(f"generation failed: {r.status_code} {r.text[:400]}")
    h, request_id, cost = cost_of(r.headers)
    return r.content, request_id, cost, h


def speak_timed(text, vid, settings, seed, previous=(), next_text=None):
    """One generation with character timings. Returns (mp3 bytes, alignment, request id, character cost)."""
    body = {"text": text, "model_id": MODEL, "voice_settings": settings, "seed": seed}
    if previous:
        body["previous_request_ids"] = list(previous)[-3:]
    if next_text:
        body["next_text"] = next_text
    r = call("POST", f"/text-to-speech/{vid}/with-timestamps", params={"output_format": OUTPUT}, json=body)
    if r.status_code != 200:
        raise RuntimeError(f"generation failed: {r.status_code} {r.text[:400]}")
    data = r.json()
    _, request_id, cost = cost_of(r.headers)
    return base64.b64decode(data["audio_base64"]), data.get("alignment") or data.get("normalized_alignment"), request_id, cost


# ---------------------------------------------------------------------------
# Manifest


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"chunks": []}


def save_manifest(m):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, MANIFEST)


def lock_settings(m):
    """The first generation fixes voices, model, settings and format; later runs must match them."""
    want = {"voices": VOICES, "model": MODEL, "output_format": OUTPUT, "scheme": SCHEME}
    if "voices" not in m:
        m.update(want)
        m["voice_settings"] = {role: voice_settings(v) for role, v in VOICES.items()}
        save_manifest(m)
    else:
        have = {k: m.get(k) for k in want}
        if have != want:
            raise SystemExit(f"the manifest was made with {have}; refusing to mix in {want}")
    return m["voice_settings"]


def sha1(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def seg_key(seg):
    return sha1(json.dumps([VOICES[seg["role"]], MODEL, OUTPUT, seg_text(seg)], ensure_ascii=False))


def rate(m):
    """Credits per character: measured by --test (here, or in the committed result for the same model), else assumed 1."""
    t = m.get("test")
    if not (t and t.get("credits_per_char")) and TEST_RESULT.exists():
        t = json.loads(TEST_RESULT.read_text(encoding="utf-8")).get("test")
        t = t if t and t.get("model") == MODEL else None
    return t["credits_per_char"] if t and t.get("credits_per_char") else 1.0


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Sound made here: silence and the chime, in the same MP3 format as ElevenLabs'


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def sound_file(seg):
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    enc = ["-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k"]
    if seg["type"] == "silence":
        path = SEGMENTS / f"silence-{seg['seconds']:.2f}.mp3"
        if not path.exists():
            ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{seg['seconds']:.2f}", *enc, str(path))
    else:  # two soft ascending notes, like a small bell (the Gooya edition's chime)
        path = SEGMENTS / "chime.mp3"
        if not path.exists():
            expr = ("0.075*exp(-t/0.35)*min(1,t/0.006)*(sin(2*PI*659.25*t)+0.35*sin(4*PI*659.25*t))"
                    "+gt(t,0.16)*0.06*exp(-(t-0.16)/0.40)*min(1,(t-0.16)/0.006)*(sin(2*PI*987.77*(t-0.16))+0.35*sin(4*PI*987.77*(t-0.16)))")
            ffmpeg("-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d=1.75", *enc, str(path))
    return path


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def line_times(seg, alignment, seconds):
    """Start and end of each line of a segment, in seconds from the segment's start, from the
    character timings (or, failing those, in proportion to the characters over the segment's length)."""
    text = seg_text(seg)
    spans, pos = [], 0
    for _, t in seg["lines"]:
        spans.append((pos, pos + len(t) - 1))
        pos += len(t) + 2
    chars = alignment.get("characters") if alignment else None
    starts = alignment.get("character_start_times_seconds") if alignment else None
    ends = alignment.get("character_end_times_seconds") if alignment else None
    if chars and len(chars) == len(text):
        return [(starts[a], ends[b]) for a, b in spans]
    return [(seconds * a / len(text), seconds * (b + 1) / len(text)) for a, b in spans]


# ---------------------------------------------------------------------------
# Modes


def chapters_to_do(args):
    return [args.chapter] if args.chapter else sorted(int(p.name[:2]) for p in SCRIPTS.glob("[01][0-9]-*.txt"))


def dry_run(m):
    r, total, requests_ = rate(m), 0, 0
    print(f"{'ch':>2}  {'requests':>8}  {'main':>7}  {'second':>7}  {'characters':>10}  {'credits':>8}")
    for n in chapters_to_do(argparse.Namespace(chapter=None)):
        _, segs, _ = plan_chapter(script(n))
        speech = [s for s in segs if s["type"] == "speech"]
        by = {role: sum(len(seg_text(s)) for s in speech if s["role"] == role) for role in ("main", "second")}
        chars = sum(by.values())
        total += chars
        requests_ += len(speech)
        print(f"{n:>2}  {len(speech):>8}  {by['main']:>7,}  {by['second']:>7,}  {chars:>10,}  {round(chars * r):>8,}")
    print(f"all: {requests_} requests, {total:,} characters, about {round(total * r):,} credits at "
          f"{r * 1000:g} credits per 1,000 characters" + (" (measured by --test)" if r != 1.0 else " (assumed; --test measures it)"))
    if os.environ.get("ELEVENLABS_API_KEY"):
        s = subscription()
        print(f"available now: {s['remaining']:,} of {s['limit']:,} credits ({s['tier']}); "
              f"enough for {s['remaining'] / max(1, total * r):.1f} times the whole book")


def test(m, args):
    vid = args.voice or VOICES["main"]
    text = test_text(paragraphs(script(1)))
    before = subscription()
    print(f"before: {before['used']:,} of {before['limit']:,} credits used, {before['remaining']:,} left "
          f"(tier {before['tier']}, overage possible: {before['can_extend']}, allowed: {before['allowed_to_extend']})")
    if before["remaining"] < TEST_CHARS * 2:
        raise SystemExit("not enough credits left for the test without risking overage; nothing generated")
    settings = voice_settings(vid)
    audio, request_id, cost, headers = speak(text, vid, settings, seed=1000)
    time.sleep(3)  # let the usage counter catch up
    after = subscription()
    charged = after["used"] - before["used"]
    STATE.mkdir(parents=True, exist_ok=True)
    out = STATE / "test-1000.mp3"
    out.write_bytes(audio)
    (STATE / "test-1000.txt").write_text(text, encoding="utf-8")
    per_char = (cost or charged) / len(text)
    try:
        seconds = duration(out)
    except (OSError, ValueError, subprocess.CalledProcessError):
        seconds = 0.0
    m["test"] = {"when": now(), "voice": vid, "model": MODEL, "output_format": OUTPUT, "voice_settings": settings,
                 "characters": len(text), "request_id": request_id, "character_cost_header": cost,
                 "used_before": before["used"], "used_after": after["used"], "charged": charged,
                 "credits_per_char": per_char, "file": str(out), "seconds": seconds, "headers_seen": sorted(headers)}
    save_manifest(m)
    print(f"submitted: {len(text):,} characters; request id {request_id}; character-cost header {cost}")
    print(f"charged (usage after minus before): {charged:,} credits; {per_char * 1000:g} credits per 1,000 characters")
    print(f"audio: {out} ({seconds:.1f} s, {len(audio):,} bytes)")
    print(f"after: {after['used']:,} of {after['limit']:,} used, {after['remaining']:,} left")
    dry_run(m)


def narrate_chapter(n, m, settings, sample=None):
    """Generate a chapter's missing segments (or, with sample, only its first ~sample characters), then join
    them into one MP3 with tags and section markers, and write its sync file."""
    path = script(n)
    title, segs, markers = plan_chapter(path)
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    entries = {c["key"]: c for c in m["chunks"] if "key" in c}
    speech = [s for s in segs if s["type"] == "speech"]
    if sample:
        chosen, count = [], 0
        for s in speech:
            if count >= sample:
                break
            chosen.append(s)
            count += len(seg_text(s))
        last = segs.index(chosen[-1])
        segs = segs[:last + 1] + [{"type": "silence", "seconds": 1.5}]
        markers = [(t, i) for t, i in markers if i <= last]
        speech = chosen

    def done(s):
        e = entries.get(seg_key(s))
        return e and e["status"] == "done" and (SEGMENTS / e["file"]).exists()
    todo = [s for s in speech if not done(s)]
    need = sum(len(seg_text(s)) for s in todo) * rate(m)
    sub = subscription()
    print(f"chapter {n}: {len(speech)} segments, {len(todo)} to generate, about {round(need):,} credits; {sub['remaining']:,} left")
    if need > sub["remaining"]:
        raise SystemExit(f"chapter {n} needs about {round(need):,} credits but only {sub['remaining']:,} are left; "
                         "stopping without generating (no overage)")
    history = {"main": [], "second": []}  # request ids of each voice's segments, for stitching
    for k, s in enumerate(speech, 1):
        key_ = seg_key(s)
        text = seg_text(s)
        if done(s):
            history[s["role"]].append(entries[key_].get("request_id"))
            continue
        if len(text) * rate(m) > subscription()["remaining"]:
            raise SystemExit(f"not enough credits left for segment {k}; stopping (no overage)")
        nxt = next((t for t in speech[k:] if t["role"] == s["role"]), None)
        name = f"{n:02d}-{key_[:12]}.mp3"
        entry = {"key": key_, "chapter": n, "chunk": k, "voice": VOICES[s["role"]], "role": s["role"], "characters": len(text),
                 "text_sha1": sha1(text), "file": name, "status": "generating", "request_id": None, "character_cost": None,
                 "when": now()}
        m["chunks"] = [c for c in m["chunks"] if c.get("key") != key_] + [entry]
        entries[key_] = entry
        save_manifest(m)
        stitch = m.get("stitching", True)
        previous = [r for r in history[s["role"]] if r][-3:] if stitch else []
        next_text = seg_text(nxt)[:500] if stitch and nxt else None
        try:
            try:
                audio, alignment, request_id, cost = speak_timed(text, VOICES[s["role"]], settings[s["role"]],
                                                                 seed=n * 1000 + k, previous=previous, next_text=next_text)
            except RuntimeError as err:
                if stitch and re.search(r"previous_request_ids|next_text|stitch", str(err), re.I):
                    m["stitching"] = False  # this model does not take request stitching; go on without it, and say so
                    save_manifest(m)
                    print(f"  the model does not accept request stitching ({err}); continuing without it", flush=True)
                    audio, alignment, request_id, cost = speak_timed(text, VOICES[s["role"]], settings[s["role"]], seed=n * 1000 + k)
                else:
                    raise
        except RuntimeError as err:
            entry["status"] = f"failed: {err}"
            save_manifest(m)
            raise SystemExit(f"chapter {n} segment {k}: {err}")
        (SEGMENTS / name).write_bytes(audio)
        (SEGMENTS / (name[:-4] + ".json")).write_text(json.dumps(alignment or {}), encoding="utf-8")
        entry.update(status="done", request_id=request_id, character_cost=cost, when=now())
        save_manifest(m)
        history[s["role"]].append(request_id)
        print(f"  segment {k}/{len(speech)} ({s['role']}): {len(text):,} characters, cost {cost}, request {request_id}", flush=True)

    # join: speech, silence and chimes, without re-encoding; sections become chapter markers
    files, lines, clock, starts = [], [], 0.0, {}
    for i, s in enumerate(segs):
        starts[i] = clock
        if s["type"] == "speech":
            f = SEGMENTS / entries[seg_key(s)]["file"]
            align_file = f.with_suffix(".json")
            alignment = json.loads(align_file.read_text(encoding="utf-8")) if align_file.exists() else {}
            for (kind, text), (b, e) in zip(s["lines"], line_times(s, alignment, duration(f))):
                lines.append({"kind": kind, "text": text, "begin": round(clock + b, 3), "end": round(clock + e, 3),
                              "voice": s["role"]})
        else:
            f = sound_file(s)
        files.append(f)
        clock += duration(f)
    CHAPTERS.mkdir(parents=True, exist_ok=True)
    stem = path.stem + ("-sample" if sample else "")
    listing = CHAPTERS / f"{stem}.txt"
    listing.write_text("".join(f"file '{f.resolve().as_posix()}'\n" for f in files), encoding="utf-8")
    meta = CHAPTERS / f"{stem}.meta"
    tags = [";FFMETADATA1", f"title={title}", f"album={ALBUM}", "artist=تسلط بر معرفت‌شناسی", f"track={n}/16",
            "genre=Audiobook", "language=fas",
            f"comment=Narrated with ElevenLabs ({MODEL}); voices {VOICES['main']} and {VOICES['second']}."]
    marks = [(t, starts[i]) for t, i in markers]
    for k, (name, start) in enumerate(marks):
        stop = marks[k + 1][1] if k + 1 < len(marks) else clock
        tags += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}", f"END={int(stop * 1000)}", f"title={name}"]
    meta.write_text("\n".join(tags) + "\n", encoding="utf-8")
    out = CHAPTERS / f"{stem}.mp3"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(meta), "-map", "0:a", "-map_metadata", "1",
           "-map_chapters", "1", "-c", "copy", "-id3v2_version", "3", str(out))
    (CHAPTERS / f"{stem}.json").write_text(json.dumps(
        {"file": f"{path.stem}.mp3", "title": title, "duration": round(clock, 3),
         "narration": {"engine": "ElevenLabs", "model": MODEL, "voices": VOICES}, "lines": lines},
        ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"chapter {n}: {out} ({clock / 60:.1f} min) and its sync file")


def import_segments(m, src):
    """Take over segments generated elsewhere: their files and manifest entries. Segments are keyed by
    voice, model, format and text, so only those identical to what a chapter needs are ever used."""
    other = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    have = {c.get("key") for c in m["chunks"]}
    taken = 0
    for c in other.get("chunks", []):
        f = src / "segments" / c.get("file", "")
        if c.get("status") == "done" and c.get("key") and c["key"] not in have and f.exists():
            for g in (f, f.with_suffix(".json")):
                if g.exists():
                    (SEGMENTS / g.name).write_bytes(g.read_bytes())
            m["chunks"].append(c)
            taken += 1
    if other.get("stitching") is False:
        m["stitching"] = False
    save_manifest(m)
    print(f"imported {taken} segments from {src}")


def main():
    global MODEL
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="count characters and predict credits; no generation")
    g.add_argument("--test", action="store_true", help=f"generate exactly {TEST_CHARS} characters from chapter 1 and report the cost")
    g.add_argument("--chapter", type=int, help="narrate one chapter")
    g.add_argument("--all", action="store_true", help="narrate every chapter")
    ap.add_argument("--resume", action="store_true", help="carry on from the manifest (segments already made are always kept)")
    ap.add_argument("--sample", type=int, help="with --chapter: only the first ~N characters, as a preview")
    ap.add_argument("--voice", help=f"main voice (default {VOICES['main']}); for --test, the voice to test")
    ap.add_argument("--voice2", help=f"second voice (default {VOICES['second']})")
    ap.add_argument("--model", help=f"model id (default: $ELEVENLABS_MODEL_ID or {MODEL})")
    ap.add_argument("--import-segments", metavar="DIR", help="reuse segments made elsewhere (DIR/manifest.json and DIR/segments/)")
    args = ap.parse_args()
    if args.model:
        MODEL = args.model
    if args.voice and not args.test:
        VOICES["main"] = args.voice
    if args.voice2:
        VOICES["second"] = args.voice2
    m = load_manifest()
    if args.import_segments:
        import_segments(m, Path(args.import_segments))
    if args.dry_run:
        dry_run(m)
    elif args.test:
        test(m, args)
    else:
        if not m.get("test"):
            raise SystemExit("run --test first, so the cost per character is measured")
        settings = lock_settings(m)
        for n in chapters_to_do(args):
            narrate_chapter(n, m, settings, sample=args.sample if args.chapter else None)


if __name__ == "__main__":
    main()
