#!/usr/bin/env python3
"""Animate an episode's painted frames with the Pruna API (a cheaper alternative to Veo; see tools/video/veo.py).

    python3 tools/video/pruna.py kids/episodes/big-feet.json --only c6 --model p-video-2 [--hold]

--hold also sends the first frame as the last frame, so the characters end where they started (the player freezes
on the last frame and the tap spots are placed on it). Raw clips go to tools/video/.cache/ like Veo's, named
<episode>-<clip>-<model>-<hash>.mp4. The key comes only from the PRUNA_API_KEY environment variable."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import veo as V  # noqa: E402  (frame_png, frame_bytes, prompt_of, CACHE, ROOT)

API = "https://api.pruna.ai/v1"
PRICE = {"p-video-2": 0.025, "p-video-2-pro": 0.035, "wan-i2v": 0.11 / 5}  # $ per second (list), as documented


def head():
    k = os.environ.get("PRUNA_API_KEY")
    if not k:
        raise SystemExit("PRUNA_API_KEY is not set")
    return {"apikey": k}


def upload(png_bytes):
    r = requests.post(f"{API}/files", headers=head(), files={"content": ("frame.png", png_bytes, "image/png")}, timeout=120)
    if r.status_code >= 300:
        raise SystemExit(f"upload refused ({r.status_code}): {r.text[:400]}")
    return r.json()["urls"]["get"]


def inputs(model, prompt, img, seconds, hold):
    if model == "p-video-2":
        d = {"prompt": prompt, "image": img, "duration": seconds, "resolution": "720p", "prompt_upsampling": False,
             "disable_safety_filter": False}
        if hold:
            d["last_frame_image"] = img
    elif model == "p-video-2-pro":
        d = {"prompt": prompt, "image": img, "duration": max(5, seconds), "resolution": "768p", "mode": "quality",
             "prompt_upsampler": "off"}
        if hold:
            d["last_frame_image"] = img
    elif model == "wan-i2v":
        d = {"prompt": prompt, "image": img, "num_frames": 121, "resolution": "720p", "frames_per_second": 16,
             "interpolate_output": True}
        if hold:
            d["last_image"] = img
    else:
        raise SystemExit(f"unknown model {model}")
    return d


def make(model, body):
    r = requests.post(f"{API}/predictions", headers={**head(), "Model": model, "Content-Type": "application/json"},
                      data=json.dumps({"input": body}), timeout=120)
    if r.status_code >= 300:
        raise SystemExit(f"{model} refused ({r.status_code}): {r.text[:600]}")
    j = r.json()
    pid, get = j.get("id"), j.get("get_url")
    print(f"  submitted: {json.dumps(j)[:300]}", flush=True)
    t0 = time.time()
    while j.get("status") not in ("succeeded", "failed", "canceled"):
        time.sleep(6)
        j = requests.get(get or f"{API}/predictions/status/{pid}", headers=head(), timeout=60).json()
        if time.time() - t0 > 1200:
            raise SystemExit(f"{model} took too long")
    if j["status"] != "succeeded":
        raise SystemExit(f"{model} failed: {json.dumps(j)[:600]}")
    url = j.get("generation_url") or (j.get("output") if isinstance(j.get("output"), str) else None)
    v = requests.get(url, headers=head(), timeout=300)
    v.raise_for_status()
    return v.content, round(time.time() - t0)


def cache_path(ep, c, model, hold):
    """Where the raw clip of this clip, model and hold setting is kept (and whether it exists)."""
    frame = V.frame_bytes(V.frame_png(ep, c), ep["veo"].get("aspect", "16:9"))
    h = hashlib.sha256(json.dumps([model, V.prompt_of(ep, c), c.get("seconds", 8), hold]).encode() + frame).hexdigest()[:16]
    return V.CACHE / f"{ep['id']}-{c['id']}-{model}-{h}.mp4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--model", default="p-video-2")
    ap.add_argument("--hold", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    ep = json.loads((V.ROOT / args.episode).read_text())
    V.CACHE.mkdir(parents=True, exist_ok=True)
    for c in ep["clips"]:
        if args.only and c["id"] not in args.only:
            continue
        if not V.frame_png(ep, c):
            print(f"{c['id']}: no painted first frame yet")
            continue
        frame = V.frame_bytes(V.frame_png(ep, c), ep["veo"].get("aspect", "16:9"))
        prompt = V.prompt_of(ep, c)
        secs = c.get("seconds", 8)
        out = cache_path(ep, c, args.model, args.hold)
        if out.exists() and not args.force:
            print(f"{c['id']} {args.model}: cached {out.name}")
            continue
        img = upload(frame)
        data, took = make(args.model, inputs(args.model, prompt, img, secs, args.hold))
        out.write_bytes(data)
        print(f"{c['id']} {args.model}{' hold' if args.hold else ''}: {took}s, {len(data) // 1024} KB -> {out.relative_to(V.ROOT)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
