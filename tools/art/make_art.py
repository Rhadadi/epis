#!/usr/bin/env python3
"""Make the illustrations of the kids' site and Baloney Detector with an OpenAI image model.

    python3 tools/art/make_art.py kids/art/prompts.json --list            # what would be made, nothing sent
    python3 tools/art/make_art.py kids/art/prompts.json                   # make everything missing
    python3 tools/art/make_art.py kids/art/prompts.json --only u01-s03    # one picture (again, if --force)
    python3 tools/art/make_art.py kids/art/prompts.json --cached-only     # publish what exists, make nothing

A prompts file: {"model", "style", "out", "images": [{"id", "size", "quality", "prompt", "refs": [ids],
"publish": true|false, "widths": [800, 1440]}]}. Every prompt gets the file's style block in front; "refs" are
earlier pictures (such as the character sheet) sent along as references so the cast looks the same in every
scene. The original PNGs are kept in tools/art/.cache/ (not committed), named by a hash of model, style, prompt
and references, so running again costs nothing unless a prompt changed. Published pictures are written as WebP
(<out>/<id>-<width>.webp) and recorded in <prompts dir>/manifest.json with the model, date and prompt hash;
"reviewed" stays "pending" until a person has looked at the picture.

The key comes only from the OPENAI_API_KEY environment variable and is never written anywhere."""
import argparse
import base64
import datetime
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).resolve().parent / ".cache"
API = "https://api.openai.com/v1/images"


def key_of(spec, model, style, ref_keys):
    blob = json.dumps([model, style, spec["prompt"], spec.get("size"), spec.get("quality"), ref_keys], ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def call(model, prompt, spec, refs):
    token = os.environ.get("OPENAI_API_KEY")
    if not token:
        raise SystemExit("OPENAI_API_KEY is not set")
    head = {"Authorization": f"Bearer {token}"}
    params = {"model": model, "prompt": prompt, "size": spec.get("size", "1536x1024"),
              "quality": spec.get("quality", "medium"), "n": 1}
    for attempt in range(4):
        try:
            if refs:
                files = [("image[]", (p.name, p.read_bytes(), "image/png")) for p in refs]
                r = requests.post(f"{API}/edits", headers=head, data=params, files=files, timeout=600)
            else:
                r = requests.post(f"{API}/generations", headers={**head, "Content-Type": "application/json"},
                                  data=json.dumps(params), timeout=600)
        except requests.RequestException as e:
            print(f"    network: {e}; retrying")
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 200:
            d = r.json()
            return base64.b64decode(d["data"][0]["b64_json"]), d.get("usage", {})
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            print(f"    {r.status_code}; retrying")
            time.sleep(10 * (attempt + 1))
            continue
        raise SystemExit(f"image API {r.status_code}: {r.text[:400]}")
    raise SystemExit("image API: gave up after retries")


def publish(png, out_dir, iid, widths):
    out_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(png).convert("RGB")
    for w in widths:
        h = round(im.height * w / im.width)
        im.resize((w, h), Image.LANCZOS).save(out_dir / f"{iid}-{w}.webp", "WEBP", quality=82, method=6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompts")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cached-only", action="store_true", help="make nothing new; publish what is made, withdraw the rest")
    args = ap.parse_args()
    pfile = (ROOT / args.prompts).resolve()
    cfg = json.loads(pfile.read_text(encoding="utf-8"))
    model, style, out_dir = cfg["model"], cfg["style"], ROOT / cfg["out"]
    man_path = pfile.parent / "manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    CACHE.mkdir(exist_ok=True)
    keys = {}
    for spec in cfg["images"]:
        iid = spec["id"]
        refs = [CACHE / f"{r}-{keys[r]}.png" for r in spec.get("refs", [])]
        k = key_of(spec, model, style, [keys[r] for r in spec.get("refs", [])])
        keys[iid] = k
        png = CACHE / f"{iid}-{k}.png"
        wanted = not args.only or iid in args.only
        if not wanted:
            continue
        if args.list:
            print(f"{iid:28} {'cached' if png.exists() else 'to make'}  {spec.get('size', '1536x1024')} {spec.get('quality', 'medium')}"
                  f"{'  refs ' + ','.join(spec['refs']) if spec.get('refs') else ''}")
            continue
        if args.cached_only and not png.exists():
            # not made for the current prompt: take any older version off the site (the page shows a placeholder)
            for old in out_dir.glob(f"{iid}-*.webp"):
                old.unlink()
            manifest.pop(iid, None)
            print(f"  {iid}: not made yet for this prompt; withdrawn")
            continue
        if not png.exists() or args.force:
            prompt = f"{style}\n\n{spec['prompt']}"
            print(f"  {iid}: making ({spec.get('quality', 'medium')}, {len(refs)} reference(s))", flush=True)
            t = time.time()
            data, usage = call(model, prompt, spec, refs)
            png.write_bytes(data)
            print(f"    {time.time() - t:.0f} s, {usage.get('output_tokens', '?')} output tokens", flush=True)
        if spec.get("publish", True):
            widths = spec.get("widths", [800, 1440])
            publish(png, out_dir, iid, widths)
            old = manifest.get(iid, {})
            manifest[iid] = {"model": model, "prompt_sha": k, "size": spec.get("size", "1536x1024"),
                             "made": old.get("made") if old.get("prompt_sha") == k else datetime.date.today().isoformat(),
                             "reviewed": old.get("reviewed", "pending") if old.get("prompt_sha") == k else "pending",
                             "widths": widths}
    if not args.list:
        man_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
