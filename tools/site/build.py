#!/usr/bin/env python3
"""Build the Mastering Epistemology website from the guide and the concept map.

    python3 tools/site/build.py

Reads
    guide/NN-*.md, guide/README.md      the guide (the markdown stays the source of truth)
    guide/audio/tracks.js               audio tracks and their section times
    assets/data/concepts.js             the concept map's data (also used by map/index.html)
    tools/site/art.json                 artwork captions; images in assets/art/ (see fetch_art.py)

Writes
    index.html                          the starting page
    guide/index.html, guide/NN-*.html   the guide as web pages
    guide/audio/index.html, about.html  the audio player and how the audio was made
    concepts/index.html, concepts/*.html one readable page per concept, English and Persian
    credits.html, 404.html
    assets/art/*-{640,1200,2000}.jpg    cropped, resized artwork
    assets/diagrams/*.svg               Mermaid diagrams rendered to SVG (cached)

Needs Python 3.9+, markdown-it-py and Pillow. Rendering new or changed Mermaid
diagrams also needs Node with the playwright-core and mermaid packages and a
Chromium (see render_mermaid.cjs); diagrams already in assets/diagrams/ are reused.
"""

import hashlib
import html
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from markdown_it import MarkdownIt
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "guide"
ASSETS = ROOT / "assets"
ART_DIR = ASSETS / "art"
DIAGRAMS = ASSETS / "diagrams"
TOOLS = Path(__file__).resolve().parent
SITE = "Mastering Epistemology"
EPUB_NAME = "mastering-epistemology.epub"
LIVE = "https://rhadadi.github.io/epis/"
REPO = "https://github.com/Rhadadi/epis"

PARTS = [
    ("I", "Foundations", [1, 2, 3, 4]),
    ("II", "The Core of Epistemology", [5, 6, 7, 8]),
    ("III", "Evidence, Science, and Truth", [9, 10, 11]),
    ("IV", "Knowledge in Society and in the Mind", [12, 13, 14]),
    ("V", "Practice", [15, 16]),
    ("", "Appendices", [17, 18]),
]
PART_OF = {n: (roman, name) for roman, name, nums in PARTS for n in nums}

# Concept-map branches: the guide chapter that covers each one, and its artwork.
BRANCH_CHAPTER = {"root": 1, "trilemma": 6, "know": 5, "truth": 11, "sources": 7, "skep": 8, "formal": 9,
                  "phsci": 10, "social": 12, "natur": 14, "virtue": 13, "logic": 3, "relig": 13}
BRANCH_ART = {"root": "home", "trilemma": "ch06", "know": "ch05", "truth": "ch11", "sources": "ch07", "skep": "ch08",
              "formal": "ch09", "phsci": "ch10", "social": "ch12", "natur": "ch14", "virtue": "ch13", "logic": "ch03",
              "relig": "elephant"}

esc = html.escape


def attr(value):
    return html.escape(str(value), quote=True)


# ----------------------------------------------------------------------------- icons

def icon(name, cls="icon"):
    paths = {
        "book": '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/>',
        "map": '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><circle cx="12" cy="9" r="2"/><path d="M6.7 7 10.4 8.4M17.3 7l-3.7 1.4M12 11v5"/>',
        "grid": '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
        "phones": '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4" height="7" rx="1.5"/><rect x="17" y="14" width="4" height="7" rx="1.5"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "back": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
        "play": '<path d="M8 5v14l11-7z" fill="currentColor" stroke="none"/>',
        "pin": '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
        "ext": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
        "focus": '<path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4"/><path d="M9 9h6M9 12h6M9 15h4"/>',
        "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
        "pen": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    }
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>'


LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="14.6" fill="none" stroke="currentColor" stroke-width="1.3"/>'
        '<path d="M5.2 16c3-4.8 6.7-7.2 10.8-7.2S23.8 11.2 26.8 16c-3 4.8-6.7 7.2-10.8 7.2S8.2 20.8 5.2 16z" fill="none" stroke="currentColor" stroke-width="1.3"/>'
        '<circle cx="16" cy="16" r="3.6" fill="#D39A3A"/></svg>')

FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0A1620"/>'
           '<path d="M4.8 16c3.1-5 6.9-7.5 11.2-7.5S24.1 11 27.2 16c-3.1 5-6.9 7.5-11.2 7.5S7.9 21 4.8 16z" fill="none" stroke="#E8EEF1" stroke-width="1.6"/>'
           '<circle cx="16" cy="16" r="4" fill="#F2B84B"/></svg>\n')

BOOT = ('(function(){var d=document.documentElement,g=function(k){try{return localStorage.getItem(k)}catch(e){return null}};'
        'var p=g("epistemology-theme")||"system",sh=g("epis-shade")||"";'
        'var k=p==="dark"||(p==="system"&&window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches);'
        'if(sh==="sepia")k=false;if(sh==="black")k=true;'
        'd.setAttribute("data-theme",k?"dark":"light");d.setAttribute("data-theme-preference",p);if(sh)d.setAttribute("data-shade",sh);'
        'if(g("epistemology-lang")==="fa")d.setAttribute("data-lang","fa");'
        'try{var r=JSON.parse(g("epis-reader")||"{}");if(r.scale)d.style.setProperty("--read-scale",r.scale);'
        'if(r.lead)d.style.setProperty("--read-lead",r.lead);if(r.width)d.setAttribute("data-width",r.width);'
        'if(r.font)d.setAttribute("data-font",r.font)}catch(e){}'
        'if(g("epis-focus")==="1"&&/\\/guide\\/\\d\\d-[^\\/.]+(\\.html)?$/.test(location.pathname))d.setAttribute("data-focus","")})();')


# ----------------------------------------------------------------------------- data

def load_js_json(path, prefix):
    text = path.read_text(encoding="utf-8")
    start = text.index(prefix) + len(prefix)
    end = text.rindex(";")
    return json.loads(text[start:end])


def github_slug(text, seen):
    slug = re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")
    n = seen.get(slug, 0)
    seen[slug] = n + 1
    return slug if n == 0 else f"{slug}-{n}"


def words(text):
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", text))


def minutes_label(sec):
    m = round(sec / 60)
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


class Art:
    """Artwork captions plus the image derivatives used on the site."""

    SIZES = (640, 1200, 2000)

    def __init__(self):
        self.info = json.loads((TOOLS / "art.json").read_text(encoding="utf-8"))["images"]
        credits = ART_DIR / "credits.json"
        self.credits = json.loads(credits.read_text(encoding="utf-8")) if credits.exists() else {}

    def has(self, key):
        return (ART_DIR / f"{key}.jpg").exists()

    def derive(self):
        for key, spec in self.info.items():
            src = ART_DIR / f"{key}.jpg"
            if not src.exists():
                continue
            outs = [ART_DIR / f"{key}-{w}.jpg" for w in self.SIZES]
            stamp = max(src.stat().st_mtime, (TOOLS / "art.json").stat().st_mtime)
            if all(o.exists() and o.stat().st_mtime >= stamp for o in outs):
                continue
            img = Image.open(src).convert("RGB")
            if spec.get("crop"):
                l, t, r, b = spec["crop"]
                img = img.crop((round(l * img.width), round(t * img.height), round(r * img.width), round(b * img.height)))
            for w, out in zip(self.SIZES, outs):
                im = img if img.width <= w else img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
                im.save(out, "JPEG", quality=78 if w > 700 else 76, optimize=True, progressive=True)
            print(f"  art {key}: {img.width}x{img.height}")

    def color(self, key):
        return self.credits.get(key, {}).get("color", "#2a2f33")

    def focus(self, key):
        return self.info.get(key, {}).get("focus", "50% 50%")

    def src(self, key, root, w=1200):
        return f"{root}assets/art/{key}-{w}.jpg"

    def srcset(self, key, root):
        return ", ".join(f"{root}assets/art/{key}-{w}.jpg {w}w" for w in self.SIZES)

    def caption(self, key, italic=True):
        i = self.info.get(key, {})
        title = f"<i>{esc(i.get('title', ''))}</i>" if italic else esc(i.get("title", ""))
        bits = [esc(i.get("artist", "")), title, esc(i.get("date", ""))]
        return ", ".join(b for b in bits if b)

    def alt(self, key):
        i = self.info.get(key, {})
        return f"{i.get('title', '')} by {i.get('artist', '')} ({i.get('date', '')})"

    def img(self, key, root, sizes="100vw", cls="art", eager=False):
        return (f'<img class="{cls}" src="{self.src(key, root)}" srcset="{self.srcset(key, root)}" sizes="{sizes}" '
                f'alt="{attr(self.alt(key))}"' + (' fetchpriority="high"' if eager else ' loading="lazy"') +
                ' decoding="async">')


# ----------------------------------------------------------------------------- markdown

class Markdown:
    def __init__(self):
        # typographer for curly quotes only: "replacements" would turn "(c)" into a copyright sign
        self.md = MarkdownIt("commonmark", {"html": True, "typographer": True}).enable(["table", "smartquotes"])
        self.md.disable("replacements", ignoreInvalid=True)
        self.mermaid = {}  # hash -> source
        fence = self.md.renderer.rules.get("fence")

        def render_fence(renderer, tokens, idx, options, env):
            tok = tokens[idx]
            if tok.info.strip() == "mermaid":
                h = hashlib.sha1(tok.content.encode()).hexdigest()[:12]
                self.mermaid[h] = tok.content
                return f"<!--MERMAID:{h}-->\n"
            return fence(tokens, idx, options, env)
        self.md.add_render_rule("fence", render_fence)

    def inline(self, text):
        return self.md.renderInline(text)

    def render(self, text, link_map):
        """Markdown to HTML with GitHub-style heading ids; returns (html, headings)."""
        tokens = self.md.parse(text)
        seen, heads, depth = {}, [], 0
        for i, tok in enumerate(tokens):
            if tok.type == "blockquote_open":
                depth += 1
            elif tok.type == "blockquote_close":
                depth -= 1
            elif tok.type == "heading_open":
                inline = tokens[i + 1]
                plain = "".join(c.content for c in inline.children if c.type in ("text", "code_inline"))
                slug = github_slug(plain, seen)
                tok.attrSet("id", slug)
                heads.append((int(tok.tag[1]), slug, plain, self.md.renderer.renderInline(inline.children, self.md.options, {})))
            elif tok.type == "inline" and tok.children:
                for c in tok.children:
                    if depth and c.type == "softbreak":
                        c.type = "hardbreak"
                    if c.type == "link_open":
                        c.attrSet("href", link_map(c.attrGet("href") or ""))
        return self.md.renderer.render(tokens, self.md.options, {}), heads


def guide_links(prefix=""):
    """Rewrite links between markdown files to the generated pages."""
    def rewrite(href):
        if re.match(r"^[a-z]+:", href) or href.startswith("#"):
            return href
        path, _, frag = href.partition("#")
        frag = "#" + frag if frag else ""
        if path == "README.md":
            return prefix + "./" + frag if prefix == "" else prefix + frag
        if path == "audio/README.md":
            return "audio/about.html" + frag
        if path == "../index.html":
            return "../map/" + frag
        if path == "../README.md":
            return REPO + "#readme"
        m = re.match(r"^(\d\d-[\w-]+)\.md$", path)
        if m:
            return m.group(1) + ".html" + frag
        return href
    return rewrite


def render_mermaid(md):
    """Render diagrams missing from the cache; returns hash -> (light svg, dark svg) or None."""
    DIAGRAMS.mkdir(parents=True, exist_ok=True)
    todo = {h: src for h, src in md.mermaid.items()
            if not ((DIAGRAMS / f"{h}-light.svg").exists() and (DIAGRAMS / f"{h}-dark.svg").exists())}
    if todo:
        job = DIAGRAMS / ".jobs.json"
        job.write_text(json.dumps(todo), encoding="utf-8")
        try:
            subprocess.run(["node", str(TOOLS / "render_mermaid.cjs"), str(job), str(DIAGRAMS)], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"  warning: could not render {len(todo)} diagram(s) ({e}); they will be shown as text")
        finally:
            job.unlink(missing_ok=True)
    for old in DIAGRAMS.glob("*.svg"):
        if old.stem.rsplit("-", 1)[0] not in md.mermaid:
            old.unlink()
    out = {}
    for h in md.mermaid:
        light, dark = DIAGRAMS / f"{h}-light.svg", DIAGRAMS / f"{h}-dark.svg"
        if light.exists() and dark.exists():
            strip = lambda s: re.sub(r"^<\?xml[^>]*>\s*", "", s)
            out[h] = (strip(light.read_text(encoding="utf-8")), strip(dark.read_text(encoding="utf-8")))
    return out


def size_diagram(svg):
    """Keep diagram text legible: never scale below 62% (the figure scrolls sideways instead)."""
    width = float(re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ', svg).group(1))
    style = f'style="max-width:{width:.0f}px;min-width:{min(width, 320) if width < 520 else width * .62:.0f}px"'
    return re.sub(r'style="max-width: [\d.]+px;"', style, svg, count=1), width


def place_diagrams(page_html, md, svgs):
    def sub(m):
        h = m.group(1)
        if h in svgs:
            (light, width), (dark, _) = (size_diagram(svg) for svg in svgs[h])
            cls = "diagram wide" if width > 640 else "diagram"
            return (f'<figure class="{cls}"><div class="dg-light">{light}</div><div class="dg-dark">{dark}</div></figure>')
        return f'<figure class="diagram"><pre>{esc(md.mermaid[h])}</pre></figure>'
    return re.sub(r"<!--MERMAID:(\w+)-->", sub, page_html)


def polish(body):
    """Web-only touches to rendered chapter HTML: callouts, dialogues, quotes, tables, questions."""
    def blockquote(m):
        inner = m.group(1)
        plain = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        lines = re.split(r"<br\s*/?>\n?", re.sub(r"^\s*<p>|</p>\s*$", "", inner.strip()))
        speaker = re.compile(r"^\s*(?:<strong>)?(A|B|Speaker A|Speaker B):?(?:</strong>)?:?\s+(.*)$", re.S)
        said = [speaker.match(l) for l in lines]
        if len(lines) >= 2 and "</p>" not in inner.strip()[:-4] and sum(1 for s in said if s) >= 2 and all(said):
            rows = []
            for s in said:
                who = s.group(1)[-1]
                rows.append(f'<div class="line {who.lower()}"><span class="who">{who}</span><div class="said">{s.group(2)}</div></div>')
            return '<div class="dialogue">' + "".join(rows) + "</div>"
        lab = re.match(r"^\s*<p><strong>([^<]{2,80}?)</strong>(:?)\s*(.*)$", inner, re.S)
        if (lab and len(plain) > 60 and not lab.group(1).startswith(("“", "&quot;"))
                and (lab.group(1).endswith(".") or lab.group(2) == ":")):
            tag = lab.group(1).rstrip(".").strip()
            if tag not in ("A", "B"):
                return f'<aside class="callout"><span class="tag">{tag}</span><p>{lab.group(3)}</aside>'
        by = re.search(r"<br\s*/?>\n?\s*—\s*(.+?)</p>\s*$", inner, re.S)
        if plain.startswith(("“", '"')) and by and len(plain) < 500:
            quote = inner[:by.start()] + "</p>"
            return f'<blockquote class="quote">{quote}<span class="by">— {by.group(1)}</span></blockquote>'
        return m.group(0)
    body = re.sub(r"<blockquote>\n?(.*?)</blockquote>", blockquote, body, flags=re.S)
    body = re.sub(r"<table>", '<div class="table"><table>', body)
    body = re.sub(r"</table>", "</table></div>", body)
    body = re.sub(r"<p><strong>(\d+)\.</strong>\s*", r'<p class="q"><span class="n">\1</span>', body)
    return body


# ----------------------------------------------------------------------------- page shell

def shell(*, root, title, desc, body, current="", hero_img=None, extra_head="", bar="solid", reader=False, focus=False):
    nav = [("guide", f"{root}guide/", "book", "Guide"), ("concepts", f"{root}concepts/", "grid", "Concepts"),
           ("map", f"{root}map/", "map", "Map"), ("audio", f"{root}guide/audio/", "phones", "Listen"),
           ("notes", f"{root}notes/", "pen", "Notes")]
    here = ' aria-current="page"'
    links = "".join(f'<a href="{href}"{here if key == current else ""}>{icon(ic)}<span>{label}</span></a>'
                    for key, href, ic, label in nav)
    preload = (f'<link rel="preload" as="image" href="{hero_img[0]}" imagesrcset="{hero_img[1]}" imagesizes="100vw">'
               if hero_img else "")
    full_title = title if title == SITE else f"{title} · {SITE}"
    reader_btn = ('<button class="tbtn rbtn" id="reader" type="button" aria-label="Reading settings" title="Reading settings (A)" '
                  'aria-expanded="false" aria-controls="rpanel">Aa</button>') if reader else ""
    focus_btn = (f'<button class="tbtn" id="focus" type="button" aria-pressed="false" aria-label="Focus mode" title="Focus mode (F)">'
                 f'{icon("focus")}</button>') if focus else ""
    return f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{attr(desc)}">
<meta name="theme-color" content="#F6F3EC">
<meta property="og:title" content="{attr(full_title)}">
<meta property="og:description" content="{attr(desc)}">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{root}assets/icon-192.png">
<link rel="manifest" href="{root}manifest.webmanifest">
<link rel="stylesheet" href="{root}assets/fonts/fonts.css">
<link rel="stylesheet" href="{root}assets/site.css">
{preload}{extra_head}
<script>{BOOT}</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="bar {bar}">
  <a class="brand" href="{root}" aria-label="{SITE}, home">{LOGO}<span><b>{SITE}</b><small>Guide · Map · Audio</small></span></a>
  <nav aria-label="Site">{links}</nav>
  {focus_btn}{reader_btn}<button class="tbtn" id="theme" type="button" aria-label="Theme"></button>
</header>
{body}
{footer(root)}
<script src="{root}assets/site.js" defer></script>
<script src="{root}assets/notes.js" defer></script>
</body>
</html>
"""


def footer(root):
    return f"""<footer class="foot">
  <div class="wrap">
    <div>
      <a class="brand" href="{root}">{LOGO}<span><b>{SITE}</b></span></a>
      <p>A complete guide to knowledge, evidence, and critical thinking, with a bilingual concept map and a narrated audio edition.</p>
      <p>Artwork: public domain, via Wikimedia Commons (<a href="{root}credits.html">credits</a>). The narration uses a synthetic voice.</p>
    </div>
    <div><h3>Read</h3><ul>
      <li><a href="{root}guide/">Contents</a></li>
      <li><a href="{root}guide/01-what-is-epistemology.html">Start with chapter 1</a></li>
      <li><a href="{root}guide/17-glossary.html">Glossary</a></li>
      <li><a href="{root}guide/18-reading-list.html">Reading list and study plan</a></li>
      <li><a href="{root}guide/{EPUB_NAME}" download>EPUB for e-readers</a></li></ul></div>
    <div><h3>Explore</h3><ul>
      <li><a href="{root}map/">Concept map</a></li>
      <li><a href="{root}concepts/">All 135 concepts</a></li>
      <li><a href="{root}guide/audio/">Audio edition</a></li>
      <li><a href="{REPO}">Source on GitHub</a></li></ul></div>
  </div>
</footer>"""


def hero(art, key, root, *, kicker, title, cls="", dek=None, cite=None, lede=None, facts=None, actions=None, extra="",
         title_html=None):
    parts = [f'<div class="kicker">{kicker}</div>' if kicker else "",
             title_html or f"<h1>{title}</h1>",
             f'<p class="dek">{dek}</p>' if dek else "",
             f'<div class="dek-cite">— {cite}</div>' if cite else "",
             f'<p class="lede">{lede}</p>' if lede else "",
             extra,
             ('<div class="facts">' + "".join(f"<span>{f}</span>" for f in facts) + "</div>") if facts else "",
             ('<div class="actions">' + actions + "</div>") if actions else ""]
    plate = f'<div class="plate">{art.caption(key)}</div>' if art.has(key) else ""
    image = art.img(key, root, eager=True) if art.has(key) else ""
    return (f'<header class="hero {cls}" style="--art:{art.color(key)};--focus:{art.focus(key)}">{image}'
            f'<div class="hero-in">{"".join(parts)}{plate}</div></header>')


def label(art, key):
    i = art.info.get(key, {})
    if not i.get("note"):
        return ""
    place = f", {esc(i['place'])}" if i.get("place") else ""
    return (f'<div class="art-label"><span class="kicker">On the cover</span>'
            f'<p><cite>{art.caption(key)}{place}.</cite> {esc(i["note"])}</p></div>')


def tile(art, key, root, href, kicker, title, sub="", cls="tile"):
    return (f'<a class="{cls}" href="{href}" style="background:{art.color(key)}">'
            f'{art.img(key, root, sizes="(max-width:700px) 100vw, 50vw", cls="")}'
            f'<span class="kicker">{kicker}</span><b>{title}</b>{f"<span class=sub>{sub}</span>" if sub else ""}</a>')


# ----------------------------------------------------------------------------- guide

class Chapter:
    def __init__(self, path):
        self.path = path
        self.num = int(path.name[:2])
        self.slug = path.stem
        self.text = path.read_text(encoding="utf-8")
        first = self.text.split("\n", 1)[0].lstrip("# ").strip()
        m = re.match(r"Chapter \d+\.\s+(.*)", first)
        self.title = m.group(1) if m else first
        self.art = f"ch{self.num:02d}"
        self.href = f"{self.slug}.html"
        self.minutes = max(1, round(words(self.text) / 230))
        self.blurb = ""
        self.track = None

    @property
    def label(self):
        return f"Chapter {self.num}" if self.num <= 16 else "Appendix"


def read_blurbs(chapters):
    readme = (GUIDE / "README.md").read_text(encoding="utf-8")
    for row in re.findall(r"^\|\s*(\d+)\s*\|\s*\[[^\]]*\]\([^)]*\)\s*\|\s*(.*?)\s*\|\s*$", readme, re.M):
        n = int(row[0])
        if n in chapters:
            chapters[n].blurb = row[1]


def split_epigraphs(text):
    """Pull the opening quotations out of a chapter; returns (text without them, [(quote_md, cite_md)])."""
    lines = text.split("\n")
    out, quotes, i = [], [], 0
    before_body = True
    while i < len(lines):
        line = lines[i]
        if before_body and line.startswith("## "):
            before_body = False
        if before_body and line.startswith("> ") and i + 1 < len(lines):
            j = i
            block = []
            while j < len(lines) and lines[j].startswith(">"):
                block.append(lines[j][1:].strip())
                j += 1
            if block and block[-1].startswith("— ") and len(block) >= 2:
                quotes.append((" ".join(block[:-1]), block[-1][2:]))
                i = j
                continue
        out.append(line)
        i += 1
    return "\n".join(out), quotes


def clean_chapter_markdown(text):
    text = text.split("\n", 1)[1]  # title goes in the hero
    text = "\n".join(l for l in text.split("\n")
                     if not (l.startswith("[") and "](README.md)" in l)
                     and not l.startswith("**Audio:**")
                     and l.strip() != "---")
    text = re.sub(r"\n## In this (?:chapter|appendix)\n.*?(?=\n## )", "\n", text, flags=re.S)
    return text


def match_audio(ch, heads):
    """Map h2 headings to the start times of the matching narration sections."""
    if not ch.track:
        return {}
    secs = ch.track["sections"][1:]
    if secs and secs[-1]["title"].startswith("End of chapter"):
        secs = secs[:-1]
    h2 = [h for h in heads if h[0] == 2 and h[2] not in ("Further reading",)]
    if len(h2) != len(secs):
        print(f"  note: {ch.slug}: {len(h2)} sections in text, {len(secs)} in audio; matching by title")
        out = {}
        norm = lambda s: re.sub(r"[^a-z]", "", s.lower())
        for level, slug, plain, _ in h2:
            for s in secs:
                if norm(s["title"])[:18] == norm(plain)[:18]:
                    out[slug] = s["start"]
        return out
    return {h[1]: s["start"] for h, s in zip(h2, secs)}


def build_chapter(ch, chapters, md, art, svgs_later):
    root = "../"
    text, epigraphs = split_epigraphs(ch.text)
    body_md = clean_chapter_markdown(text)
    body, heads = md.render(body_md, guide_links())
    body = polish(body)
    at = match_audio(ch, heads)

    def h2(m):
        slug, inner = m.group(1), m.group(2)
        hear = ""
        if slug in at:
            hear = (f'<button class="hear" type="button" data-at="{at[slug]}" title="Listen from this section">'
                    f'{icon("phones")}<span>Listen</span></button>')
        return f'<h2 id="{slug}"><span class="ht">{inner}</span>{hear}</h2>'
    body = re.sub(r'<h2 id="([^"]+)">(.*?)</h2>', h2, body)
    if ch.num == 17:
        body = re.sub(r'<h2 id="([a-z])"><span class="ht">([A-Z])</span></h2>', r'<h2 id="\1" class="glossary-letter">\2</h2>', body)
    body = re.sub(r"^<p>", '<p class="lede">', body, count=1)

    more_quotes = "".join(
        f'<blockquote class="quote"><p>{md.inline(q)}</p><span class="by">— {md.inline(c)}</span></blockquote>'
        for q, c in epigraphs[1:])
    toc_items = [(slug, inner) for level, slug, plain, inner in heads if level == 2]
    toc = "".join(f'<li><a href="#{slug}">{re.sub(r"<[^>]+>", "", inner)}</a></li>' for slug, inner in toc_items)
    roman, part = PART_OF.get(ch.num, ("", ""))
    kicker = (f"Part {roman} · {part} · Chapter {ch.num}" if roman else "Appendix")
    facts = [f"{icon('clock')} {ch.minutes} min read"]
    listen_card, actions = "", f'<a class="btn primary" href="#main">Start reading {icon("arrow")}</a>'
    if ch.track:
        facts.append(f"{icon('phones')} {minutes_label(ch.track['duration'])} audio")
        sections = [{"t": "Opening" if i == 0 else s["title"], "s": s["start"]} for i, s in enumerate(ch.track["sections"])]
        chips = "".join(f'<button class="chip" type="button" data-at="{s["s"]}">{esc(s["t"])} <small>{int(s["s"] // 60)}:{int(s["s"] % 60):02d}</small></button>'
                        for s in sections)
        listen_card = (f'<section class="listen" data-audio="audio/{ch.track["file"]}" data-thumb="{art.src(ch.art, root, 640)}" '
                       f'data-title="{attr(ch.label + ": " + ch.title)}" data-sections="{attr(json.dumps(sections))}" aria-label="Listen to this chapter">'
                       f'<button class="play" type="button" aria-label="Play the narrated chapter">{icon("play", "icon i-play")}'
                       f'<svg class="icon i-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" stroke="none"/></svg></button>'
                       f'<span class="kicker">Listen · {minutes_label(ch.track["duration"])} · narrated</span>'
                       f'<h2>Hear this chapter read aloud <span class="resume" style="font-weight:400;color:var(--dim)"></span></h2>'
                       f'<div class="row">{chips}</div></section>')
        actions += f'<button class="btn" type="button" data-listen>{icon("phones")} Listen</button>'
    dek = cite = None
    if epigraphs:
        dek, cite = md.inline(epigraphs[0][0]), md.inline(epigraphs[0][1])
    head = hero(art, ch.art, root, kicker=kicker, title=esc(ch.title), dek=dek, cite=cite, facts=facts, actions=actions)

    listen_link = (f'<button type="button" data-listen>{icon("phones")} Listen</button>' if ch.track else "")
    focus_head = (f'<div class="focus-head"><span class="kicker">{kicker}</span><div class="ftitle" role="heading" aria-level="1">{esc(ch.title)}</div>'
                  f'<div class="fmeta"><span>{ch.minutes} min read</span>{listen_link}'
                  f'<button type="button" data-focus-toggle>Leave focus mode</button></div></div>')
    prev_ch, next_ch = chapters.get(ch.num - 1), chapters.get(ch.num + 1)
    pager = '<nav class="pager" aria-label="Chapters">'
    pager += (tile(art, prev_ch.art, root, prev_ch.href, f"← Previous · {prev_ch.label}", esc(prev_ch.title)) if prev_ch
              else tile(art, "guide", root, "./", "← Contents", "The guide"))
    pager += (tile(art, next_ch.art, root, next_ch.href, f"Next · {next_ch.label} →", esc(next_ch.title), cls="tile next") if next_ch
              else tile(art, "home", root, "../", "Home →", SITE, cls="tile next"))
    pager += "</nav>"
    page = (f"{head}{label(art, ch.art)}"
            f'<main id="main" class="page"><aside class="side"><nav class="toc" aria-label="In this chapter">'
            f'<span class="kicker">In this chapter</span><ol>{toc}</ol></nav></aside>'
            f'<article data-slug="{ch.slug}" data-read-min="{ch.minutes}">{focus_head}{listen_card}<details class="mini-toc"><summary>In this chapter</summary><ol>{toc}</ol></details>'
            f'<div class="prose">{more_quotes}{body}</div></article></main>{pager}')
    desc = ch.blurb.replace("*", "") or f"{ch.label}: {ch.title}"
    svgs_later.append((GUIDE / ch.href, page, root, ch, desc))


# ----------------------------------------------------------------------------- concepts

def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


class Concepts:
    def __init__(self):
        data = load_js_json(ASSETS / "data" / "concepts.js", "window.EPIS=")
        self.N, self.R, self.UI = data["N"], data["R"], data["UI"]
        self.parent = {}
        for pid, n in self.N.items():
            for c in n.get("c", []):
                self.parent[c] = pid

    def route(self, cid):
        r = [cid]
        while r[0] in self.parent:
            r.insert(0, self.parent[r[0]])
        return r

    def branch(self, cid):
        r = self.route(cid)
        return r[1] if len(r) > 1 else "root"

    def title(self, cid, lang="en"):
        n = self.N[cid]
        t = n["tf"] if lang == "fa" else n["t"]
        return "Epistemology" if cid == "root" and lang == "en" else t

    def line(self, cid, lang="en"):
        return self.R.get(cid, {}).get(lang, {}).get("line", "")


def guide_heading_index(chapters, md):
    idx = []
    for ch in chapters.values():
        if ch.num > 16:
            continue
        _, heads = md.render(clean_chapter_markdown(split_epigraphs(ch.text)[0]), lambda h: h)
        for level, slug, plain, _ in heads:
            idx.append((ch.num, slug, plain))
    return idx


def best_section(title, branch_ch, idx):
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", re.sub(r"\(.*?\)", "", s.lower()))).strip()
    stop = {"the", "a", "an", "of", "and", "in", "to"}
    t = norm(title)
    tw = [w for w in t.split() if w not in stop]
    best, score = None, 0
    for num, slug, plain in idx:
        h = norm(plain)
        hw = set(h.split())
        s = 0
        if h == t or h == "the " + t or "the " + h == t:
            s = 6
        elif t and (h.startswith(t) or t.startswith(h)) and len(h) > 3:
            s = 4
        elif tw and all(w in hw for w in tw):
            s = 3
        if s and num == branch_ch:
            s += 1
        if s > score:
            best, score = (num, slug, plain), s
    return best if score >= 3 else None


def concept_body(C, cid, lang):
    UI = C.UI[lang]
    n, r = C.N[cid], C.R.get(cid, {}).get(lang, {})
    body_html = n.get(lang, "")
    ex, ap = n.get("xf" if lang == "fa" else "xe", ""), n.get("pf" if lang == "fa" else "pe", "")

    def blk(num, cls, head, inner):
        return f'<section class="blk {cls}"><h2><i>{num}</i>{esc(head.capitalize() if lang == "en" else head)}</h2>{inner}</section>'
    out = [f'<p class="oneline">{r["line"]}</p>' if r.get("line") else ""]
    k = 0

    def nxt():
        nonlocal k
        k += 1
        return k
    if r.get("why"):
        out.append(blk(nxt(), "", UI["why"], r["why"]))
    out.append(blk(nxt(), "", UI["idea"], r.get("idea") or body_html))
    if r.get("origin"):
        out.append(blk(nxt(), "origin", UI["origin"], f"<p>{r['origin']}</p>"))
    if ex:
        out.append(blk(nxt(), "", UI["ex"], f"<p>{ex}</p>"))
    if r.get("obj"):
        inner = "".join(f'<div class="qa"><p class="o"><em>{UI["objL"]}.</em> {o}</p><p><em>{UI["repL"]}.</em> {rep}</p></div>'
                        for o, rep in r["obj"])
        out.append(blk(nxt(), "obj", UI["obj"], inner))
    if r.get("confuse"):
        inner = "".join(f'<div class="pair"><p class="pt">{a}</p><p>{b}</p></div>' for a, b in r["confuse"])
        out.append(blk(nxt(), "", UI["confuse"], inner))
    if r.get("mistakes"):
        out.append(blk(nxt(), "mist", UI["mist"], "<ul>" + "".join(f"<li>{m}</li>" for m in r["mistakes"]) + "</ul>"))
    if ap:
        out.append(blk(nxt(), "app", UI["app"], f"<p>{ap}</p>"))
    if r.get("check"):
        out.append(blk(nxt(), "check", UI["check"],
                       f'<p class="cq">{r["check"]["q"]}</p><details><summary>{UI["show"]}</summary><p>{r["check"]["a"]}</p></details>'))
    return "".join(out)


def build_concepts(C, chapters, md, art, pages):
    root = "../"
    idx = guide_heading_index(chapters, md)
    order = []

    def walk(cid):
        order.append(cid)
        for c in C.N[cid].get("c", []):
            if c in C.N:
                walk(c)
    walk("root")
    for cid in order:
        n = C.N[cid]
        branch = C.branch(cid)
        key = BRANCH_ART.get(branch, "home")
        chn = BRANCH_CHAPTER.get(branch, 1)
        route = C.route(cid)[:-1]
        crumbs_en = "".join(f'<a href="{a}.html">{esc(C.title(a))}</a><span>›</span>' for a in route)
        crumbs_fa = "".join(f'<a href="{a}.html">{esc(C.title(a, "fa"))}</a><span>‹</span>' for a in route)
        who = n.get("w", "")
        switch = ('<div class="langswitch" role="group" aria-label="Language">'
                  '<button type="button" data-set-lang="en" aria-label="Read in English">EN</button>'
                  '<button type="button" data-set-lang="fa" aria-label="مطالعه به فارسی">فا</button></div>')
        extra = (f'<div class="crumbs l-en">{crumbs_en or "<span>Concept map</span>"}</div>'
                 f'<div class="crumbs l-fa">{crumbs_fa or "<span>نقشهٔ مفاهیم</span>"}</div>'
                 f'<h1 class="l-en">{esc(C.title(cid))}</h1><h1 class="l-fa" lang="fa">{esc(C.title(cid, "fa"))}</h1>'
                 f'<div class="who">{esc(who)}</div>'
                 f'<div class="actions">{switch}'
                 f'<a class="btn" href="../map/#{cid}">{icon("pin")} <span class="l-en">Show on the map</span><span class="l-fa">نمایش روی نقشه</span></a></div>')
        head = hero(art, key, root, kicker="", title="", cls="band", title_html=extra)
        entry = (f'<div class="entry"><div class="l-en" lang="en">{concept_body(C, cid, "en")}</div>'
                 f'<div class="l-fa" lang="fa" dir="rtl">{concept_body(C, cid, "fa")}</div></div>')
        side = []
        kids = [k for k in n.get("c", []) if k in C.N]
        if kids:
            li_en = "".join(f'<li><a href="{k}.html"><b>{esc(C.title(k))}</b><small>{esc(strip_tags(C.line(k)))}</small></a></li>' for k in kids)
            li_fa = "".join(f'<li><a href="{k}.html"><b>{esc(C.title(k, "fa"))}</b><small>{esc(strip_tags(C.line(k, "fa")))}</small></a></li>' for k in kids)
            side.append(f'<section class="box"><h2 class="l-en">Go deeper · {len(kids)}</h2><h2 class="l-fa">عمیق‌تر شوید · {len(kids)}</h2>'
                        f'<ul class="l-en">{li_en}</ul><ul class="l-fa">{li_fa}</ul></section>')
        links = [k for k in n.get("k", []) if k in C.N]
        if links:
            li_en = "".join(f'<li><a href="{k}.html"><b>↗ {esc(C.title(k))}</b></a></li>' for k in links)
            li_fa = "".join(f'<li><a href="{k}.html"><b>↗ {esc(C.title(k, "fa"))}</b></a></li>' for k in links)
            side.append(f'<section class="box"><h2 class="l-en">Connects across the map</h2><h2 class="l-fa">پیوندها در سراسر نقشه</h2>'
                        f'<ul class="l-en">{li_en}</ul><ul class="l-fa">{li_fa}</ul></section>')
        ch = chapters[chn]
        sec = best_section(n["t"], chn, idx) if cid != "root" else None
        if sec:
            ch = chapters[sec[0]]
            href = f"../guide/{ch.href}#{sec[1]}"
            where = f"§ {esc(sec[2])}"
        else:
            href, where = f"../guide/{ch.href}", "Read the chapter"
        side.append(f'<section class="box"><h2 class="l-en">In the guide</h2><h2 class="l-fa">در راهنما (انگلیسی)</h2>'
                    f'<a class="guidebox" href="{href}"><img src="{art.src(ch.art, root, 640)}" alt="" loading="lazy">'
                    f'<span><small>Chapter {ch.num}</small><b>{esc(ch.title)}</b><small style="text-transform:none;letter-spacing:0">{where}</small></span></a></section>')
        q = n.get("q") or n["t"]
        side.append(f'<section class="box"><h2 class="l-en">Learn more</h2><h2 class="l-fa">مطالعهٔ بیشتر</h2><ul>'
                    f'<li><a href="https://plato.stanford.edu/search/searcher.py?query={attr(q.replace(" ", "+"))}" rel="noopener"><b>Stanford Encyclopedia of Philosophy ↗</b><small>Peer-reviewed reference articles</small></a></li>'
                    f'<li class="l-en"><a href="https://en.wikipedia.org/w/index.php?search={attr(q.replace(" ", "+"))}" rel="noopener"><b>Wikipedia ↗</b><small>Background and further reading</small></a></li>'
                    f'<li class="l-fa"><a href="https://fa.wikipedia.org/w/index.php?search={attr(C.title(cid, "fa").replace(" ", "+"))}" rel="noopener"><b>ویکی‌پدیای فارسی ↗</b><small>پیش‌زمینه و مطالعهٔ بیشتر</small></a></li>'
                    f'</ul></section>')
        par = C.parent.get(cid)
        sibs = [s for s in C.N[par]["c"] if s in C.N] if par else []
        i = sibs.index(cid) if cid in sibs else -1
        prev_id = sibs[i - 1] if i > 0 else None
        next_id = sibs[i + 1] if 0 <= i < len(sibs) - 1 else (kids[0] if kids else None)
        sib = '<nav class="sibs" aria-label="Neighbouring concepts">'
        if prev_id:
            sib += f'<a href="{prev_id}.html"><small>← Previous</small><b class="l-en">{esc(C.title(prev_id))}</b><b class="l-fa">{esc(C.title(prev_id, "fa"))}</b></a>'
        elif par:
            sib += f'<a href="{par}.html"><small>↑ Up</small><b class="l-en">{esc(C.title(par))}</b><b class="l-fa">{esc(C.title(par, "fa"))}</b></a>'
        if next_id:
            sib += f'<a class="n" href="{next_id}.html"><small>Next →</small><b class="l-en">{esc(C.title(next_id))}</b><b class="l-fa">{esc(C.title(next_id, "fa"))}</b></a>'
        sib += "</nav>"
        body = (f"{head}<main id=\"main\" class=\"cpage\">{entry}<aside class=\"aside\">{''.join(side)}</aside></main>{sib}")
        desc = strip_tags(C.line(cid)) or f"{C.title(cid)}: a concept in epistemology."
        pages.append((ROOT / "concepts" / f"{cid}.html", root, f"{C.title(cid)} · Concepts", desc, body, "concepts", key))

    # index of concepts
    branches = [b for b in C.N["root"]["c"] if b in C.N]
    blocks = []
    for b in branches:
        members = []

        def walk2(cid, depth):
            for c in C.N[cid].get("c", []):
                if c in C.N:
                    members.append((c, depth))
                    walk2(c, depth + 1)
        walk2(b, 0)
        hay = lambda cid: attr((C.title(cid) + " " + C.title(cid, "fa") + " " + strip_tags(C.line(cid)) + " " + C.N[cid].get("q", "")).lower())
        items = "".join(f'<a class="{"d3" if d else ""}" href="{c}.html" data-hay="{hay(c)}"><b class="l-en">{esc(C.title(c))}</b>'
                        f'<b class="l-fa">{esc(C.title(c, "fa"))}</b><small class="l-en">{esc(strip_tags(C.line(c)))}</small>'
                        f'<small class="l-fa">{esc(strip_tags(C.line(c, "fa")))}</small></a>' for c, d in members)
        key = BRANCH_ART.get(b, "home")
        blocks.append(f'<section class="branch" data-hay="{hay(b)}"><header><img src="{art.src(key, root, 640)}" alt="" loading="lazy">'
                      f'<div><a href="{b}.html"><b class="l-en">{esc(C.title(b))}</b><b class="l-fa">{esc(C.title(b, "fa"))}</b></a>'
                      f'<p class="l-en">{esc(strip_tags(C.line(b)))}</p><p class="l-fa">{esc(strip_tags(C.line(b, "fa")))}</p></div></header>'
                      f'<div class="clist">{items}</div></section>')
    switch = ('<div class="langswitch" role="group" aria-label="Language"><button type="button" data-set-lang="en">EN</button>'
              '<button type="button" data-set-lang="fa">فا</button></div>')
    head = hero(art, "elephant", root, kicker="The concept map as pages", title="All concepts", cls="short",
                lede="135 concepts in epistemology, each with a full entry in English and Persian: the problem it solves, the idea, "
                     "objections and replies, common confusions, and a question to check yourself.",
                actions=f'{switch}<a class="btn" href="../map/">{icon("map")} Open the map</a><a class="btn" href="root.html">Start at the root</a>')
    body = (f'{head}{label(art, "elephant")}<main id="main" class="wrap" style="padding-top:36px;padding-bottom:80px">'
            f'<div class="filter"><input id="cfilter" type="search" placeholder="Filter concepts, thinkers, terms…" aria-label="Filter concepts"></div>'
            f'{"".join(blocks)}</main>')
    pages.append((ROOT / "concepts" / "index.html", root, "All concepts",
                  "Every concept in the epistemology map as a readable page, in English and Persian.", body, "concepts", "elephant"))


# ----------------------------------------------------------------------------- other pages

def chapter_card(art, ch, root):
    meta = f'<span>{icon("clock")} {ch.minutes} min</span>'
    if ch.track:
        meta += f'<span>{icon("phones")} {minutes_label(ch.track["duration"])}</span>'
    blurb = re.sub(r"\*([^*]+)\*", r"\1", ch.blurb)
    return (f'<a class="card" href="{root}guide/{ch.href}" data-slug="{ch.slug}"><div class="pic" style="--art:{art.color(ch.art)};--focus:{art.focus(ch.art)}">'
            f'{art.img(ch.art, root, sizes="(max-width:600px) 100vw, 320px", cls="")}<span class="num">{ch.label.upper()}</span></div>'
            f'<div class="body"><h4>{esc(ch.title)}</h4><p>{esc(blurb)}</p><div class="meta">{meta}</div></div></a>')


def contents_parts(art, chapters, root):
    out = []
    for roman, name, nums in PARTS:
        cards = "".join(chapter_card(art, chapters[n], root) for n in nums)
        out.append(f'<section class="part"><header><span class="kicker">{"Part " + roman if roman else "Also"}</span>'
                   f'<h3>{esc(name)}</h3></header><div class="grid">{cards}</div></section>')
    return "".join(out)


def readme_sections(md):
    text = (GUIDE / "README.md").read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)
    intro = parts[0]
    secs = {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] for p in parts[1:]}
    return intro, secs


def build_guide_index(art, chapters, md, total_audio):
    root = "../"
    intro, secs = readme_sections(md)
    intro = re.sub(r"^# .*\n", "", intro)
    intro, quotes = split_epigraphs(intro)
    intro = "\n".join(l for l in intro.split("\n") if l.strip() not in ("---",) and not l.startswith("**A complete"))
    intro_html, _ = md.render(intro, guide_links())
    intro_html = re.sub(r"^<p>", '<p class="lede">', intro_html.strip(), count=1)
    def sec(name):
        body = secs.get(name, "")
        body = "\n".join(l for l in body.split("\n") if l.strip() != "---")
        h, _ = md.render(body, guide_links())
        return polish(h)
    paths = sec("Learning paths")
    how = sec("How each chapter works")
    connect = sec("How the ideas connect")
    companion = sec("The companion explorer")
    sources = sec("A note on sources and accuracy")
    q, c = quotes[0] if quotes else ("", "")
    head = hero(art, "guide", root, kicker="The guide · sixteen chapters, a glossary and a reading list", title="Mastering Epistemology",
                dek=md.inline(q) if q else None, cite=md.inline(c) if c else None,
                facts=[f"{icon('book')} 16 chapters", f"{icon('clock')} about 130,000 words", f"{icon('phones')} {total_audio} of audio"],
                actions=f'<a class="btn primary" href="01-what-is-epistemology.html">Start with chapter 1 {icon("arrow")}</a>'
                        f'<a class="btn" href="audio/">{icon("phones")} Listen</a>'
                        f'<a class="btn" href="{EPUB_NAME}" download>{icon("download")} EPUB</a>')
    body = (f'{head}{label(art, "guide")}'
            f'<main id="main"><div class="wrap" style="padding-top:34px"><div id="resume"></div><div class="prose" style="max-width:46rem">{intro_html}</div></div>'
            f'<section class="section" style="padding-top:40px"><div class="wrap">{contents_parts(art, chapters, root)}</div></section>'
            f'<section class="section alt"><div class="wrap"><div class="section-head"><div><span class="kicker">How the ideas connect</span>'
            f'<h2>One question, many branches</h2></div><p>Every chapter answers part of a single question: what should I believe, and how sure should I be?</p></div>'
            f'<div class="prose" style="max-width:none">{connect}</div></div></section>'
            f'<section class="section"><div class="wrap"><div class="section-head"><div><span class="kicker">Learning paths</span>'
            f'<h2>Where to start</h2></div></div><div class="prose" style="max-width:52rem">{paths}</div></div></section>'
            f'<section class="section alt"><div class="wrap" style="display:grid;gap:40px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">'
            f'<div class="prose"><h2 style="border:0;padding:0;margin-top:0">How each chapter works</h2>{how}</div>'
            f'<div class="prose"><h2 style="border:0;padding:0;margin-top:0">The companion map</h2>{companion}'
            f'<h2 style="border:0;padding:0">A note on sources</h2>{sources}</div></div></section></main>')
    return body


def build_home(art, chapters, md, total_audio, n_concepts):
    root = ""
    intro, secs = readme_sections(md)
    paths_md = secs.get("Learning paths", "")
    paths = []
    for m in re.finditer(r"^\*\*(.+?)\*\*(.*?):\s*(.+)$", paths_md, re.M):
        name, note, seq = m.group(1), m.group(2).strip(" ()"), m.group(3)
        nums = re.findall(r"\[(\d+)\]\((\d\d-[\w-]+)\.md", seq)
        if not nums:
            continue
        chips = "".join(f'<li><a href="guide/{slug}.html" title="{attr(chapters[int(n)].title)}">{n}</a></li>' for n, slug in nums)
        paths.append(f'<div class="path"><h4>{esc(name)}</h4><p>{esc(note)}</p><ol>{chips}</ol></div>')
    head = hero(art, "home", root, kicker="A free course in the theory of knowledge", title="How do you know?",
                lede=(f"<b>{SITE}</b> is a complete guide to knowledge, evidence, and critical thinking: sixteen illustrated chapters, "
                      f"a bilingual map of {n_concepts} concepts, and {total_audio} of narrated audio."),
                facts=[f"{icon('book')} 16 chapters", f"{icon('map')} {n_concepts} concepts · English &amp; فارسی", f"{icon('phones')} {total_audio} audio"],
                actions=(f'<a class="btn primary" href="guide/01-what-is-epistemology.html">Start reading {icon("arrow")}</a>'
                         f'<a class="btn" href="map/">{icon("map")} Explore the map</a>'
                         f'<a class="btn" href="guide/audio/">{icon("phones")} Listen</a>'))
    doors = (f'<div class="doors">'
             + tile(art, "guide", root, "guide/", "Read", "The guide",
                    "Sixteen chapters, from the Gettier problem to Bayes' theorem, with worked examples and self-checks.", cls="tile door")
             + tile(art, "map", root, "map/", "Explore", "The concept map",
                    f"{n_concepts} ideas as a living map you can pan and expand, in English and Persian, each with a full entry.", cls="tile door")
             + tile(art, "audio", root, "guide/audio/", "Listen", "The audio edition",
                    f"Every chapter narrated, {total_audio} in all, with section markers and a quiz after each chapter.", cls="tile door")
             + "</div>")
    stats = (f'<div class="statline"><div><b>16</b><span>chapters in five parts</span></div><div><b>{n_concepts}</b><span>concepts, in English and Persian</span></div>'
             f'<div><b>14½</b><span>hours of narration</span></div><div><b>200</b><span>glossary terms</span></div></div>')
    body = (f'{head}<main id="main">'
            f'<section class="section"><div class="wrap"><div id="resume"></div><div class="section-head"><div><span class="kicker">Three ways in</span>'
            f'<h2>Read it, map it, or hear it</h2></div><p>The same ideas, three ways. Start wherever suits you; everything is cross-linked.</p></div>{doors}'
            f'<div style="margin-top:28px">{stats}</div></div></section>'
            f'<section class="section alt"><div class="wrap"><div class="section-head"><div><span class="kicker">The course</span>'
            f'<h2>Sixteen chapters, each with a masterpiece</h2></div><p>Every chapter opens with a painting or photograph that captures its question, '
            f'from Raphael\'s <i>School of Athens</i> to the <i>Earthrise</i> photograph.</p></div>{contents_parts(art, chapters, root)}</div></section>'
            f'<section class="quoteband"><img src="{art.src("cave", root, 2000)}" alt="{attr(art.alt("cave"))}" loading="lazy">'
            f'<div class="wrap"><blockquote><p>“The duty of the man who investigates the writings of scientists, if learning the truth is his goal, '
            f'is to make himself an enemy of all that he reads.”</p><footer>— Ibn al-Haytham, Doubts Concerning Ptolemy, c. 1025</footer></blockquote></div></section>'
            f'<section class="section"><div class="wrap"><div class="section-head"><div><span class="kicker">Learning paths</span>'
            f'<h2>Short on time?</h2></div><p>Follow a path through the chapters that fits your goal.</p></div><div class="paths">{"".join(paths)}</div></div></section>'
            f'</main>')
    return body


def build_audio_page(art, chapters, tracks):
    root = "../../"
    head = hero(art, "audio", root, kicker="The audio edition", title="Listen", cls="short",
                lede="Every chapter of the guide, narrated. Pick up where you left off, jump to any section, and change the speed. "
                     "Each chapter ends with a spoken quiz, with time to think.",
                facts=[f"{icon('phones')} {minutes_label(sum(t['duration'] for t in tracks))}", "16 chapters", "MP3 with chapter markers"])
    data = [{"file": t["file"], "title": t["title"], "duration": t["duration"], "page": f"../{t['text'][3:].replace('.md', '.html')}",
             "sections": t["sections"]} for t in tracks]
    thumbs = [art.src(f"ch{i + 1:02d}", root, 640) for i in range(len(tracks))]
    body = (f'{head}<main id="main" class="wrap" style="padding-bottom:80px">'
            f'<section class="player" id="player" aria-label="Player"><span class="kicker" style="color:var(--accent)">Now playing</span>'
            f'<h2>Choose a chapter</h2><div class="sec"></div><audio controls preload="metadata"></audio>'
            f'<div class="ctl"><button id="prev" type="button">⏮ Chapter</button><button id="back" type="button">↺ 15 s</button>'
            f'<button id="fwd" type="button">30 s ↻</button><button id="next" type="button">Chapter ⏭</button>'
            f'<label>Speed <select id="rate"><option>0.8</option><option>0.9</option><option selected>1</option><option>1.1</option>'
            f'<option>1.25</option><option>1.5</option><option>1.75</option></select></label>'
            f'<a class="btn" id="read" href="../01-what-is-epistemology.html" style="min-height:40px">{icon("book")} Read this chapter</a></div></section>'
            f'<div class="tracks"><section><h2 class="kicker" style="color:var(--dim)">Chapters</h2><ol id="chapters"></ol></section>'
            f'<section class="secs"><h2 class="kicker" style="color:var(--dim)">Sections in this chapter</h2><ol id="sections"></ol></section></div>'
            f'<p style="color:var(--dim);font-size:.95rem;margin-top:30px">The narration is generated with a synthetic voice, the open Kokoro-82M '
            f'text-to-speech model, from scripts adapted for listening. <a href="about.html">How the audio was made</a>. '
            f'Keyboard: <kbd>k</kbd> or space to play and pause, <kbd>j</kbd> and <kbd>l</kbd> to skip.</p></main>'
            f'<script>window.TRACKS={json.dumps(data, ensure_ascii=False)};window.TRACK_ART={json.dumps(thumbs)};</script>')
    return body


def build_audio_about(art, md):
    root = "../../"
    text = (GUIDE / "audio" / "README.md").read_text(encoding="utf-8")
    text = re.sub(r"^# .*\n", "", text)

    def links(href):
        if href == "index.html":
            return "./"
        if href.endswith(".mp3"):
            return href
        if href.startswith(("scripts/", "tools/")):
            return f"{REPO}/tree/main/guide/audio/{href}"
        return href
    body_html, heads = md.render(text, links)
    head = hero(art, "audio", root, kicker="The audio edition", title="How the audio was made", cls="band")
    return (f'{head}<main id="main" class="wrap" style="padding-top:36px;padding-bottom:80px">'
            f'<div class="prose" style="max-width:46rem;margin:0 auto">{polish(body_html)}</div></main>')


def build_credits(art):
    root = ""
    cards = []
    for key, i in art.info.items():
        if not art.has(key):
            continue
        c = art.credits.get(key, {})
        src = c.get("source") or ""
        place = f" {esc(i['place'])}." if i.get("place") else ""
        cards.append(f'<div class="credit"><img src="{art.src(key, root, 640)}" alt="" loading="lazy"><div><b>{art.caption(key)}</b>'
                     f'<p>{place.strip()} {esc(c.get("license") or "Public domain")}, via '
                     f'<a href="{attr(src)}" rel="noopener">Wikimedia Commons</a>.</p></div></div>')
    head = hero(art, "ch18", root, kicker="Credits", title="Artwork, sound and type", cls="band")
    faces = [("Cormorant Garamond", "cormorant-garamond"), ("Source Serif 4", "source-serif-4"), ("Space Grotesk", "space-grotesk"),
             ("IBM Plex Mono", "ibm-plex-mono"), ("Vazirmatn", "vazirmatn"), ("Atkinson Hyperlegible", "atkinson-hyperlegible")]
    names = [f'<a href="assets/fonts/licenses/{slug}-OFL.txt">{name}</a>' for name, slug in faces]
    fonts = ", ".join(names[:-1]) + " and " + names[-1]
    body = (f'{head}<main id="main" class="wrap" style="padding-top:36px;padding-bottom:80px"><div class="prose" style="max-width:46rem">'
            f'<p class="lede">The paintings, prints and photographs on this site are in the public domain. The images come from Wikimedia Commons; '
            f'follow each link for the source file and its description.</p></div>'
            f'<div class="credits">{"".join(cards)}</div>'
            f'<div class="prose" style="max-width:46rem;margin-top:40px"><h2>Sound</h2><p>The audio edition is narrated by a synthetic voice: '
            f'the <a href="https://huggingface.co/hexgrad/Kokoro-82M">Kokoro-82M</a> text-to-speech model (Apache License 2.0), with pronunciation by '
            f'<a href="https://github.com/hexgrad/misaki">misaki</a>. See <a href="guide/audio/about.html">how the audio was made</a>.</p>'
            f'<h2>Type</h2><p>{fonts}, all under the SIL Open Font License (follow a name for its licence).</p></div></main>')
    return body


BASE_404 = ('<script>(function(){var p=location.pathname.split("/"),b="/";'
            'if(/\\.github\\.io$/.test(location.hostname)&&p.length>2)b="/"+p[1]+"/";'
            'document.write(\'<base href="\'+b+\'">\')})();</script>')


def build_notebook(art):
    root = "../"
    head = hero(art, "ch18", root, kicker="Your notebook", title="Highlights and notes", cls="band",
                lede="Everything you have highlighted or written, from every chapter and concept page. "
                     "It is kept in this browser; export it to keep a copy or to move it to another device.")
    filters = ""
    for c in ("all", "yellow", "green", "blue", "pink"):
        cls = "" if c == "all" else f' class="c-{c}"'
        filters += (f'<button type="button" data-filter="{c}" aria-pressed="{"true" if c == "all" else "false"}"{cls}>'
                    f'{"All" if c == "all" else ""}<span class="sr">{c}</span></button>')
    return (f'{head}<main id="main" class="wrap notebook-page">'
            f'<div class="nb-tools"><input id="nb-q" type="search" placeholder="Search your notes" aria-label="Search your notes">'
            f'<div class="nb-filters" role="group" aria-label="Filter by colour">{filters}</div>'
            f'<div class="nb-actions"><button type="button" id="nb-md">{icon("download")} Markdown</button>'
            f'<button type="button" id="nb-json">{icon("download")} Backup (.json)</button>'
            f'<button type="button" id="nb-import">Import backup</button><input id="nb-file" type="file" accept=".json,application/json" hidden></div>'
            f'<p id="nb-count" class="nb-count"></p></div>'
            f'<div id="notebook" aria-live="polite"></div></main>')


def build_404(art):
    head = hero(art, "cave", "", kicker="Error 404", title="Only shadows here",
                lede="The page you were looking for isn't on this site. Perhaps it was only ever an appearance.",
                actions='<a class="btn primary" href="./">Go to the start</a>')
    return f'<main id="main">{head}</main>'


# ----------------------------------------------------------------------------- offline, app manifest, EPUB

MANIFEST = {
    "name": SITE, "short_name": "Epistemology", "description": "A complete guide to knowledge, evidence, and critical thinking.",
    "start_url": "./", "scope": "./", "display": "standalone", "background_color": "#F6F3EC", "theme_color": "#0A1620",
    "icons": [{"src": "assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
              {"src": "assets/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
}


def build_offline_list():
    """Everything "Save the whole guide for offline reading" fetches, relative to the site root."""
    paths = ["", "index.html", "guide/", "guide/index.html", "concepts/", "map/", "map/index.html", "credits.html",
             "guide/audio/", "guide/audio/index.html", "guide/audio/about.html", "guide/audio/tracks.js",
             "assets/site.css", "assets/site.js", "assets/notes.js", "notes/", "assets/favicon.svg", "assets/data/concepts.js", "assets/fonts/fonts.css",
             "manifest.webmanifest", "assets/icon-192.png"]
    paths += sorted(f"guide/{p.name}" for p in GUIDE.glob("[01][0-9]-*.html"))
    paths += sorted(f"concepts/{p.name}" for p in (ROOT / "concepts").glob("*.html"))
    paths += sorted(f"assets/fonts/{p.name}" for p in (ASSETS / "fonts").glob("*.woff2"))
    paths += sorted(f"assets/art/{p.name}" for p in ART_DIR.glob("*-640.jpg"))
    paths += sorted(f"assets/art/{p.name}" for p in ART_DIR.glob("*-1200.jpg"))
    return list(dict.fromkeys(paths))


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class XHTML(HTMLParser):
    """Re-serialise HTML fragments as well-formed XHTML for the EPUB."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        a = "".join(f' {k}="{html.escape(v if v is not None else k, quote=True)}"' for k, v in attrs)
        if tag in VOID:
            self.out.append(f"<{tag}{a}/>")
        else:
            self.out.append(f"<{tag}{a}>")
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        a = "".join(f' {k}="{html.escape(v if v is not None else k, quote=True)}"' for k, v in attrs)
        self.out.append(f"<{tag}{a}/>")

    def handle_endtag(self, tag):
        if tag in VOID or tag not in self.stack:
            return
        while self.stack:
            t = self.stack.pop()
            self.out.append(f"</{t}>")
            if t == tag:
                break

    def handle_data(self, data):
        self.out.append(html.escape(data, quote=False))

    def result(self):
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def xhtml(fragment):
    x = XHTML()
    x.feed(re.sub(r"<!--.*?-->", "", fragment, flags=re.S))
    x.close()
    return x.result()


EPUB_CSS = """body{font-family:serif;line-height:1.5;margin:0 4%}
h1{font-size:1.9em;line-height:1.15;margin:0.4em 0 0.2em}
h2{font-size:1.4em;margin:1.6em 0 0.5em;page-break-after:avoid}
h3{font-size:1.15em;margin:1.3em 0 0.4em;page-break-after:avoid}
p{margin:0 0 0.8em}
blockquote{margin:1em 1.5em;font-style:italic}
table{border-collapse:collapse;margin:1em 0;font-size:0.9em}
th,td{border:1px solid #999;padding:0.3em 0.5em;vertical-align:top;text-align:left}
.kicker{font-family:sans-serif;font-size:0.75em;letter-spacing:0.12em;text-transform:uppercase;color:#8A4F00}
figure.cover{margin:0 0 1em;text-align:center}
figure.cover img{max-width:100%}
figcaption{font-size:0.8em;color:#555;font-style:italic}
.note{font-family:sans-serif;font-size:0.85em;border:1px solid #ccc;padding:0.5em 0.8em}
code{font-family:monospace;font-size:0.9em}
"""


def epub_links(href):
    """Links inside the EPUB: between chapters stay inside the book, everything else goes to the website."""
    if re.match(r"^[a-z]+:", href) or href.startswith("#"):
        return href
    path, _, frag = href.partition("#")
    frag = "#" + frag if frag else ""
    m = re.match(r"^(\d\d-[\w-]+)\.md$", path)
    if m:
        return m.group(1) + ".xhtml" + frag
    if path == "../index.html":
        return LIVE + "map/" + frag
    if path == "README.md":
        return LIVE + "guide/" + frag
    if path.startswith("audio/"):
        return LIVE + "guide/" + (path.replace("README.md", "about.html")) + frag
    if path == "../README.md":
        return REPO + "#readme"
    return LIVE + "guide/" + href


def build_epub(chapters, art):
    """The whole guide as an EPUB 3 book, written by hand so no extra tools are needed."""
    import zipfile
    md = Markdown()
    try:
        modified = subprocess.run(["git", "log", "-1", "--format=%cI", "--", "guide"], cwd=ROOT, capture_output=True,
                                  text=True, check=True).stdout.strip()
        stamp = modified[:19] + "Z" if modified else "2026-01-01T00:00:00Z"
    except (OSError, subprocess.CalledProcessError):
        stamp = "2026-01-01T00:00:00Z"
    docs, nav, images = [], [], []
    for n, ch in sorted(chapters.items()):
        body, heads = md.render(clean_chapter_markdown(ch.text), epub_links)
        body = re.sub(r"<!--MERMAID:\w+-->",
                      f'<p class="note">This diagram is in the web edition: <a href="{LIVE}guide/{ch.href}">{html.escape(ch.title)}</a>.</p>', body)
        pic = ""
        if (ART_DIR / f"{ch.art}-640.jpg").exists():
            images.append(ch.art)
            cap = art.caption(ch.art) if hasattr(art, "caption") else ""
            pic = (f'<figure class="cover"><img src="images/{ch.art}.jpg" alt="{attr(art.alt(ch.art))}"/>'
                   f'{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>')
        roman, part = PART_OF.get(ch.num, ("", ""))
        kicker = f"Part {roman} · {part} · Chapter {ch.num}" if roman else "Appendix"
        name = f"{ch.slug}.xhtml"
        page = (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
                f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">'
                f'<head><meta charset="utf-8"/><title>{html.escape(ch.title)}</title><link rel="stylesheet" href="book.css"/></head>'
                f'<body><section epub:type="chapter">{pic}<p class="kicker">{html.escape(kicker)}</p><h1>{html.escape(ch.title)}</h1>'
                f'{xhtml(body)}</section></body></html>')
        docs.append((name, page))
        subs = "".join(f'<li><a href="{name}#{slug}">{html.escape(plain)}</a></li>' for level, slug, plain, _ in heads if level == 2)
        nav.append(f'<li><a href="{name}">{html.escape(ch.label + ": " + ch.title if ch.num <= 16 else ch.title)}</a>'
                   f'{f"<ol>{subs}</ol>" if subs else ""}</li>')
    cover = ("<?xml version='1.0' encoding='utf-8'?>\n<!DOCTYPE html>\n"
             '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">'
             '<head><meta charset="utf-8"/><title>Cover</title><link rel="stylesheet" href="book.css"/></head>'
             '<body><section epub:type="cover"><figure class="cover"><img src="images/cover.jpg" alt="Caspar David Friedrich, Wanderer above the Sea of Fog"/></figure>'
             f'<h1>{SITE}</h1><p>A complete guide to knowledge, evidence, and critical thinking.</p>'
             f'<p>The illustrated web edition, the concept map and the audio: <a href="{LIVE}">{LIVE}</a></p></section></body></html>')
    nav_doc = ("<?xml version='1.0' encoding='utf-8'?>\n<!DOCTYPE html>\n"
               '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">'
               '<head><meta charset="utf-8"/><title>Contents</title><link rel="stylesheet" href="book.css"/></head>'
               f'<body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol>{"".join(nav)}</ol></nav></body></html>')
    items = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
             '<item id="css" href="book.css" media-type="text/css"/>',
             '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
             '<item id="cover-image" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>']
    items += [f'<item id="img-{k}" href="images/{k}.jpg" media-type="image/jpeg"/>' for k in images]
    items += [f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>' for i, (name, _) in enumerate(docs)]
    spine = '<itemref idref="cover"/><itemref idref="nav"/>' + "".join(f'<itemref idref="c{i}"/>' for i in range(len(docs)))
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="en">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           '<dc:identifier id="uid">urn:uuid:5f0c7c1e-3f47-4c55-9a0c-6d2a9b1e7e11</dc:identifier>'
           f'<dc:title>{SITE}</dc:title><dc:creator>{SITE}</dc:creator><dc:language>en</dc:language>'
           f'<dc:source>{LIVE}</dc:source><meta property="dcterms:modified">{stamp}</meta></metadata>'
           f'<manifest>{"".join(items)}</manifest><spine>{spine}</spine></package>')
    container = ('<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    out = GUIDE / EPUB_NAME
    fixed = (2026, 1, 1, 0, 0, 0)

    def add(z, name, data, compress=True):
        info = zipfile.ZipInfo(name, fixed)
        info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
        z.writestr(info, data)
    with zipfile.ZipFile(out, "w") as z:
        add(z, "mimetype", "application/epub+zip", compress=False)
        add(z, "META-INF/container.xml", container)
        add(z, "OEBPS/content.opf", opf)
        add(z, "OEBPS/nav.xhtml", nav_doc)
        add(z, "OEBPS/cover.xhtml", cover)
        add(z, "OEBPS/book.css", EPUB_CSS)
        add(z, "OEBPS/images/cover.jpg", (ART_DIR / "home-1200.jpg").read_bytes(), compress=False)
        for k in images:
            add(z, f"OEBPS/images/{k}.jpg", (ART_DIR / f"{k}-640.jpg").read_bytes(), compress=False)
        for name, page in docs:
            add(z, f"OEBPS/{name}", page)
    return out


# ----------------------------------------------------------------------------- main

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    art = Art()
    print("artwork")
    art.derive()
    (ASSETS / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    md = Markdown()
    chapters = {}
    for p in sorted(GUIDE.glob("[01][0-9]-*.md")):
        ch = Chapter(p)
        chapters[ch.num] = ch
    read_blurbs(chapters)
    tracks = load_js_json(GUIDE / "audio" / "tracks.js", "window.TRACKS =")
    for t in tracks:
        n = int(t["file"][:2])
        if n in chapters:
            chapters[n].track = t
    total = sum(t["duration"] for t in tracks)
    total_label = f"{int(total // 3600)}½ hours" if 0.25 <= (total / 3600) % 1 < 0.75 else f"{round(total / 3600)} hours"
    C = Concepts()

    print("guide")
    later = []
    for ch in chapters.values():
        build_chapter(ch, chapters, md, art, later)
    guide_index = build_guide_index(art, chapters, md, total_label)
    home = build_home(art, chapters, md, total_label, len(C.N))
    svgs = render_mermaid(md)
    for path, page, root, ch, desc in later:
        page = place_diagrams(page, md, svgs)
        write(path, shell(root=root, title=f"{ch.label}: {ch.title}" if ch.num <= 16 else ch.title, desc=desc, body=page,
                          current="guide", hero_img=(art.src(ch.art, root), art.srcset(ch.art, root)), bar="clear", reader=True, focus=True))
    write(GUIDE / "index.html", shell(root="../", title="The guide", desc="Contents of Mastering Epistemology: sixteen chapters on knowledge, evidence, and critical thinking.",
                                      body=place_diagrams(guide_index, md, svgs), current="guide",
                                      hero_img=(art.src("guide", "../"), art.srcset("guide", "../")), bar="clear"))
    write(ROOT / "index.html", shell(root="", title=SITE, desc="A free, complete guide to epistemology and critical thinking: illustrated chapters, a bilingual concept map, and a narrated audio edition.",
                                     body=home, hero_img=(art.src("home", ""), art.srcset("home", "")), bar="clear"))

    print("concepts")
    pages = []
    build_concepts(C, chapters, md, art, pages)
    for path, root, title, desc, body, current, key in pages:
        write(path, shell(root=root, title=title, desc=desc, body=body, current=current,
                          hero_img=(art.src(key, root), art.srcset(key, root)), bar="clear", reader=True))

    print("audio, credits")
    write(GUIDE / "audio" / "index.html", shell(root="../../", title="Listen", desc="The narrated audio edition of Mastering Epistemology.",
                                                body=build_audio_page(art, chapters, tracks), current="audio",
                                                hero_img=(art.src("audio", "../../"), art.srcset("audio", "../../")), bar="clear"))
    write(GUIDE / "audio" / "about.html", shell(root="../../", title="How the audio was made", desc="How the narrated audio edition was produced.",
                                                body=build_audio_about(art, md), current="audio", bar="clear"))
    write(ROOT / "notes" / "index.html", shell(root="../", title="Notebook", desc="Your highlights and notes.",
                                               body=build_notebook(art), current="notes", bar="clear"))
    write(ROOT / "credits.html", shell(root="", title="Credits", desc="Credits for the artwork, audio and fonts on this site.",
                                       body=build_credits(art), bar="clear"))
    write(ROOT / "404.html", shell(root="", title="Page not found", desc="Page not found.", body=build_404(art), bar="clear")
          .replace("<meta charset=\"utf-8\">", "<meta charset=\"utf-8\">\n" + BASE_404, 1))
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    print("offline, epub")
    write(ROOT / "manifest.webmanifest", json.dumps(MANIFEST, indent=2) + "\n")
    write(ROOT / "offline.json", json.dumps(build_offline_list(), indent=0) + "\n")
    build_epub(chapters, art)
    print(f"done: {len(chapters)} chapters, {len(pages)} concept pages")


if __name__ == "__main__":
    main()
