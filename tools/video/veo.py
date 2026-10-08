#!/usr/bin/env python3
"""Make the video clips of a kids' episode with Google Veo (Gemini API), one clip from each painted first frame.

    python3 tools/video/veo.py kids/episodes/big-feet.json --list        # what would be made, nothing sent
    python3 tools/video/veo.py kids/episodes/big-feet.json --only c1     # one clip (again, if --force)
    python3 tools/video/veo.py kids/episodes/big-feet.json               # every clip that is missing

Each clip of the episode has a painted first frame (made by tools/art/make_art.py from the episode's frames file)
and a "motion" prompt; the episode's "veo" block gives the model, the shared style and what to avoid. Raw clips are
kept in tools/video/.cache/ (not committed), named by a hash of model, prompt and frame, so running again costs
nothing unless a prompt or frame changed. tools/video/episode.py turns them into the published files.

The key comes only from the GEMINI_API_KEY environment variable and is never written anywhere."""
import argparse
import base64
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).resolve().parent / ".cache"
ART_CACHE = ROOT / "tools" / "art" / ".cache"
API = "https://generativelanguage.googleapis.com/v1beta"
PRICE = {"veo-3.1-generate-preview": 0.40, "veo-3.1-fast-generate-preview": 0.15, "veo-3.1-lite-generate-preview": 0.08}


def frame_png(ep, clip):
    """The cached PNG of the clip's painted first frame (newest, if a prompt changed)."""
    fid = clip.get("frame_id", f"{ep['id']}-{clip['id']}")
    found = sorted(ART_CACHE.glob(f"{fid}-*.png"), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def frame_bytes(png, aspect):
    """The frame cut to the clip's aspect ratio (centre crop), as PNG bytes; also what the player shows first."""
    im = Image.open(png).convert("RGB")
    aw, ah = (int(x) for x in aspect.split(":"))
    w, h = im.size
    if w * ah > h * aw:
        nw = h * aw // ah
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = w * ah // aw
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def prompt_of(ep, clip):
    v = ep["veo"]
    return f"{clip['motion']} {v['style']}"


def key_of(model, prompt, negative, seconds, frame):
    h = hashlib.sha256()
    h.update(json.dumps([model, prompt, negative, seconds], ensure_ascii=False).encode())
    h.update(frame)
    return h.hexdigest()[:16]


def headers():
    token = os.environ.get("GEMINI_API_KEY")
    if not token:
        raise SystemExit("GEMINI_API_KEY is not set")
    return {"x-goog-api-key": token}


def make(model, prompt, negative, frame, seconds, aspect, resolution):
    body = {"instances": [{"prompt": prompt,
                           "image": {"bytesBase64Encoded": base64.b64encode(frame).decode(),
                                     "mimeType": "image/png"}}],
            "parameters": {"aspectRatio": aspect, "durationSeconds": seconds, "resolution": resolution,
                           "negativePrompt": negative, "personGeneration": "allow_adult"}}
    r = requests.post(f"{API}/models/{model}:predictLongRunning", headers={**headers(), "Content-Type": "application/json"},
                      data=json.dumps(body), timeout=120)
    if r.status_code != 200:
        raise SystemExit(f"Veo refused ({r.status_code}): {r.text[:600]}")
    op = r.json()["name"]
    t0 = time.time()
    while True:
        time.sleep(10)
        s = requests.get(f"{API}/{op}", headers=headers(), timeout=60).json()
        if s.get("done"):
            break
        if time.time() - t0 > 900:
            raise SystemExit(f"Veo took too long ({op})")
    if "error" in s:
        raise SystemExit(f"Veo failed: {s['error']}")
    resp = s.get("response", {}).get("generateVideoResponse", {})
    samples = resp.get("generatedSamples") or []
    if not samples:
        raise SystemExit(f"Veo returned no video (filtered?): {json.dumps(resp)[:600]}")
    uri = samples[0]["video"]["uri"]
    v = requests.get(uri, headers=headers(), timeout=300, allow_redirects=True)
    v.raise_for_status()
    return v.content, round(time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--model", help="override the episode's model for this run")
    args = ap.parse_args()
    ep = json.loads((ROOT / args.episode).read_text())
    v = ep["veo"]
    model = args.model or v["model"]
    CACHE.mkdir(parents=True, exist_ok=True)
    cost = 0.0
    for clip in ep["clips"]:
        if args.only and clip["id"] not in args.only:
            continue
        png = frame_png(ep, clip)
        if not png:
            print(f"{clip['id']:6} no painted first frame yet (run tools/art/make_art.py on {ep['frames']})")
            continue
        prompt = prompt_of(ep, clip)
        frame = frame_bytes(png, v.get("aspect", "16:9"))
        secs = clip.get("seconds", 8)
        out = CACHE / f"{ep['id']}-{clip['id']}-{key_of(model, prompt, v.get('negative', ''), secs, frame)}.mp4"
        if args.list:
            print(f"{clip['id']:6} {'cached' if out.exists() else 'to make'}  {secs}s  ~${PRICE.get(model, 0.4) * secs:.2f}")
            continue
        if out.exists() and not args.force:
            print(f"{clip['id']:6} cached")
            continue
        print(f"{clip['id']:6} making with {model} ({secs}s)", flush=True)
        data, took = make(model, prompt, v.get("negative", ""), frame, secs, v.get("aspect", "16:9"), v.get("resolution", "720p"))
        out.write_bytes(data)
        cost += PRICE.get(model, 0.4) * secs
        print(f"{clip['id']:6} done in {took}s, {len(data) // 1024} KB -> {out.relative_to(ROOT)}", flush=True)
    if cost:
        print(f"estimated cost of this run: ${cost:.2f}")


if __name__ == "__main__":
    sys.exit(main())
