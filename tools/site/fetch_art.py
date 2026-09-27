#!/usr/bin/env python3
"""Download the site's header artwork from Wikimedia Commons.

Reads tools/site/art.json. For each image it takes the lead image of the first
Wikipedia article that has one (or a named Commons file), downloads a large
rendition, and writes

    assets/art/<key>.jpg        up to 2400 px wide, for page headers
    assets/art/<key>-thumb.jpg  720 px wide, for cards
    assets/art/credits.json     title, artist, date, licence and source page

Only files hosted on Wikimedia Commons are used, so every image is freely
licensed (the chosen works are public domain). Images already downloaded are
skipped unless their source changes. Needs Pillow.

    python3 tools/site/fetch_art.py
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tools" / "site" / "art.json"
OUT = ROOT / "assets" / "art"
UA = "EpistemologyGuideSite/1.0 (https://github.com/Rhadadi/epis) python-urllib"


def get(url, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception as e:  # network hiccups and rate limits
            if attempt == tries - 1:
                raise
            print(f"  retry after {e}", flush=True)
            time.sleep(3 * (attempt + 1))


def lead_image(title):
    """File name of a Wikipedia article's lead image, if it is on Commons."""
    api = ("https://en.wikipedia.org/w/api.php?action=query&format=json&redirects=1"
           "&prop=pageimages|info&inprop=url&piprop=name&titles=" + urllib.parse.quote(title))
    try:
        pages = json.loads(get(api))["query"]["pages"]
    except Exception as e:
        print(f"  lookup failed for {title!r}: {e}")
        return None
    page = next(iter(pages.values()))
    name = page.get("pageimage")
    if not name:
        print(f"  {title!r}: no article or no lead image")
        return None
    return name, page.get("fullurl")


def commons_info(filename, width):
    """Commons file details, or None if the file is not on Commons (e.g. non-free)."""
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo"
           f"&iiprop=url|size|extmetadata&iiurlwidth={width}&titles=" + urllib.parse.quote("File:" + filename))
    pages = json.loads(get(api))["query"]["pages"]
    page = next(iter(pages.values()))
    return page["imageinfo"][0] if "imageinfo" in page else None


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["images"]
    OUT.mkdir(parents=True, exist_ok=True)
    credits_path = OUT / "credits.json"
    credits = json.loads(credits_path.read_text(encoding="utf-8")) if credits_path.exists() else {}
    failed = []
    for key, spec in manifest.items():
        try:
            fetch_one(key, spec, credits)
        except Exception as e:
            print(f"{key}: FAILED: {e!r}", flush=True)
            failed.append(key)
    credits_path.write_text(json.dumps(credits, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1 if len(failed) == len(manifest) else 0)


def fetch_one(key, spec, credits):
    files = spec.get("file") or []
    candidates = [(f, None) for f in ([files] if isinstance(files, str) else files)]
    for title in spec.get("wiki", []):
        found = lead_image(title)
        if found:
            candidates.append(found)
    info = filename = article = None
    for filename, article in candidates:
        info = commons_info(filename, 2400)
        if info:
            break
        print(f"  {key}: {filename!r} is not on Commons")
    if not info:
        raise RuntimeError("no usable Commons image")
    hero, thumb = OUT / f"{key}.jpg", OUT / f"{key}-thumb.jpg"
    if credits.get(key, {}).get("file") == filename and hero.exists() and thumb.exists():
        print(f"{key}: up to date ({filename})")
        return
    meta = info.get("extmetadata", {})
    img = Image.open(BytesIO(get(info.get("thumburl") or info["url"])))
    img = img.convert("RGB")
    if img.width > 2400:
        img = img.resize((2400, round(img.height * 2400 / img.width)), Image.LANCZOS)
    img.save(hero, "JPEG", quality=80, optimize=True, progressive=True)
    small = img.resize((720, round(img.height * 720 / img.width)), Image.LANCZOS)
    small.save(thumb, "JPEG", quality=78, optimize=True, progressive=True)
    avg = small.resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    credits[key] = {
        "file": filename,
        "article": article,
        "source": info.get("descriptionurl"),
        "width": img.width,
        "height": img.height,
        "color": "#%02x%02x%02x" % avg,
        "artist": plain(meta.get("Artist", {}).get("value")),
        "object": plain(meta.get("ObjectName", {}).get("value")),
        "date": plain(meta.get("DateTimeOriginal", {}).get("value")),
        "license": plain(meta.get("LicenseShortName", {}).get("value")),
        "credit": plain(meta.get("Credit", {}).get("value")),
    }
    print(f"{key}: {filename} -> {img.width}x{img.height}, {credits[key]['license']}", flush=True)
    time.sleep(1)


if __name__ == "__main__":
    main()
