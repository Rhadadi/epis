#!/usr/bin/env python3
"""Narrate the Persian chapters with ElevenLabs, carefully and resumably.

    python3 eleven_narrate.py --dry-run          # exact characters and predicted credits; no generation
    python3 eleven_narrate.py --test             # one request of exactly 1,000 characters from chapter 1
    python3 eleven_narrate.py --chapter 3        # narrate one chapter
    python3 eleven_narrate.py --all              # narrate every chapter
    python3 eleven_narrate.py --all --resume     # the same; chunks already made are never made again

The text is the one the Gooya narration speaks (scripts/NN-*.txt, as in
transcripts/): section titles, paragraphs, quotations and quiz lines, one
paragraph each. A chapter is cut into chunks of about 4,000 to 6,000
characters, only between paragraphs or sentences and preferably where a new
section starts, so that a bad take costs little to redo. Each chunk is sent
with the request IDs of the chunks before it (ElevenLabs request stitching),
so voice, pace and intonation run on across the joins. Chunks are saved
separately and joined without re-encoding into one MP3 per chapter.

Everything about the voice is fixed in the manifest at the first generation:
voice, model, voice settings, output format. Later runs refuse to go on with
anything different, so the whole book sounds the same.

Money: before every chapter (and every chunk) the subscription is read, and
nothing is generated unless the remaining credits cover it; usage beyond the
plan's credits (overage) is never used, even where the account allows it.

Needs: the requests package and ffmpeg; ELEVENLABS_API_KEY and
ELEVENLABS_VOICE_ID in the environment (the key is only read from there and
never written anywhere); optionally ELEVENLABS_MODEL_ID.
State lives in tools/.eleven/: manifest.json, chunks/ and chapters/.
"""

import argparse
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
API = "https://api.elevenlabs.io/v1"

MODEL = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_v4_turbo")
OUTPUT = "mp3_44100_128"
MIN_CHUNK, TARGET_CHUNK, MAX_CHUNK = 4000, 5000, 6000
TEST_CHARS = 1000

sys.path.insert(0, str(HERE))
from narrate import parse  # noqa: E402  (the script format)


# ---------------------------------------------------------------------------
# Text


def paragraphs(script_path):
    """The chapter as spoken paragraphs: [(kind, text)], in order."""
    out = []
    for kind, text in parse(script_path.read_text(encoding="utf-8")):
        if kind in ("title", "pause", "think", "chime") or not text:
            continue
        out.append((kind, text.strip()))
    return out


def sentences(text):
    parts, start = [], 0
    for m in re.finditer(r'[.!?؟]+[»"]?(?=\s|$)', text):
        parts.append(text[start:m.end()].strip())
        start = m.end()
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def chunks(paras):
    """Group paragraphs into chunks of about TARGET_CHUNK characters (never above MAX_CHUNK), cutting only
    between paragraphs, or between sentences inside a paragraph that is too long by itself. Once a chunk
    has MIN_CHUNK characters, a new section starts a new chunk."""
    units = []  # (text, starts_section)
    for kind, text in paras:
        if len(text) <= MAX_CHUNK:
            units.append((text, kind == "section"))
            continue
        cur = ""
        for s in sentences(text):
            if cur and len(cur) + 1 + len(s) > MAX_CHUNK:
                units.append((cur, False))
                cur = s
            else:
                cur = f"{cur} {s}".strip()
        units.append((cur, False))
    out, cur = [], []
    size = lambda parts: sum(len(p) for p in parts) + 2 * max(0, len(parts) - 1)
    for text, section in units:
        if cur and (size(cur + [text]) > MAX_CHUNK
                    or (size(cur) >= TARGET_CHUNK)
                    or (section and size(cur) >= MIN_CHUNK)):
            out.append("\n\n".join(cur))
            cur = []
        cur.append(text)
    if cur:
        out.append("\n\n".join(cur))
    if len(out) > 1 and len(out[-1]) < 1500 and len(out[-2]) + 2 + len(out[-1]) <= MAX_CHUNK:
        out[-2:] = [out[-2] + "\n\n" + out[-1]]  # no tiny last chunk
    return out


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


def voice_id(args):
    v = args.voice or os.environ.get("ELEVENLABS_VOICE_ID")
    if not v:
        raise SystemExit("set ELEVENLABS_VOICE_ID (or pass --voice)")
    return v


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
        raise SystemExit(f"could not read the voice's settings: {r.status_code} {r.text[:300]}")
    return r.json()


def speak(text, vid, settings, seed, previous=(), next_text=None):
    """One generation. Returns (mp3 bytes, request id, character cost, all response headers)."""
    body = {"text": text, "model_id": MODEL, "voice_settings": settings, "seed": seed}
    if previous:
        body["previous_request_ids"] = list(previous)[-3:]
    if next_text:
        body["next_text"] = next_text
    r = call("POST", f"/text-to-speech/{vid}", params={"output_format": OUTPUT}, json=body,
             headers={"Accept": "audio/mpeg"})
    if r.status_code != 200:
        raise RuntimeError(f"generation failed: {r.status_code} {r.text[:400]}")
    h = {k.lower(): v for k, v in r.headers.items()}
    cost = h.get("character-cost") or h.get("x-character-count")
    return r.content, h.get("request-id") or h.get("x-request-id"), int(cost) if cost and cost.isdigit() else None, h


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


def lock_settings(m, vid):
    """The first generation fixes voice, model, settings and format; later runs must match them."""
    if "voice" not in m:
        m.update({"voice": vid, "model": MODEL, "output_format": OUTPUT, "voice_settings": voice_settings(vid)})
        save_manifest(m)
    elif (m["voice"], m["model"], m["output_format"]) != (vid, MODEL, OUTPUT):
        raise SystemExit(f"the manifest was made with voice {m['voice']}, model {m['model']}, {m['output_format']}; "
                         f"refusing to mix in voice {vid}, model {MODEL}, {OUTPUT}")
    return m["voice_settings"]


def sha1(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def rate(m):
    """Credits per character: measured by --test, else assumed 1."""
    t = m.get("test")
    return t["credits_per_char"] if t and t.get("credits_per_char") else 1.0


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Modes


def plan():
    """Every chapter's chunks, exactly as they would be sent."""
    return {int(p.name[:2]): (p, chunks(paragraphs(p))) for p in sorted(SCRIPTS.glob("[01][0-9]-*.txt"))}


def dry_run(m):
    r = rate(m)
    total = 0
    print(f"{'ch':>2}  {'chunks':>6}  {'characters':>10}  {'credits':>9}  chunk sizes")
    for n, (p, cs) in plan().items():
        chars = sum(len(c) for c in cs)
        total += chars
        print(f"{n:>2}  {len(cs):>6}  {chars:>10,}  {round(chars * r):>9,}  {', '.join(str(len(c)) for c in cs)}")
    print(f"all {total:,} characters, about {round(total * r):,} credits at {r:g} credits per character"
          + ("" if m.get("test") else " (assumed; --test measures it)"))
    if os.environ.get("ELEVENLABS_API_KEY"):
        s = subscription()
        print(f"available now: {s['remaining']:,} of {s['limit']:,} credits ({s['tier']})")
    return total


def test(m, args):
    vid = voice_id(args)
    paras = paragraphs(script(1))
    text = test_text(paras)
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
    m["test"] = {"when": now(), "voice": vid, "model": MODEL, "output_format": OUTPUT, "voice_settings": settings,
                 "characters": len(text), "request_id": request_id, "character_cost_header": cost,
                 "used_before": before["used"], "used_after": after["used"], "charged": charged,
                 "credits_per_char": per_char, "file": str(out), "headers_seen": sorted(headers)}
    save_manifest(m)
    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                                    capture_output=True, text=True).stdout or 0)
    print(f"submitted: {len(text):,} characters; request id {request_id}; character-cost header {cost}")
    print(f"charged (usage after minus before): {charged:,} credits; {per_char * 1000:g} credits per 1,000 characters")
    print(f"audio: {out} ({duration:.1f} s, {len(audio):,} bytes)")
    print(f"after: {after['used']:,} of {after['limit']:,} used, {after['remaining']:,} left")
    total = 0
    for n, (p, cs) in plan().items():
        chars = sum(len(c) for c in cs)
        total += chars
        print(f"  chapter {n:>2}: {chars:>6,} characters, about {round(chars * per_char):>7,} credits")
    print(f"  all 16: {total:,} characters, about {round(total * per_char):,} credits")
    left, covered, upto = after["remaining"], 0, 0
    for n, (p, cs) in plan().items():
        need = sum(len(c) for c in cs) * per_char
        if covered + need > left:
            break
        covered += need
        upto = n
    print(f"the {after['remaining']:,} credits left cover {left / per_char:,.0f} characters: "
          f"{100 * min(1, left / per_char / total):.0f}% of the book, chapters 1 to {upto} in full" if upto else
          f"the {after['remaining']:,} credits left cover {left / per_char:,.0f} characters "
          f"({100 * min(1, left / per_char / total):.0f}% of the book), less than chapter 1")


def narrate_chapter(n, m, vid, settings):
    p, cs = plan()[n]
    CH = STATE / "chunks"
    CH.mkdir(parents=True, exist_ok=True)
    entries = {(c["chapter"], c["chunk"]): c for c in m["chunks"]}
    todo = []
    for k, text in enumerate(cs, 1):
        e = entries.get((n, k))
        done = e and e["status"] == "done" and e["text_sha1"] == sha1(text) and (CH / e["file"]).exists()
        if not done:
            todo.append(k)
    need = sum(len(cs[k - 1]) for k in todo) * rate(m)
    s = subscription()
    print(f"chapter {n}: {len(cs)} chunks, {len(todo)} to generate, about {round(need):,} credits; {s['remaining']:,} left")
    if need > s["remaining"]:
        raise SystemExit(f"chapter {n} needs about {round(need):,} credits but only {s['remaining']:,} are left; "
                         "stopping without generating (no overage)")
    for k, text in enumerate(cs, 1):
        e = entries.get((n, k))
        if k not in todo:
            continue
        s = subscription()
        if len(text) * rate(m) > s["remaining"]:
            raise SystemExit(f"only {s['remaining']:,} credits left, not enough for chunk {k}; stopping (no overage)")
        previous = [entries[(n, j)]["request_id"] for j in range(max(1, k - 3), k)
                    if (n, j) in entries and entries[(n, j)].get("request_id")]
        next_text = cs[k][:500] if k < len(cs) else None
        name = f"{n:02d}-c{k:02d}.mp3"
        entry = {"chapter": n, "chunk": k, "characters": len(text), "text_sha1": sha1(text), "file": name,
                 "status": "generating", "request_id": None, "character_cost": None, "when": now()}
        if e:
            m["chunks"].remove(e)
        m["chunks"].append(entry)
        entries[(n, k)] = entry
        save_manifest(m)
        stitch = m.get("stitching", True)
        try:
            try:
                audio, request_id, cost, _ = speak(text, vid, settings, seed=n * 100 + k,
                                                   previous=previous if stitch else (), next_text=next_text if stitch else None)
            except RuntimeError as err:
                if stitch and re.search(r"previous_request_ids|next_text|stitch", str(err), re.I):
                    m["stitching"] = False  # this model does not take request stitching; go on without it, and say so
                    save_manifest(m)
                    print(f"  the model does not accept request stitching ({err}); continuing without it", flush=True)
                    audio, request_id, cost, _ = speak(text, vid, settings, seed=n * 100 + k)
                else:
                    raise
        except RuntimeError as err:
            entry["status"] = f"failed: {err}"
            save_manifest(m)
            raise SystemExit(f"chapter {n} chunk {k}: {err}")
        (CH / name).write_bytes(audio)
        entry.update(status="done", request_id=request_id, character_cost=cost, when=now())
        save_manifest(m)
        print(f"  chunk {k}/{len(cs)}: {len(text):,} characters, cost {cost}, request {request_id}", flush=True)
    # one MP3 per chapter, joined without re-encoding
    out_dir = STATE / "chapters"
    out_dir.mkdir(parents=True, exist_ok=True)
    listing = STATE / f"{n:02d}-list.txt"
    listing.write_text("".join(f"file '{(CH / f'{n:02d}-c{k:02d}.mp3').as_posix()}'\n" for k in range(1, len(cs) + 1)), encoding="utf-8")
    out = out_dir / f"{p.stem}.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(out)], check=True)
    print(f"chapter {n}: {out}")


def main():
    global MODEL
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="count characters and predict credits; no generation")
    g.add_argument("--test", action="store_true", help=f"generate exactly {TEST_CHARS} characters from chapter 1 and report the cost")
    g.add_argument("--chapter", type=int, help="narrate one chapter")
    g.add_argument("--all", action="store_true", help="narrate every chapter")
    ap.add_argument("--resume", action="store_true", help="carry on from the manifest (chunks already made are always kept)")
    ap.add_argument("--voice", help="voice id (default: $ELEVENLABS_VOICE_ID)")
    ap.add_argument("--model", help=f"model id (default: $ELEVENLABS_MODEL_ID or {MODEL})")
    args = ap.parse_args()
    if args.model:
        MODEL = args.model
    m = load_manifest()
    if args.dry_run:
        dry_run(m)
    elif args.test:
        test(m, args)
    else:
        if not m.get("test"):
            raise SystemExit("run --test first, so the cost per character is measured")
        vid = voice_id(args)
        settings = lock_settings(m, vid)
        for n in ([args.chapter] if args.chapter else sorted(plan())):
            narrate_chapter(n, m, vid, settings)


if __name__ == "__main__":
    main()
