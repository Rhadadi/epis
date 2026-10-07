#!/usr/bin/env python3
"""Build the Mastering Epistemology website from the guide and the concept map.

    python3 tools/site/build.py

Reads
    guide/NN-*.md, guide/README.md      the guide (the markdown stays the source of truth)
    guide/audio/tracks.js               audio tracks and their section times
    assets/data/concepts.js             the concepts: their entries, and the tree the concept pages follow
    tools/site/art.json                 artwork captions; images in assets/art/ (see fetch_art.py)
    tools/site/map-relations.json       the editorial relations between sections that the map explains (ids are checked)

Writes
    index.html                          the starting page
    fa/index.html                       the Persian starting page
    guide/index.html, guide/NN-*.html   the guide as web pages
    guide/audio/index.html, about.html  the audio player and how the audio was made
    concepts/index.html, concepts/*.html one readable page per concept, English and Persian
    map/index.html, fa/map/index.html   the map of the guide (its data embedded; drawn by assets/map.js)
    assets/data/map-{cards,passages}[-fa].json  what the map's idea cards and connections show, fetched after it draws
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
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path

from markdown_it import MarkdownIt
from PIL import Image
from reading_path import build_catalogue as build_reading_catalogue, page_body as reading_path_body

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "guide"
ASSETS = ROOT / "assets"
ART_DIR = ASSETS / "art"
DIAGRAMS = ASSETS / "diagrams"
TOOLS = Path(__file__).resolve().parent
SITE = "Mastering Epistemology"
SITE_FA = "تسلط بر معرفت‌شناسی"
EPUB_NAME = "mastering-epistemology.epub"
EPUB_NAME_FA = "mastering-epistemology-fa.epub"
LIVE = "https://epis.duckdns.org/"  # GitHub Pages, custom domain (CNAME)
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
PARTS_FA = {"I": ("یکم", "بنیادها"), "II": ("دوم", "هستهٔ معرفت‌شناسی"), "III": ("سوم", "شواهد، علم و حقیقت"),
            "IV": ("چهارم", "معرفت در جامعه و در ذهن"), "V": ("پنجم", "عمل"), "": ("", "پیوست‌ها")}

# The site is built twice: in English at the root, and in Persian under fa/. LANG says which.
LANG = "en"
# The chapters that have Persian narration (guide/fa/audio/tracks.js), by number, and whether
# there are any. Persian pages of the other chapters play the English narration and say so.
FA_TRACKS = {}
FA_AUDIO = False
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def L(en, fa):
    """The English or the Persian version of a piece of text, for the language being built."""
    return fa if LANG == "fa" else en


def num(x):
    return str(x).translate(FA_DIGITS) if LANG == "fa" else str(x)


def up(n):
    """Relative path from a page n folders deep (in the English layout) back to the site root."""
    return "../" * (n + (1 if LANG == "fa" else 0))


def home(root):
    """From the site root to the home of the language being built."""
    return root + ("fa/" if LANG == "fa" else "")


def audio_dir(root, track=None):
    """Folder of a track's MP3, from the site root: the Persian narration's or the English one's."""
    return f"{root}guide/fa/audio/" if LANG == "fa" and track and track.get("fa") else f"{root}guide/audio/"


def fa_audio(native, english, partial=None):
    """Persian wording about the whole audio edition: when every chapter has Persian narration,
    when none has, and (partial, defaulting to native) while some chapters have it."""
    if len(FA_TRACKS) >= 16:
        return native
    if FA_TRACKS:
        return native if partial is None else partial
    return english


def track_bytes(t):
    """Size of a track's MP3, for the buttons that save it for offline listening."""
    path = (GUIDE / "fa" / "audio" if t.get("fa") else GUIDE / "audio") / t["file"]
    return path.stat().st_size if path.exists() else 0


def megabytes(n):
    return f"{num(max(1, round(n / 1048576)))} {L('MB', 'مگابایت')}"


def audiobook_cover():
    """A square cover for podcast and audiobook apps, cut from the middle of the audio page's artwork."""
    src, out = ART_DIR / "audio.jpg", ART_DIR / "audiobook-cover.jpg"
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return
    img = Image.open(src).convert("RGB")
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((1400, 1400), Image.LANCZOS)
    img.save(out, "JPEG", quality=82, optimize=True, progressive=True)


FEED_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


def build_feed(chapters, tracks, md):
    """The audiobook as a podcast feed (guide/audio/feed.xml), so a podcast app can subscribe to it,
    download the chapters, play them offline and keep its place. The Persian feed lists only the
    chapters narrated in Persian; new ones appear in subscribers' apps as they are published.
    Returns the feed's address, or None when there is nothing to list."""
    fa = LANG == "fa"
    items = [t for t in tracks if t.get("fa")] if fa else list(tracks)
    if not items:
        return None
    site = LIVE + ("fa/" if fa else "")
    feed = site + "guide/audio/feed.xml"
    cover = LIVE + "assets/art/audiobook-cover.jpg"
    x = lambda v: html.escape(str(v), quote=True)
    title = L(f"{SITE} (audiobook)", f"{SITE_FA} (کتاب صوتی)")
    about = L("The narrated edition of Mastering Epistemology, a free, complete guide to knowledge, evidence and critical "
              "thinking: sixteen chapters, each ending with a spoken quiz. Narrated with a synthetic voice.",
              "نسخهٔ صوتیِ «تسلط بر معرفت‌شناسی»، راهنمایی رایگان و کامل دربارهٔ معرفت، شواهد و تفکرِ نقادانه: "
              "شانزده فصل، هر کدام با آزمونکی شفاهی در پایان. روایت با صداهای ساختگی است.")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">',
           "<channel>",
           f"<title>{x(title)}</title>", f"<link>{x(site + 'guide/audio/')}</link>",
           f'<atom:link href="{x(feed)}" rel="self" type="application/rss+xml"/>',
           f"<language>{'fa' if fa else 'en'}</language>", f"<description>{x(about)}</description>",
           f"<itunes:author>{x(L(SITE, SITE_FA))}</itunes:author>", f"<itunes:summary>{x(about)}</itunes:summary>",
           f'<itunes:image href="{x(cover)}"/>',
           f"<image><url>{x(cover)}</url><title>{x(title)}</title><link>{x(site)}</link></image>",
           '<itunes:category text="Society &amp; Culture"><itunes:category text="Philosophy"/></itunes:category>',
           "<itunes:explicit>false</itunes:explicit>", "<itunes:type>serial</itunes:type>"]
    for t in items:
        n = int(t["file"][:2])
        ch = chapters[n]
        mp3 = LIVE + ("guide/fa/audio/" if t.get("fa") else "guide/audio/") + t["file"]
        text = site + "guide/" + ch.href
        blurb = html.unescape(strip_tags(md.inline(ch.blurb))) if ch.blurb else ""
        note = blurb + (" " if blurb else "") + L(f"Read the chapter: {text}", f"متنِ فصل: {text}")
        out += ["<item>", f"<title>{x(ch.label + ': ' + ch.title)}</title>", f"<itunes:title>{x(ch.title)}</itunes:title>",
                f"<itunes:episode>{n}</itunes:episode>", "<itunes:episodeType>full</itunes:episodeType>",
                f"<description>{x(note)}</description>", f"<link>{x(text)}</link>",
                f'<enclosure url="{x(mp3)}" length="{track_bytes(t)}" type="audio/mpeg"/>',
                f'<guid isPermaLink="false">epis-{"fa" if fa else "en"}-{n:02d}</guid>',
                f"<pubDate>{format_datetime(FEED_EPOCH + timedelta(hours=n))}</pubDate>",  # in chapter order
                f"<itunes:duration>{round(t['duration'])}</itunes:duration>", "</item>"]
    out += ["</channel>", "</rss>"]
    write(ROOT / ("fa" if fa else "") / "guide" / "audio" / "feed.xml", "\n".join(out) + "\n")
    return feed


def fa_voice(ch):
    """Whether this chapter's page plays Persian narration."""
    return LANG == "fa" and bool(ch.track) and bool(ch.track.get("fa"))


def ch_audio(ch, native, english):
    """Persian wording about one chapter's audio: Persian narration or English."""
    return native if fa_voice(ch) else english


def mmss(seconds):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def map_url(root, frag=""):
    """The concept map of the language being built (/map/ or /fa/map/)."""
    return f"{home(root)}map/" + (f"#{frag}" if frag else "")


def site_name():
    return L(SITE, SITE_FA)


def OUT():
    return ROOT / "fa" if LANG == "fa" else ROOT


def SRC():
    return GUIDE / "fa" if LANG == "fa" else GUIDE


def part_label(roman, name):
    if LANG == "fa":
        word, fa_name = PARTS_FA.get(roman, ("", name))
        return (f"بخش {word}" if word else "پیوست‌ها"), fa_name
    return (f"Part {roman}" if roman else "Also"), name

FA_CHAPTERS = {
    1: ("معرفت‌شناسی چیست؟", "پرسش‌های بنیادی؛ سه گونهٔ دانستن؛ باور، درجهٔ باور و پذیرش؛ معرفت پیشین، تحلیلی و ضروری؛ دلایل معرفتی در برابر دلایل عملی؛ نقشهٔ این حوزه"),
    2: ("تاریخ نظریهٔ معرفت", "از پیشاسقراطیان، سقراط، افلاطون و ارسطو تا سنت‌های هندی، اسلامی و چینی؛ و از دکارت، لاک، هیوم، رید و کانت تا عمل‌گرایی، پوپر، ویتگنشتاین، کواین و گتیه"),
    3: ("منطق و کالبدشناسی استدلال", "قیاس، استقرا و استنتاج به بهترین تبیین؛ اعتبار و استحکام؛ شرط‌های لازم و کافی؛ صورت‌های معتبر و مغالطه‌های صوری؛ مقدمه‌های پنهان؛ اصل خیرخواهی؛ نقشهٔ استدلال و مدل تولمین"),
    4: ("زبان، مفاهیم و تعریف‌ها", "معنا و مرجع؛ انواع تعریف؛ ابهام و واگی؛ نزاع‌های لفظی؛ زبان باردار و قاب‌بندی؛ مفاهیم مناقشه‌برانگیز؛ شکاف هست–باید؛ آزمون‌های فکری و تعادل تأملی"),
    5: ("معرفت چیست؟", "باور صادق موجه؛ مسئلهٔ گتیه؛ وثاقت‌گرایی، حساسیت، ایمنی، فضیلت و نظریه‌های معرفت‌نخست؛ بخت معرفتی؛ ارزش معرفت؛ فهم و خرد"),
    6: ("توجیه: ساختار دلایل خوب", "ابطال‌کننده‌ها؛ مسئلهٔ تسلسل؛ مبناگرایی، انسجام‌گرایی، تسلسل‌گرایی و رویکردهای ترکیبی؛ درون‌گرایی در برابر برون‌گرایی؛ شواهدگرایی؛ مسئلهٔ معیار و خطاپذیری"),
    7: ("منابع معرفت", "ادراک، حافظه، درون‌نگری، عقل و گواهی: هریک چگونه کار می‌کند و چگونه از کار می‌افتد؛ علم حضوری؛ چه زمانی به شهود اعتماد کنیم"),
    8: ("شکاکیت و پاسخ‌های آن", "شکاکیت پیرونی و دکارتی؛ مغز در خمره؛ استدلال بستار؛ مور، زمینه‌گرایی، معرفت‌شناسی لولایی و پاسخ‌های دیگر؛ شکاکیت سالم در برابر شکاکیت فرساینده"),
    9: ("استقرا، احتمال و استدلال بیزی", "مسئلهٔ هیوم؛ سبزآبی و کلاغ‌ها؛ احتمال؛ قضیهٔ بیز با مثال‌های حل‌شده؛ نرخ‌های پایه، مغالطهٔ عطف، مسئلهٔ مونتی‌هال، بازگشت به میانگین، پارادوکس سیمپسون؛ کالیبراسیون، مقدار p و ریسک"),
    10: ("علم، شواهد و تبیین", "ابطال‌پذیری؛ دوئم–کواین؛ کون و لاکاتوش؛ استنتاج به بهترین تبیین؛ واقع‌گرایی؛ علیت، همبستگی و آزمایش‌های تصادفی؛ ارزش‌ها در علم؛ اجماع؛ بحران تکرارپذیری و تشخیص شبه‌علم"),
    11: ("حقیقت، نسبی‌گرایی و عینیت", "نظریه‌های حقیقت؛ پارادوکس دروغ‌گو؛ نسبی‌گرایی و منتقدانش؛ ساخت اجتماعی؛ عینیت و منظر؛ پساحقیقت و چرندگویی"),
    12: ("معرفت‌شناسی اجتماعی: باهم دانستن", "اعتماد و تخصص؛ انتخاب میان کارشناسان؛ اختلاف همتایان؛ بی‌عدالتی معرفتی؛ نظریهٔ موقعیت؛ اتاق‌های پژواک، آبشارهای اطلاعاتی و خرد جمعی؛ اطلاعات نادرست، تبلیغات و نظریه‌های توطئه؛ نهادها و هوش مصنوعی"),
    13: ("فضیلت فکری و اخلاق باور", "کلیفورد در برابر جیمز؛ فضیلت‌ها و رذیلت‌های فکری؛ فروتنی و گشوده‌ذهنی؛ ملاحظات عملی و اخلاقی در اسناد معرفت؛ ایمان، عقل و معرفت‌شناسی دینی"),
    14: ("روان‌شناسی استدلال: ذهن در عمل", "نظریه‌های دوفرایندی؛ میان‌برهای ذهنی و سوگیری‌ها؛ سوگیری تأییدی و سوگیری جانب خود؛ استدلال انگیزه‌مند؛ اعتمادبه‌نفس بیش‌ازحد؛ شناخت هویت‌محافظ؛ نظریهٔ استدلالی؛ روش‌های مؤثر سوگیری‌زدایی و اَبَرپیش‌بینی"),
    15: ("راهنمای میدانی مغالطه‌ها", "بیش از چهل مغالطه و فن بلاغی؛ برای هریک مثال، خویشاوند مشروع، روش پاسخ‌گویی و تمرین‌های کاربردی"),
    16: ("جعبه‌ابزار متفکر نقاد", "روشی هفت‌مرحله‌ای برای تحلیل هر گفت‌وگو؛ نظریهٔ موضع‌ها؛ یافتن نقطهٔ گرهی؛ صورت‌بندی استدلال‌های خود؛ بار اثبات؛ تیغ‌های فلسفی؛ اخلاق گفت‌وگو؛ پنج مطالعهٔ موردی و فهرست‌های وارسی"),
    17: ("واژه‌نامه", "۲۰۰ اصطلاح کلیدی، هریک پیوندخورده به توضیح کامل خود"),
    18: ("فهرست مطالعه و برنامهٔ یادگیری", "بهترین کتاب‌ها به تفکیک سطح؛ متون دست‌اول؛ سنت‌های غیرغربی؛ منابع رایگان و یک برنامهٔ مطالعهٔ دوازده‌هفته‌ای"),
}

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
        "chev": '<path d="m15 18-6-6 6-6"/>',
        "plus": '<path d="M12 5v14M5 12h14"/>',
        "minus": '<path d="M5 12h14"/>',
        "fit": '<path d="M9 4H4v5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>',
        "close": '<path d="m6 6 12 12M18 6 6 18"/>',
        "toc": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1.1"/><circle cx="4.5" cy="12" r="1.1"/><circle cx="4.5" cy="18" r="1.1"/>',
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
        "rss": '<path d="M5 5a14 14 0 0 1 14 14M5 11a8 8 0 0 1 8 8"/><circle cx="6" cy="18" r="1.4"/>',
        "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
        "save": '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
        "pen": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
        "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
        "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
        "chat": '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>',
        "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
        "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
        "review": '<path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.6"/><path d="M4 4v4.6h4.6"/><path d="M12 8v4l3 2"/>',
    }
    if name in ("arrow", "back") and cls == "icon":
        cls = "icon flip"  # arrows point the other way in right-to-left pages
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
        'if(d.lang==="fa"||(g("epistemology-lang")==="fa"&&d.getAttribute("data-bilingual")!==null))d.setAttribute("data-lang","fa");'
        'try{var r=JSON.parse(g("epis-reader")||"{}");if(r.scale)d.style.setProperty("--read-scale",r.scale);'
        'var L=r.lead;if(typeof L==="number")L=L<1.7?"compact":L>1.8?"airy":"";if(L&&L!=="normal")d.setAttribute("data-lead",L);'
        'if(r.width)d.setAttribute("data-width",r.width);'
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
    if LANG == "fa":
        return f"{num(m // 60)} ساعت و {num(m % 60)} دقیقه" if m >= 60 else f"{num(m)} دقیقه"
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

    DOT = 160  # px, the square crop shown in the map's medallions: the chapters' paintings and, at the centre, the map's own
    DOT_KEYS = {f"ch{n:02d}" for n in range(1, 17)} | {"map"}
    DOT_SIDE = {"map": 0.36}  # share of the shorter side kept; the map's own plate shows just its sun

    def derive_dots(self):
        for key, spec in self.info.items():
            if key not in self.DOT_KEYS:
                continue
            src, out = ART_DIR / f"{key}-640.jpg", ART_DIR / f"{key}-dot.jpg"
            if not src.exists() or (out.exists() and out.stat().st_mtime >= src.stat().st_mtime):
                continue
            img = Image.open(src).convert("RGB")
            fx, fy = (float(v.rstrip("%")) / 100 for v in spec.get("focus", "50% 50%").split())
            side = round(min(img.size) * self.DOT_SIDE.get(key, 0.8))
            cx, cy = fx * img.width, fy * img.height
            left = min(max(0, round(cx - side / 2)), img.width - side)
            top = min(max(0, round(cy - side / 2)), img.height - side)
            img.crop((left, top, left + side, top + side)).resize((self.DOT, self.DOT), Image.LANCZOS) \
                .save(out, "JPEG", quality=80, optimize=True, progressive=True)

    def color(self, key):
        return self.credits.get(key, {}).get("color", "#2a2f33")

    def focus(self, key):
        return self.info.get(key, {}).get("focus", "50% 50%")

    def src(self, key, root, w=1200):
        return f"{root}assets/art/{key}-{w}.jpg"

    def srcset(self, key, root):
        return ", ".join(f"{root}assets/art/{key}-{w}.jpg {w}w" for w in self.SIZES)

    def meta(self, key):
        i = self.info.get(key, {})
        return i.get("fa", i) if LANG == "fa" else i

    def caption(self, key, italic=True):
        i = self.meta(key)
        if LANG == "fa":
            bits = [esc(i.get("artist", "")), f"«{esc(i.get('title', ''))}»", esc(i.get("date", ""))]
            return "، ".join(b for b in bits if b and b != "«»")
        title = f"<i>{esc(i.get('title', ''))}</i>" if italic else esc(i.get("title", ""))
        bits = [esc(i.get("artist", "")), title, esc(i.get("date", ""))]
        return ", ".join(b for b in bits if b)

    def alt(self, key):
        i = self.meta(key)
        if LANG == "fa":
            return f"«{i.get('title', '')}» اثر {i.get('artist', '')} ({i.get('date', '')})"
        return f"{i.get('title', '')} by {i.get('artist', '')} ({i.get('date', '')})"

    def img(self, key, root, sizes="100vw", cls="art", eager=False, alt=None):
        return (f'<img class="{cls}" src="{self.src(key, root)}" srcset="{self.srcset(key, root)}" sizes="{sizes}" '
                f'alt="{attr(self.alt(key) if alt is None else alt)}"' + (' fetchpriority="high"' if eager else ' loading="lazy"') +
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
            return map_url(up(1), frag[1:])
        if path == "../README.md":
            return REPO + "#readme"
        m = re.match(r"^(\d\d-[\w-]+)\.md$", path)
        if m:
            return m.group(1) + ".html" + frag
        return href
    return rewrite


def render_mermaid(md, prune=True):
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
    for old in DIAGRAMS.glob("*.svg") if prune else []:
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

_ASSET_V = {}
def av(root, name):
    """An asset URL with a short content hash, so browsers fetch a stylesheet or script again as soon as it changes."""
    if name not in _ASSET_V:
        _ASSET_V[name] = hashlib.sha1((ASSETS / name).read_bytes()).hexdigest()[:10]
    return f"{root}assets/{name}?v={_ASSET_V[name]}"


MENU_CHAPTERS = {}  # the chapters of the language being built, for the chapter menu on pages that are not chapters


def chapter_menu(root):
    """The chapter menu for any page that is not itself a chapter: every chapter, and the contents page."""
    if not MENU_CHAPTERS:
        return ""
    g = f"{home(root)}guide/"
    items = "".join(f'<li><a href="{g}{c.href}"><small>{c.label}</small><span>{esc(c.title)}</span></a></li>' for _, c in sorted(MENU_CHAPTERS.items()))
    return (f'<nav class="chsw" aria-label="{L("Chapters", "فصل‌ها")}"><details class="chsw-pick"><summary class="tbtn" '
            f'title="{L("Chapters", "فصل‌ها")}" aria-label="{L("Chapters", "فصل‌ها")}">{icon("toc")}</summary>'
            f'<div class="chsw-panel"><ol>{items}</ol><a class="all" href="{g}">{L("The guide’s contents →", "فهرستِ راهنما ←")}</a></div></details></nav>')


def shell(*, root, title, desc, body, current="", hero_img=None, extra_head="", bar="solid", reader=False, focus=False,
          alt=None, bilingual=False, chapter_nav="", extra_scripts=""):
    h = home(root)
    chapter_nav = chapter_nav or chapter_menu(root)
    nav = [("guide", f"{h}guide/", "book", L("Guide", "راهنما")), ("concepts", f"{h}concepts/", "grid", L("Concepts", "مفاهیم")),
           ("map", map_url(root), "map", L("Map", "نقشه")), ("audio", f"{h}guide/audio/", "phones", L("Listen", "شنیدن"))]
    here = ' aria-current="page"'
    links = "".join(f'<a href="{href}"{here if key == current else ""} title="{label}">{icon(ic)}<span>{label}</span></a>'
                    for key, href, ic, label in nav)
    preload = (f'<link rel="preload" as="image" href="{hero_img[0]}" imagesrcset="{hero_img[1]}" imagesizes="100vw">'
               if hero_img else "")
    full_title = title if title == site_name() else f"{title} · {site_name()}"
    # the user menu: account, notebook, review, download, reading settings and theme
    cur = lambda key: here if key == current else ""
    reader_item = (f'<button id="reader" type="button" aria-expanded="false" aria-controls="rpanel" title="{L("Reading settings (A)", "تنظیمات خواندن (A)")}">'
                   f'<i class="aa" aria-hidden="true">Aa</i><span>{L("Reading settings", "تنظیمات خواندن")}</span></button>') if reader else ""
    user_menu = (f'<div class="umenu-wrap"><button class="tbtn" id="ubtn" type="button" aria-expanded="false" aria-controls="umenu" '
                 f'aria-label="{L("Your study, downloads and settings", "مطالعهٔ شما، دریافت و تنظیمات")}" title="{L("Your study and settings", "مطالعه و تنظیمات")}">{icon("user")}</button>'
                 f'<div class="umenu" id="umenu" hidden>'
                 f'<a href="{h}account/"{cur("account")}>{icon("user")}<span>{L("My study", "مطالعهٔ من")}</span></a>'
                 f'<a href="{h}reading-path/">{icon("map")}<span>{L("My reading path", "مسیر مطالعهٔ من")}</span></a>'
                 f'<a href="{h}notes/">{icon("pen")}<span>{L("Notebook", "دفترچه")}</span></a>'
                 f'<a href="{h}review/">{icon("review")}<span>{L("Review questions", "مرور پرسش‌ها")}</span></a>'
                 f'<a href="{h}guide/download.html"{cur("download")}>{icon("download")}<span>{L("Download", "دریافت")}</span></a>'
                 f'<span class="sep"></span>{reader_item}'
                 f'<button id="theme" type="button"><i class="ico" aria-hidden="true"></i><span class="tl">{L("Theme", "پوسته")}</span></button></div></div>')
    ask_btn = (f'<button class="tbtn" id="ask" type="button" aria-expanded="false" aria-label="{L("Ask the study companion", "پرسش از همراهِ مطالعه")}" '
               f'title="{L("Ask about this page (I)", "دربارهٔ این صفحه بپرسید (I)")}">{icon("chat")}</button>') if reader else ""
    focus_btn = (f'<button class="tbtn" id="focus" type="button" aria-pressed="false" aria-label="{L("Focus mode", "حالت تمرکز")}" '
                 f'title="{L("Focus mode (F)", "حالت تمرکز (F)")}">{icon("focus")}</button>') if focus else ""
    lang_btn = (f'<a class="tbtn lang" id="lang" href="{alt}" hreflang="{L("fa", "en")}" lang="{L("fa", "en")}" '
                f'data-set-site-lang="{L("fa", "en")}" title="{L("فارسی", "English")}">{L("فا", "EN")}</a>') if alt else ""
    alt_link = f'<link rel="alternate" hreflang="{L("fa", "en")}" href="{alt}">' if alt else ""
    attrs = ' lang="fa" dir="rtl" data-lang="fa"' if LANG == "fa" else ' lang="en"'
    return f"""<!doctype html>
<html{attrs} data-theme="light"{" data-bilingual" if bilingual else ""}>
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
{alt_link}
<link rel="stylesheet" href="{av(root, "fonts/fonts.css")}">
<link rel="stylesheet" href="{av(root, "site.css")}">
{preload}{extra_head}
<script>{BOOT}</script>
</head>
<body>
<a class="skip" href="#main">{L("Skip to content", "رفتن به متن")}</a>
<header class="bar {bar}{" has-chsw" if chapter_nav else ""}">
  <a class="brand" href="{h}" aria-label="{site_name()}, {L("home", "صفحهٔ نخست")}">{LOGO}<span><b>{site_name()}</b><small>{L("Guide · Map · Audio", "راهنما · نقشه · صوت")}</small></span></a>{chapter_nav}
  <nav class="site-nav" aria-label="{L("Site", "سایت")}">{links}</nav>
  <button class="tbtn" id="search" type="button" aria-label="{L("Search the guide", "جست‌وجو در راهنما")}" title="{L("Search (/)", "جست‌وجو (/)")}">{icon("search")}</button>{ask_btn}{focus_btn}{lang_btn}{user_menu}
  <button class="tbtn" id="menu" type="button" aria-label="{L("Menu", "فهرست")}" aria-expanded="false" aria-controls="mnav">{icon("menu")}</button>
</header>
<nav class="mnav" id="mnav" aria-label="{L("Menu", "فهرست")}" hidden>{links}
  {f'<span class="sep"></span>' if alt else ""}{f'<a href="{alt}" data-set-site-lang="{L("fa", "en")}" lang="{L("fa", "en")}">{icon("globe")}<span>{L("فارسی", "English")}</span></a>' if alt else ""}</nav>
{body}
{footer(root)}
<script src="{av(root, "site.js")}" defer></script>
<script src="{av(root, "notes.js")}" defer></script>
<script src="{av(root, "learn.js")}" defer></script>
<script src="{av(root, "ai-config.js")}" defer></script>
<script src="{av(root, "account.js")}" defer></script>
<script src="{av(root, "ai.js")}" defer></script>
{extra_scripts}
</body>
</html>
"""


def footer(root):
    h = home(root)
    epub = f"{h}guide/{EPUB_NAME_FA if LANG == 'fa' else EPUB_NAME}"
    return f"""<footer class="foot">
  <div class="wrap">
    <div>
      <a class="brand" href="{h}">{LOGO}<span><b>{site_name()}</b></span></a>
      <p>{L("A complete guide to knowledge, evidence, and critical thinking, with a bilingual concept map and a narrated audio edition.",
            "راهنمایی کامل دربارهٔ معرفت، شواهد و تفکر نقادانه، با نقشهٔ دوزبانهٔ مفاهیم و نسخهٔ صوتی.")}</p>
      <p>{L(f'Artwork: public domain, via Wikimedia Commons (<a href="{h}credits.html">credits</a>). The narration uses a synthetic voice.',
            f'آثار هنری: مالکیت عمومی، از ویکی‌انبار (<a href="{h}credits.html">منابع</a>). روایت صوتی با صدای ساختگی و به زبان {fa_audio("فارسی", "انگلیسی", "فارسی است؛ فصل‌هایی که صدای فارسی‌شان هنوز آماده نیست به انگلیسی روایت می‌شوند")}{fa_audio(" است", " است", "")}.')}</p>
    </div>
    <div><h3>{L("Read", "خواندن")}</h3><ul>
      <li><a href="{h}guide/">{L("Contents", "فهرست مطالب")}</a></li>
      <li><a href="{h}guide/01-what-is-epistemology.html">{L("Start with chapter 1", "آغاز از فصل ۱")}</a></li>
      <li><a href="{h}guide/17-glossary.html">{L("Glossary", "واژه‌نامه")}</a></li>
      <li><a href="{h}guide/18-reading-list.html">{L("Reading list and study plan", "فهرست مطالعه و برنامهٔ درسی")}</a></li>
      <li><a href="{epub}" download>{L("EPUB for e-readers", "نسخهٔ EPUB برای کتاب‌خوان")}</a></li></ul></div>
    <div><h3>{L("Explore", "کاوش")}</h3><ul>
      <li><a href="{map_url(root)}">{L("Concept map", "نقشهٔ مفاهیم")}</a></li>
      <li><a href="{h}concepts/">{L("All 135 concepts", "همهٔ ۱۳۵ مفهوم")}</a></li>
      <li><a href="{h}guide/audio/">{L("Audio edition", fa_audio("نسخهٔ صوتی", "نسخهٔ صوتی (انگلیسی)"))}</a></li>
      <li><a href="{h}account/">{L("My study (sign in)", "مطالعهٔ من (ورود)")}</a></li>
      <li><a href="{h}notes/">{L("Your notebook", "دفترچهٔ شما")}</a></li>
      <li><a href="{h}review/">{L("Review questions", "مرور پرسش‌ها")}</a></li>
      <li><a href="{REPO}">{L("Source on GitHub", "کد منبع در گیت‌هاب")}</a></li></ul></div>
  </div>
  <div class="wrap legal"><a href="{h}privacy.html">{L("Privacy policy", "سیاستِ حریم خصوصی")}</a><span aria-hidden="true">·</span><a href="{h}terms.html">{L("Terms of service", "شرایطِ استفاده")}</a><span aria-hidden="true">·</span><a href="{h}credits.html">{L("Credits", "منابع")}</a></div>
</footer>"""


def hero(art, key, root, *, kicker, title, cls="", dek=None, cite=None, lede=None, facts=None, actions=None, extra="",
         title_html=None, image_alt=None, plate_html=None):
    parts = [f'<div class="kicker">{kicker}</div>' if kicker else "",
             title_html or f"<h1>{title}</h1>",
             f'<p class="dek">{dek}</p>' if dek else "",
             f'<div class="dek-cite">— {cite}</div>' if cite else "",
             f'<p class="lede">{lede}</p>' if lede else "",
             extra,
             ('<div class="facts">' + "".join(f"<span>{f}</span>" for f in facts) + "</div>") if facts else "",
             ('<div class="actions">' + actions + "</div>") if actions else ""]
    plate = f'<div class="plate">{plate_html if plate_html is not None else art.caption(key)}</div>' if art.has(key) else ""
    image = f'<div class="hero-art">{art.img(key, root, eager=True, alt=image_alt)}</div>' if art.has(key) else ""
    return (f'<header class="hero {cls}" style="--art:{art.color(key)};--focus:{art.focus(key)}">{image}'
            f'<div class="hero-in">{"".join(parts)}{plate}</div></header>')


def label(art, key):
    i = art.meta(key)
    if not i.get("note"):
        return ""
    sep = L(", ", "، ")
    place = f"{sep}{esc(i['place'])}" if i.get("place") else ""
    source = art.credits.get(key, {}).get("source")
    source_label = L("View artwork source and full-resolution image (opens in a new tab)",
                     "مشاهدهٔ منبع تصویر و نسخهٔ باکیفیت (در زبانهٔ جدید)")
    source_link = (f' <a class="art-source" href="{attr(source)}" target="_blank" rel="noopener noreferrer" '
                   f'aria-label="{attr(source_label)}" title="{attr(source_label)}">'
                   f'{icon("ext")}</a>') if source else ""
    return (f'<div class="art-label"><span class="kicker">{L("On the cover", "روی جلد")}</span>'
            f'<p><cite>{art.caption(key)}{place}.</cite> {esc(i["note"])}{source_link}</p></div>')


def tile(art, key, root, href, kicker, title, sub="", cls="tile", image_alt=None):
    return (f'<a class="{cls}" href="{href}" style="background:{art.color(key)}">'
            f'{art.img(key, root, sizes="(max-width:700px) 100vw, 50vw", cls="", alt=image_alt)}'
            f'<span class="kicker">{kicker}</span><b>{title}</b>{f"<span class=sub>{sub}</span>" if sub else ""}</a>')


# ----------------------------------------------------------------------------- guide

class Chapter:
    def __init__(self, path, fallback=False):
        self.path = path
        self.num = int(path.name[:2])
        self.slug = path.stem
        self.text = path.read_text(encoding="utf-8")
        self.fallback = fallback  # a Persian page showing the English text until the translation exists
        self.lang = "en" if fallback else LANG
        first = self.text.split("\n", 1)[0].lstrip("# ").strip()
        m = re.match(r"(?:Chapter|فصل)\s*[\d۰-۹]+[.:]\s+(.*)", first)
        self.title = m.group(1) if m else first
        if fallback and self.num in FA_CHAPTERS:
            self.title = FA_CHAPTERS[self.num][0]  # the Persian title, even before the chapter is translated
        self.art = f"ch{self.num:02d}"
        self.href = f"{self.slug}.html"
        if self.lang == "fa":
            self.minutes = max(1, round(len(re.findall(r"\w+", self.text)) / 200))
        else:
            self.minutes = max(1, round(words(self.text) / 230))
        self.blurb = ""
        self.track = None

    @property
    def label(self):
        return (f"فصل {num(self.num)}" if self.num <= 16 else "پیوست") if LANG == "fa" else (f"Chapter {self.num}" if self.num <= 16 else "Appendix")


def read_blurbs(chapters):
    readme = (SRC() / "README.md").read_text(encoding="utf-8")
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
                     and not l.startswith(("**Audio:**", "**صوت:**"))
                     and l.strip() != "---")
    text = re.sub(r"\n## (?:In this (?:chapter|appendix)|در این (?:فصل|پیوست))\n.*?(?=\n## )", "\n", text, flags=re.S)
    return text


def match_audio(ch, heads):
    """Map h2 headings to the start times of the matching narration sections."""
    if not ch.track:
        return {}
    secs = ch.track["sections"][1:]
    if secs and secs[-1]["title"].startswith(("End of chapter", "پایانِ فصلِ")):
        secs = secs[:-1]
    h2 = [h for h in heads if h[0] == 2 and h[2] not in ("Further reading", "برای مطالعهٔ بیشتر")]
    if len(h2) != len(secs):
        print(f"  note: {ch.slug}: {len(h2)} sections in text, {len(secs)} in audio; matching by title")
        out = {}
        norm = lambda s: re.sub(r"[^a-z\u0600-\u06FF]", "", s.lower())
        for level, slug, plain, _ in h2:
            for s in secs:
                if norm(s["title"])[:18] == norm(plain)[:18]:
                    out[slug] = s["start"]
        return out
    return {h[1]: s["start"] for h, s in zip(h2, secs)}


EN_HEADS = {}  # chapter number -> headings of the English text, so Persian pages can reuse its section ids


def build_chapter(ch, chapters, md, art, svgs_later, C):
    root = up(1)
    text, epigraphs = split_epigraphs(ch.text)
    body_md = clean_chapter_markdown(text)
    body, heads = md.render(body_md, guide_links())
    if LANG == "fa" and not ch.fallback and ch.num in EN_HEADS and ch.num != 17:  # the glossary has its own letters
        # Persian headings get the English section ids, so links, audio markers and highlights line up.
        en = EN_HEADS[ch.num]
        if [h[0] for h in heads] != [h[0] for h in en]:
            print(f"  note: fa/{ch.slug}: heading structure differs from the English ({len(heads)} vs {len(en)})")
        mapped = []
        for i, h in enumerate(heads):
            if i < len(en) and en[i][0] == h[0]:
                body = body.replace(f'<h{h[0]} id="{h[1]}">', f'<h{h[0]} id="\x00{en[i][1]}">', 1)
                mapped.append((h[0], en[i][1], h[2], h[3]))
            else:
                mapped.append(h)
        body = body.replace('id="\x00', 'id="')
        heads = mapped
    if LANG == "en":
        EN_HEADS[ch.num] = heads
    elif not ch.fallback:
        for h in heads:
            FA_HEADS[(ch.num, h[1])] = h[2]
    body = polish(body)
    if fa_voice(ch):
        at = match_audio(ch, heads)  # the Persian narration follows the Persian headings
    else:
        at = match_audio(EN_CHAPTERS.get(ch.num, ch), EN_HEADS.get(ch.num, heads))

    def h2(m):
        slug, inner = m.group(1), m.group(2)
        hear = ""
        if slug in at:
            hear = (f'<button class="hear" type="button" data-at="{at[slug]}" title="{L("Listen from this section", ch_audio(ch, "شنیدن از این بخش", "شنیدن از این بخش (انگلیسی)"))}">'
                    f'{icon("phones")}<span>{L("Listen", "شنیدن")}</span></button>')
        return f'<h2 id="{slug}"><span class="ht">{inner}</span>{hear}</h2>'
    body = re.sub(r'<h2 id="([^"]+)">(.*?)</h2>', h2, body)
    if ch.num == 17:
        body = re.sub(r'<h2 id="([^"]{1,3})"><span class="ht">([^<]{1,3})</span></h2>', r'<h2 id="\1" class="glossary-letter">\2</h2>', body)
    body = re.sub(r"^<p>", '<p class="lede">', body, count=1)
    if ch.num <= 16:
        body = link_terms(body)
    else:
        def gterm(m):
            key = html.unescape(strip_tags(m.group(1)))
            gid = LEARN["glossary_ids"].get(key)
            return f'<p id="{gid}" class="gterm"><strong>{m.group(1)}.</strong>' if gid else m.group(0)
        body = re.sub(r"<p><strong>(.+?)\.</strong>", gterm, body)
    collect_sections(ch, body)
    body = deeper_links(ch, body)

    more_quotes = "".join(
        f'<blockquote class="quote"><p>{md.inline(q)}</p><span class="by">— {md.inline(c)}</span></blockquote>'
        for q, c in epigraphs[1:])
    toc_items = [(slug, inner) for level, slug, plain, inner in heads if level == 2]
    toc = "".join(f'<li><a href="#{slug}">{re.sub(r"<[^>]+>", "", inner)}</a></li>' for slug, inner in toc_items)
    roman, part = PART_OF.get(ch.num, ("", ""))
    if roman:
        pl, pn = part_label(roman, part)
        kicker = f"{pl} · {pn} · {ch.label}"
    else:
        kicker = L("Appendix", "پیوست")
    facts = [f"{icon('clock')} {num(ch.minutes)} {L('min read', 'دقیقه مطالعه')}"]
    listen_card, actions = "", f'<a class="btn primary" href="#main">{L("Start reading", "شروع خواندن")} {icon("arrow")}</a>'
    if ch.track:
        titles = {}
        if LANG == "fa" and not fa_voice(ch):
            by_time = {t: s for s, t in at.items()}
            fa_title = {slug: re.sub(r"<[^>]+>", "", inner) for level, slug, plain, inner in heads if level == 2}
            titles = {t: fa_title.get(s, "") for t, s in by_time.items()}
        def sec_title(i, s):
            if i == 0:
                return L("Opening", "آغاز")
            if LANG == "fa" and not fa_voice(ch):
                return titles.get(s["start"]) or ("پایان و آزمونک" if s["title"].startswith("End of chapter") else s["title"])
            return s["title"]
        sections = [{"t": sec_title(i, s), "s": s["start"]} for i, s in enumerate(ch.track["sections"])]
        secs = "".join(f'<li><button type="button" data-at="{s["s"]}"><span>{esc(s["t"])}</span><small>{num(mmss(s["s"]))}</small></button></li>'
                       for s in sections)
        readalong_attrs = (f'data-readalong="listen/{ch.slug}.html" data-epub="epub/{ch.slug}/files.json" '
                           if chapter_sync(ch) else "")
        # one slim row: play, what it is, and a small menu (save, download, read along, EPUB, the sections)
        listen_card = (f'<section class="listen" data-audio="{audio_dir(root, ch.track)}{ch.track["file"]}" data-size="{track_bytes(ch.track)}" {readalong_attrs}data-thumb="{art.src(ch.art, root, 640)}" '
                       f'data-title="{attr(ch.label + ": " + ch.title)}" data-sections="{attr(json.dumps(sections, ensure_ascii=False))}" '
                       f'aria-label="{L("Listen to this chapter", "شنیدن این فصل")}">'
                       f'<button class="play" type="button" aria-label="{L("Play the narrated chapter", "پخش روایت صوتی فصل")}">{icon("play", "icon i-play")}'
                       f'<svg class="icon i-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" stroke="none"/></svg></button>'
                       f'<div class="lt"><b>{L("Listen to this chapter", "شنیدنِ این فصل")}</b>'
                       f'<span>{minutes_label(ch.track["duration"])} · {L("narrated", ch_audio(ch, "روایت‌شده", "روایت به انگلیسی"))}<span class="resume"></span></span></div>'
                       f'<button class="more" type="button" aria-expanded="false" aria-haspopup="true" '
                       f'aria-label="{L("Sections, download and more", "بخش‌ها، دریافت و بیشتر")}" title="{L("Sections, download and more", "بخش‌ها، دریافت و بیشتر")}">'
                       f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none"/>'
                       f'<circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none"/></svg></button>'
                       f'<div class="lmenu" hidden><div class="lacts"></div>'
                       f'<p class="kicker">{L("Sections", "بخش‌ها")}</p><ol class="lsecs">{secs}</ol></div></section>')
        actions += listen_card
    dek = cite = None
    if epigraphs:
        dek, cite = md.inline(epigraphs[0][0]), md.inline(epigraphs[0][1])
        if ch.fallback:
            dek, cite = f'<span dir="ltr" lang="en">{dek}</span>', f'<span dir="ltr" lang="en">{cite}</span>'
    head = hero(art, ch.art, root, kicker=kicker, title=title_html(ch), dek=dek, cite=cite, facts=facts, actions=actions,
                cls="with-listen" if ch.track else "")

    listen_link = (f'<button type="button" data-listen>{icon("phones")} {L("Listen", "شنیدن")}</button>' if ch.track else "")
    focus_head = (f'<div class="focus-head"><span class="kicker">{kicker}</span><div class="ftitle" role="heading" aria-level="1">{title_html(ch)}</div>'
                  f'<div class="fmeta"><span>{num(ch.minutes)} {L("min read", "دقیقه مطالعه")}</span>{listen_link}'
                  f'<button type="button" data-focus-toggle>{L("Leave focus mode", "خروج از حالت تمرکز")}</button></div></div>')
    prev_ch, next_ch = chapters.get(ch.num - 1), chapters.get(ch.num + 1)
    # in the site bar, beside the site name: the chapter before, every chapter, the chapter after
    here_ = ' aria-current="page"'
    all_chs = "".join(f'<li><a href="{c.href}"{here_ if c.num == ch.num else ""}><small>{c.label}</small><span>{esc(c.title)}</span></a></li>'
                      for _, c in sorted(chapters.items()))
    steps_row = ((f'<a href="{prev_ch.href}" rel="prev"><small>{L("← Previous", "→ قبلی")}</small><span>{esc(prev_ch.title)}</span></a>' if prev_ch else "<span></span>")
                 + (f'<a class="next" href="{next_ch.href}" rel="next"><small>{L("Next →", "بعدی ←")}</small><span>{esc(next_ch.title)}</span></a>' if next_ch else "<span></span>"))
    chsw = (f'<nav class="chsw" aria-label="{L("Chapters", "فصل‌ها")}">'
            + f'<details class="chsw-pick"><summary class="tbtn" title="{L("Chapters", "فصل‌ها")}" '
              f'aria-label="{L("Chapters", "فصل‌ها")} ({attr(ch.label)}: {attr(ch.title)})">{icon("toc")}</summary>'
              f'<div class="chsw-panel"><div class="chsw-steps">{steps_row}</div><ol>{all_chs}</ol>'
              f'<a class="all" href="./">{L("The guide’s contents →", "فهرستِ راهنما ←")}</a></div></details></nav>')
    prev_w, next_w = L("← Previous", "→ قبلی"), L("Next", "بعدی")
    pager = f'<nav class="pager" aria-label="{L("Chapters", "فصل‌ها")}">'
    pager += (tile(art, prev_ch.art, root, prev_ch.href, f"{prev_w} · {prev_ch.label}", esc(prev_ch.title)) if prev_ch
              else tile(art, "guide", root, "./", L("← Contents", "→ فهرست"), L("The guide", "راهنما")))
    pager += (tile(art, next_ch.art, root, next_ch.href, f"{next_w} · {next_ch.label} {L('→', '←')}", esc(next_ch.title), cls="tile next") if next_ch
              else tile(art, "home", root, "../", L("Home →", "صفحهٔ نخست ←"), site_name(), cls="tile next"))
    pager += "</nav>"
    notice = ""
    prose_attrs = ""
    if ch.fallback:
        notice = ('<div class="fa-pending" dir="rtl" lang="fa"><b>ترجمهٔ این فصل در راه است.</b> '
                  'تا آماده شود، متن انگلیسی را می‌بینید. بقیهٔ سایت به فارسی است.</div>')
        prose_attrs = ' dir="ltr" lang="en"'
    in_ch = L("In this chapter", "در این فصل")
    page = (f"{head}{label(art, ch.art)}"
            f'<main id="main" class="page"><aside class="side"><nav class="toc" aria-label="{in_ch}">'
            f'<span class="kicker">{in_ch}</span><ol{prose_attrs}>{toc}</ol></nav></aside>'
            f'<article data-slug="{ch.slug}" data-read-min="{ch.minutes}">{focus_head}{notice}<details class="mini-toc"><summary>{in_ch}</summary><ol{prose_attrs}>{toc}</ol></details>'
            f'<div class="prose"{prose_attrs}>{more_quotes}{body}</div>{deeper_box(ch, C, root) if ch.num <= 16 else ""}</article></main>{pager}')
    desc = ch.blurb.replace("*", "") or f"{ch.label}: {ch.title}"
    svgs_later.append((OUT() / "guide" / ch.href, page, root, ch, desc, chsw))


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


# Where the guide teaches each concept whose title is not one of its headings: (chapter, heading id), or
# (chapter, None) for a branch entry that a whole chapter is about.
CONCEPT_HOME = {
    "know": (5, None), "truth": (11, None), "sources": (7, None), "skep": (8, None), "formal": (9, None),
    "phsci": (10, None), "social": (12, None), "natur": (14, None), "logic": (3, None),
    "trilemma": (6, "agrippas-trilemma"), "virtue": (13, "virtue-epistemology"),
    "relig": (13, "faith-reason-and-religious-epistemology"),
    "jtb": (5, "the-tripartite-analysis"), "kinds": (1, "three-kinds-of-knowing"), "just": (6, "what-justification-is"),
    "intext": (6, "internalism-and-externalism"), "deont": (6, "deontology-and-doxastic-voluntarism"),
    "basicality": (6, "foundationalism"), "reliab": (6, "reliabilism-about-justification"),
    "prag": (11, "pragmatist-theories"), "defl": (11, "deflationism"), "object": (11, "perspectivism-and-objectivity"),
    "ratemp": (7, "rationalism-and-empiricism-about-the-a-priori"), "ansyn": (1, "analytic-and-synthetic"),
    "synapr": (1, "putting-the-three-distinctions-together"), "reid": (7, "anti-reductionism"),
    "closure": (8, "the-closure-argument"), "moore": (8, "mooreanism"),
    "cred": (9, "full-belief-and-degrees-of-belief"), "dutch": (9, "credences-and-coherence"),
    "probint": (9, "what-is-probability"), "lottery": (9, "full-belief-and-degrees-of-belief"),
    "preface": (9, "full-belief-and-degrees-of-belief"), "raven": (9, "the-paradox-of-the-ravens"),
    "pval": (9, "p-values"), "forking": (9, "multiple-comparisons-and-p-hacking"),
    "popper": (10, "popper-and-falsificationism"), "risky": (10, "popper-and-falsificationism"),
    "corrob": (10, "popper-and-falsificationism"), "adhoc": (10, "ad-hoc-hypotheses"),
    "duhem": (10, "the-duhem-quine-problem"), "normal": (10, "kuhn-and-paradigms"), "incomm": (10, "kuhn-and-paradigms"),
    "expl": (10, "inference-to-the-best-explanation"), "realism": (10, "scientific-realism-and-anti-realism"),
    "miracle": (10, "scientific-realism-and-anti-realism"), "pmi": (10, "scientific-realism-and-anti-realism"),
    "constemp": (10, "scientific-realism-and-anti-realism"), "ladder": (10, "counterfactuals-and-interventions"),
    "confound": (10, "correlation-and-causation"), "collider": (10, "correlation-and-causation"),
    "pubbias": (10, "the-replication-crisis"),
    "expert": (12, "the-novice-expert-problem"), "aumann": (12, "peer-disagreement"),
    "echo": (12, "echo-chambers-and-epistemic-bubbles"), "condorcet": (12, "the-wisdom-of-crowds"),
    "bs": (11, "frankfurt-on-bullshit"), "moral": (7, "moral-knowledge"),
    "ivice": (13, "intellectual-vices"), "evidfid": (13, "the-evidentialist-challenge"),
    "properly": (13, "reformed-epistemology"), "flew": (13, "falsification-and-religious-language"),
    "fideism": (13, "fideism"), "blind": (14, "other-well-documented-biases"), "scout": (14, "the-scout-mindset"),
    "valid": (3, "validity-and-soundness"), "modus": (3, "valid-argument-forms"), "affirm": (3, "formal-fallacies"),
    "steel": (3, "the-principle-of-charity"),
}


def concept_home(C, cid, idx):
    """The chapter and heading that teach a concept, as (chapter, heading id, heading); the heading id is None when
    the whole chapter is about it, and the result is None for the root."""
    if cid == "root":
        return None
    if cid in CONCEPT_HOME:
        n, slug = CONCEPT_HOME[cid]
        return (n, slug, next((p for m, s, p in idx if m == n and s == slug), "")) if slug else (n, None, "")
    sec = best_section(C.title(cid), BRANCH_CHAPTER.get(C.branch(cid), 1), idx)
    return sec or (BRANCH_CHAPTER.get(C.branch(cid), 1), None, "")


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


MAP_UI = {
    "en": {"kmap": "The map of the guide", "chapter": "Chapter {n}", "sec": "Section {i} of {n}", "concept": "Concept entry",
           "path": "Learning path", "read": "Read the chapter", "readsec": "Read this section", "entry": "Read the full entry",
           "listen": "Listen · {n} min", "deeper": "Deeper study", "practise": "Practise its questions",
           "sections": "Sections", "connected": "Most connected chapters", "linksn": "{n} links",
           "entries": "Concept entries", "terms": "Terms explained here", "out": "Points to", "in": "Referred to from",
           "where": "Where the guide explains it", "related": "Related concepts", "same": "Also in this section",
           "parts": "Five parts", "paths": "Ways through the guide", "onpaths": "On these learning paths",
           "steps": "{n} chapters", "start": "Start reading", "closepath": "Leave the path", "read_p": "You have read {n}%",
           "stopped": "You stopped at", "continue": "Continue reading", "prev": "Previous", "next": "Next",
           "showsec": "Show the section on the map", "find": "Search the map…", "none": "Nothing matches.",
           "zin": "Zoom in", "zout": "Zoom out", "fit": "Show the whole map", "close": "Close", "open": "Details",
           "back": "Back to the whole map", "kch": "Chapter", "ksec": "Section", "kcon": "Concept", "kterm": "Term",
           "how": "Choose a chapter to turn the wheel to it, then a section to see where it leads. "
                  "The arrow keys step through the sections.",
           "stats": "{c} chapters · {s} sections · {l} cross-references · {e} concept entries", "mins": "{n} min",
           "tOver": "Overview", "tList": "List", "tExp": "Explore", "tPath": "My path",
           "expEmpty": "Choose an idea on the map, in the list, or in the search box, and its closest connections appear here.",
           "colIn": "Links in", "colOut": "Links out", "centre": "Exploring",
           "out": {"helps": "Helps you understand", "challenges": "Challenges", "rival": "Competing answer", "example": "Is an example of",
                   "leads": "Leads on to", "xref": "The guide points to", "seq": "Next in the chapter"},
           "in": {"helps": "Builds on", "challenges": "Is challenged by", "rival": "Competing answer", "example": "Has as an example",
                  "leads": "Follows from", "xref": "Refers to this", "pre": "Read first", "seq": "Earlier in the chapter"},
           "connection": "The connection", "editor": "Editor’s note, restating the guide", "passage": "Where the guide says it",
           "exploreX": "Explore this idea", "readPassage": "Read the passage", "noRel": "The guide links these sections. Here is the sentence that does.",
           "cWhat": "In plain words", "cQ": "The question it helps answer", "cEx": "An everyday example", "cBack": "Read first, and why",
           "cCheck": "Check your understanding", "cShow": "Show an answer", "cGot": "I could explain it", "cAgain": "Not yet",
           "aRead": "Read", "aExplore": "Explore connections", "aSave": "Add to my path", "aSaved": "Saved ✓",
           "sVisited": "Visited", "sRead": "Read", "sChecked": "Understanding checked",
           "pNone": "Answer a few short questions about what you want to understand, and the map will show a reading path built for you, in order, with a reason for each step.",
           "pFind": "Find my reading path", "pYour": "Your question", "pSteps": "{n} steps · about {m} min", "pNext": "Next step",
           "pEdit": "Change my path", "pSaved": "Saved ideas", "pNoSaved": "Ideas you add with “Add to my path” appear here.",
           "pPresets": "Other routes", "pShow": "Show on the wheel", "pDeep": "Deeper study", "pBg": "Background", "pRemove": "Remove",
           "pNote": "These are suggestions from your answers, not a measure of ability. Reading a chapter does not mean you have understood it.",
           "pLoading": "Loading your path…", "pDone": "Done", "pMarkDone": "Mark done",
           "nBack": "Back", "nOver": "Overview", "nNext": "Next", "trail": "Your trail", "conn": "{n} connections", "lChapters": "Chapters",
           "wheelHint": "Tap a chapter to explore it.", "found": "This section is not on your path yet."},
    "fa": {"kmap": "نقشهٔ راهنما", "chapter": "فصل {n}", "sec": "قسمتِ {i} از {n}", "concept": "مدخلِ مفهوم",
           "path": "مسیرِ یادگیری", "read": "خواندنِ فصل", "readsec": "خواندنِ این قسمت", "entry": "خواندنِ مدخلِ کامل",
           "listen": "شنیدن · {n} دقیقه", "deeper": "مطالعهٔ عمیق‌تر", "practise": "تمرینِ پرسش‌های آن",
           "sections": "قسمت‌ها", "connected": "فصل‌هایی با بیشترین پیوند", "linksn": "{n} پیوند",
           "entries": "مدخل‌های مفهومی", "terms": "اصطلاح‌هایی که این‌جا شرح داده می‌شوند", "out": "ارجاع می‌دهد به",
           "in": "ارجاع‌شده از", "where": "جایی که راهنما آن را شرح می‌دهد", "related": "مفاهیمِ مرتبط",
           "same": "همچنین در این قسمت", "parts": "پنج بخش", "paths": "مسیرهایی در راهنما",
           "onpaths": "در این مسیرهای یادگیری", "steps": "{n} فصل", "start": "شروعِ خواندن", "closepath": "بیرون آمدن از مسیر",
           "read_p": "{n}٪ را خوانده‌اید", "stopped": "جایی که ماندید", "continue": "ادامهٔ خواندن", "prev": "قبلی",
           "next": "بعدی", "showsec": "نمایشِ این قسمت روی نقشه", "find": "جست‌وجو در نقشه…",
           "none": "چیزی پیدا نشد.", "zin": "بزرگ‌نمایی", "zout": "کوچک‌نمایی", "fit": "نمایشِ کلِ نقشه", "close": "بستن",
           "open": "جزئیات", "back": "بازگشت به کلِ نقشه", "kch": "فصل", "ksec": "قسمت", "kcon": "مفهوم", "kterm": "اصطلاح",
           "how": "فصلی را برگزینید تا چرخ به سوی آن بچرخد، سپس قسمتی را تا ببینید به کجا می‌رسد. "
                  "کلیدهای جهت‌نما قسمت‌ها را یکی‌یکی پیش می‌برند.",
           "stats": "{c} فصل · {s} قسمت · {l} ارجاع · {e} مدخلِ مفهومی", "mins": "{n} دقیقه",
           "tOver": "نمای کلی", "tList": "فهرست", "tExp": "کاوش", "tPath": "مسیر من",
           "expEmpty": "ایده‌ای را روی نقشه، در فهرست یا در کادرِ جست‌وجو برگزینید تا نزدیک‌ترین پیوندهایش این‌جا بیاید.",
           "colIn": "پیوندهای ورودی", "colOut": "پیوندهای خروجی", "centre": "در حالِ کاوش",
           "out": {"helps": "به فهمیدنِ این کمک می‌کند", "challenges": "به چالش می‌کشد", "rival": "پاسخی رقیب", "example": "نمونه‌ای از",
                   "leads": "ادامه می‌یابد به", "xref": "راهنما ارجاع می‌دهد به", "seq": "قسمتِ بعدی در فصل"},
           "in": {"helps": "بر پایهٔ", "challenges": "به چالش کشیده می‌شود با", "rival": "پاسخی رقیب", "example": "نمونه‌ای دارد:",
                  "leads": "برخاسته از", "xref": "به این ارجاع می‌دهد", "pre": "پیش از این بخوانید", "seq": "قسمتِ پیشین در فصل"},
           "connection": "پیوند", "editor": "یادداشتِ ویراستار، بازگویی از راهنما", "passage": "جایی که راهنما این را می‌گوید",
           "exploreX": "کاوشِ این ایده", "readPassage": "خواندنِ عبارت", "noRel": "راهنما این دو قسمت را به هم پیوند می‌دهد. جمله‌ای که این کار را می‌کند:",
           "cWhat": "به زبانِ ساده", "cQ": "پرسشی که به پاسخ‌دادنش کمک می‌کند", "cEx": "یک مثالِ روزمره", "cBack": "نخست بخوانید، و چرا",
           "cCheck": "فهمتان را بسنجید", "cShow": "نمایشِ پاسخ", "cGot": "می‌توانستم توضیح بدهم", "cAgain": "هنوز نه",
           "aRead": "خواندن", "aExplore": "کاوشِ پیوندها", "aSave": "افزودن به مسیرِ من", "aSaved": "ذخیره شد ✓",
           "sVisited": "دیده‌شده", "sRead": "خوانده‌شده", "sChecked": "فهم سنجیده شد",
           "pNone": "به چند پرسشِ کوتاه دربارهٔ آنچه می‌خواهید بفهمید پاسخ دهید تا نقشه مسیری برایتان بچیند، به ترتیب و با دلیلی برای هر گام.",
           "pFind": "مسیرِ مطالعه‌ام را پیدا کن", "pYour": "پرسشِ شما", "pSteps": "{n} گام · حدودِ {m} دقیقه", "pNext": "گامِ بعد",
           "pEdit": "تغییرِ مسیرِ من", "pSaved": "ایده‌های ذخیره‌شده", "pNoSaved": "ایده‌هایی که با «افزودن به مسیرِ من» بیفزایید این‌جا می‌آیند.",
           "pPresets": "مسیرهای دیگر", "pShow": "نمایش روی چرخ", "pDeep": "مطالعهٔ عمیق‌تر", "pBg": "پیش‌زمینه", "pRemove": "برداشتن",
           "pNote": "این‌ها پیشنهادهایی بر پایهٔ پاسخ‌های شماست، نه سنجشِ توانایی. خواندنِ یک فصل به معنای فهمیدنِ آن نیست.",
           "pLoading": "در حالِ بارگیریِ مسیر…", "pDone": "انجام شد", "pMarkDone": "علامتِ انجام‌شده",
           "nBack": "بازگشت", "nOver": "نمای کلی", "nNext": "بعدی", "trail": "ردِ شما", "conn": "{n} پیوند", "lChapters": "فصل‌ها",
           "wheelHint": "برای کاوشِ یک فصل رویش بزنید.", "found": "این قسمت هنوز در مسیرِ شما نیست."},
}

# Short chapter names for the chart, where the full titles do not fit (the panel gives them in full).
CH_SHORT = {1: ("What is epistemology?", "معرفت‌شناسی چیست؟"), 2: ("History", "تاریخ"),
            3: ("Logic and arguments", "منطق و استدلال"), 4: ("Language and definitions", "زبان و تعریف"),
            5: ("What is knowledge?", "معرفت چیست؟"), 6: ("Justification", "توجیه"), 7: ("Sources of knowledge", "منابع معرفت"),
            8: ("Skepticism", "شکاکیت"), 9: ("Probability and Bayes", "احتمال و بیز"), 10: ("Science and evidence", "علم و شواهد"),
            11: ("Truth and relativism", "حقیقت و نسبی‌گرایی"), 12: ("Social epistemology", "معرفت‌شناسی اجتماعی"),
            13: ("Virtue and belief", "فضیلت و اخلاقِ باور"), 14: ("Psychology of reasoning", "روان‌شناسیِ استدلال"),
            15: ("Fallacies", "مغالطه‌ها"), 16: ("The toolkit", "جعبه‌ابزار")}


def readme_paths(md):
    """The learning paths on the guide's contents page, as (name, note, [(chapter, note), ...])."""
    text = (SRC() / "README.md").read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^\*\*(.+?)\*\*\s*(?:\(([^)]*)\))?\s*:\s*(.+)$", text, re.M):
        steps = [(int(s.group(1)), (s.group(2) or "").strip())
                 for s in re.finditer(r"\[[^\]]+\]\((\d\d)-[\w-]+\.md\)(?:\s*\(([^)]*)\))?", m.group(3))]
        steps = [s for s in steps if s[0] <= 16]
        if len(steps) >= 3:
            out.append((plain_inline(md, m.group(1)), (m.group(2) or "").strip(), steps))
    return out


def readme_question():
    """The question at the root of the contents page's diagram of how the ideas connect."""
    m = re.search(r'Q\["([^"]+)"\]', (SRC() / "README.md").read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def spaced(markup):
    """Markup as plain text, with the breaks between paragraphs and list items kept as spaces."""
    return html.unescape(strip_tags(re.sub(r"</(?:p|li|div|h\d)>|<br\s*/?>", " ", markup or "")))


def excerpt(text, limit=230):
    """The opening of a section, cut at a sentence if one ends late enough."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "), cut.rfind("؟ "))
    return cut[:end + 1] if end > limit // 2 else cut.rsplit(" ", 1)[0].rstrip(",;:—–") + "…"


# Sections that are reading apparatus rather than ideas (how to use the guide, summaries, timelines, checklists and exercises) stay
# in the chapters but are left off the map's wheel.
MAP_APPARATUS = {(2, "timeline"), (5, "summary-of-theories"), (15, "how-to-use-this-field-guide"), (15, "quick-reference-table"),
                 (15, "practice-spot-the-fallacy"), (16, "checklists")}


def map_title(title):
    """A section's name for the wheel: the numbering of a sequence ('Step 3: ') is carried by the order, so it is dropped."""
    return re.sub(r"^(?:Step|گامِ?)\s*[\d۰-۹]+\s*[:：]\s*", "", title).strip() or title


def build_map(C, chapters, md, art):
    """The map of the guide, drawn as a planisphere by assets/map.js from the data embedded here: the sixteen chapters
    (each a medallion with its painting) in the guide's five parts, every section of every chapter on the outer orbit,
    the guide's own cross-references between them, its learning paths, and each concept entry on the section that
    teaches it."""
    root = up(1)
    h = home(root)
    lang = LANG
    P = lang_prefix()
    en = EN_CHAPTERS or chapters
    outline = {}
    for ch in en.values():
        if ch.num <= 16:
            _, heads = md.render(clean_chapter_markdown(split_epigraphs(ch.text)[0]), lambda x: x)
            outline[ch.num] = [(hd[0], hd[1], hd[2]) for hd in heads]
    idx = [(n, s, p) for n, hs in outline.items() for _, s, p in hs]
    texts = {e["u"]: e["x"] for e in LEARN["search"] if e["k"] == "s"}

    # the sections: each chapter's second-level headings, less the ones that only frame it
    sections, at, owner = [], {}, {}
    for n in sorted(outline):
        ch = chapters[n]
        pages = (DEEP_FA if lang == "fa" else DEEP).get(ch.slug, {})
        cur = None
        for level, slug, plain in outline[n]:
            if level == 2:
                cur = None if slug in NOT_SUBSTANTIVE or (n, slug) in MAP_APPARATUS else slug
                if cur:
                    at[(n, slug)] = len(sections)
                    sections.append({"c": n, "id": slug, "t": map_title(plain if lang == "en" else FA_HEADS.get((n, slug), plain)),
                                     "x": excerpt(texts.get(f"{P}guide/{ch.href}#{slug}", "")),
                                     "d": f"../deeper/{ch.slug}/{slug}.html" if slug in pages else "", "k": [], "g": []})
            if cur:
                owner[(n, slug)] = cur

    # the guide's cross-references, from section to section (or to a whole chapter, as -n), each with the sentence that makes it
    weights, passages = {}, {}

    def scan(text, n, h2s, visit):
        k, cur = -1, None
        for line in text.split("\n"):
            if line.startswith("## "):
                k += 1
                cur = at.get((n, h2s[k])) if k < len(h2s) else None
                continue
            if cur is None:
                continue
            for m in re.finditer(r"\]\((?:(\d\d)-[\w-]+\.md)?(?:#([\w-]+))?\)", line):
                if not m.group(1) and not m.group(2):
                    continue
                tn = int(m.group(1)) if m.group(1) else n
                if tn > 16:
                    continue
                target = at.get((tn, owner.get((tn, m.group(2))))) if m.group(2) else None
                to = target if target is not None else -tn
                if to != cur and to != -n:
                    visit(cur, to, line, m)
        return k + 1

    def sentence(line, m):
        """The sentence of a markdown line that holds the link ending at match m, as plain text."""
        start = line.rfind("[", 0, m.start())
        marked = line[:start] + "\x01" + line[start + 1:m.start()] + "\x02" + line[m.end():] if start >= 0 else line
        marked = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", marked)
        marked = re.sub(r"[*_`>#|]+", "", marked)
        marked = re.sub(r"^\s*(?:[-+]|\d+\.)\s+", "", marked.strip())
        for sent in re.split(r"(?<=[.!?؟])\s+(?=[\"“(A-Zآ-ی\x01])", marked):
            if "\x01" in sent:
                return re.sub(r"\s+", " ", sent.replace("\x01", "").replace("\x02", "")).strip()
        return ""

    def count(cur, to, line, m):
        weights[(cur, to)] = weights.get((cur, to), 0) + 1
        if (cur, to) not in passages:
            passages[(cur, to)] = sentence(line, m)

    for n in sorted(outline):
        h2s = [s_ for lv, s_, _ in outline[n] if lv == 2]
        if scan(clean_chapter_markdown(split_epigraphs(en[n].text)[0]), n, h2s, count) != len(h2s):
            print(f"  note: map: chapter {n} has a different number of '## ' lines than second-level headings")
    if lang == "fa":  # the passages in Persian, where the translation keeps the section structure
        passages.clear()
        for n in sorted(outline):
            if chapters[n].fallback:
                continue
            h2s = [s_ for lv, s_, _ in outline[n] if lv == 2]
            local = {}
            if scan(clean_chapter_markdown(split_epigraphs(chapters[n].text)[0]), n, h2s,
                    lambda cur, to, line, m: local.setdefault((cur, to), sentence(line, m))) == len(h2s):
                passages.update({k_: v_ for k_, v_ in local.items() if v_})
    links = [[a, b, w] for (a, b), w in sorted(weights.items())]

    # every concept entry on the section (or chapter) that teaches it
    cons = {}
    for cid, node in C.N.items():
        home_ = concept_home(C, cid, idx)
        si = at.get((home_[0], owner.get((home_[0], home_[1]))), -1) if home_ and home_[1] else -1
        cons[cid] = {"t": C.title(cid, lang), "l": strip_tags(C.line(cid, lang)), "c": home_[0] if home_ else 0, "s": si,
                     "a": (home_[1] or "") if home_ else "", "k": [x for x in node.get("k", []) if x in C.N],
                     "h": " ".join([C.title(cid), C.title(cid, "fa"), node.get("q", ""), node.get("w", "")]).lower()}
        if si >= 0:
            sections[si]["k"].append(cid)
    # and the glossary's terms on the sections that explain them
    for v in LEARN["terms"].values():
        m = re.search(r"guide/(\d\d)-[\w-]+\.html#([\w-]+)", v.get("s", ""))
        if v["id"].startswith("g-") and m:
            si = at.get((int(m.group(1)), owner.get((int(m.group(1)), m.group(2)))))
            if si is not None:
                sections[si]["g"].append([v["t"], "../" + v["g"][len(P):]])

    # editorial relations between sections, checked against the real headings
    rel_path = ROOT / "tools" / "site" / "map-relations.json"
    relations = []
    for r_ in json.loads(rel_path.read_text(encoding="utf-8"))["relations"]:
        ends = []
        for key in (r_["from"], r_["to"]):
            n_, _, slug_ = key.partition("/")
            if (int(n_), slug_) not in at:
                raise ValueError(f"map relation names a section that does not exist: {key}")
            ends.append(at[(int(n_), slug_)])
        if r_["kind"] not in ("helps", "challenges", "rival", "example", "leads"):
            raise ValueError(f"map relation has an unknown kind: {r_['kind']}")
        relations.append([ends[0], ends[1], r_["kind"], r_["fa" if lang == "fa" else "en"]])
    # what each idea card needs, fetched once the map has drawn: the plain explanation, the question it answers,
    # an everyday example and a check
    idea_cards = {}
    for cid, node in C.N.items():
        if cid == "root":
            continue
        r_ = C.R.get(cid, {}).get(lang, {})
        chk = r_.get("check") or {}
        ex_ = spaced(node.get("xf" if lang == "fa" else "xe", ""))
        card = {"w": spaced(r_.get("why", "")), "i": excerpt(spaced(r_.get("idea") or node.get(lang, "")), 680), "x": excerpt(ex_, 420),
                "q": spaced(chk.get("q", "")), "a": spaced(chk.get("a", ""))}
        idea_cards[cid] = {k_: v_ for k_, v_ in card.items() if v_}
    sfx = "-fa" if lang == "fa" else ""
    write(ASSETS / "data" / f"map-cards{sfx}.json", json.dumps(idea_cards, ensure_ascii=False, separators=(",", ":")))
    write(ASSETS / "data" / f"map-passages{sfx}.json",
          json.dumps({f"{a_}>{b_}": t_ for (a_, b_), t_ in sorted(passages.items()) if t_}, ensure_ascii=False, separators=(",", ":")))

    questions = {}
    for q in LEARN["questions"]:
        questions[q["ch"]] = questions.get(q["ch"], 0) + 1
    romans = [r for r, _, nums in PARTS if r]
    chs = []
    for n in range(1, 17):
        ch = chapters[n]
        chs.append({"n": n, "p": romans.index(PART_OF[n][0]), "t": ch.title, "sh": L(*CH_SHORT[n]), "l": ch.label,
                    "h": f"../guide/{ch.href}", "img": f"{root}assets/art/{ch.art}-dot.jpg", "im": art.src(ch.art, root, 640),
                    "b": plain_inline(md, ch.blurb) if ch.blurb else "", "m": ch.minutes, "slug": ch.slug,
                    "a": round(ch.track["duration"] / 60) if ch.track else 0,
                    "dp": f"../deeper/{ch.slug}/" if (DEEP_FA if lang == "fa" else DEEP).get(ch.slug) else "",
                    "rv": f"../review/#{ch.slug}" if questions.get(n) else ""})
    parts = [{"r": r, "t": L(name, PARTS_FA[r][1]), "l": L(f"Part {r}", f"بخشِ {PARTS_FA[r][0]}"), "ch": nums}
             for r, name, nums in PARTS if r]
    hours = round(sum(chapters[n].minutes for n in range(1, 17)) / 60)
    paths = [{"t": L("Cover to cover", "از آغاز تا پایان"),
              "m": L(f"all sixteen chapters in order, about {hours} hours of reading", f"همهٔ شانزده فصل به ترتیب، حدودِ {num(hours)} ساعت خواندن"),
              "st": [[n, ""] for n in range(1, 17)]}]
    paths += [{"t": name, "m": note, "st": [[n, plain_inline(md, s) if s else ""] for n, s in steps]}
              for name, note, steps in readme_paths(md)]
    ui = dict(MAP_UI[lang])
    data = {"lang": lang, "ui": ui, "q": readme_question(), "parts": parts, "chapters": chs, "sections": sections,
            "links": links, "rel": relations, "concepts": cons, "paths": paths, "site": root,
            "files": {"cards": f"{root}assets/data/map-cards{sfx}.json", "pass": f"{root}assets/data/map-passages{sfx}.json",
                      "rp": f"{root}assets/data/reading-path{sfx}.json", "rpPage": f"{h}reading-path/"},
            "root": {"t": C.title("root", lang), "u": "../concepts/root.html", "img": f"{root}assets/art/map-dot.jpg",
                     "l": strip_tags(C.line("root", lang))}}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    refs = sum(w for _, _, w in links)

    head = hero(art, "map", root, kicker=L("The map of the guide", "نقشهٔ راهنما"),
                title=L("A planisphere of knowledge", "نقشهٔ آسمانیِ دانش"), cls="short",
                lede=L(f"The whole guide on one chart: its sixteen chapters in five parts, all {len(sections)} sections, and the "
                       f"{refs} cross-references that tie them together. Turn the wheel to a chapter to see what it covers, "
                       "follow a section to where it leads, or take one of the guide’s learning paths.",
                       f"کلِ راهنما روی یک نقشه: شانزده فصل در پنج بخش، همهٔ {num(len(sections))} قسمت، و {num(refs)} ارجاعی که "
                       "آن‌ها را به هم می‌پیوندد. چرخ را به سوی فصلی بچرخانید تا ببینید چه چیزهایی را در بر می‌گیرد، قسمتی را "
                       "دنبال کنید تا ببینید به کجا می‌رسد، یا یکی از مسیرهای یادگیریِ راهنما را بپیمایید."),
                actions=(f'<a class="btn primary" href="#chart">{icon("map")} {L("Explore the map", "کاوش در نقشه")}</a>'
                         f'<a class="btn" href="{h}concepts/">{icon("grid")} {L("All concepts as pages", "همهٔ مفاهیم به صورتِ صفحه")}</a>'))
    tab = lambda key, ico, extra="": (f'<button type="button" role="tab" data-view="{key}" aria-selected="false"{extra}>{ico}<span>{ui["t" + key[0].upper() + key[1:]]}</span></button>')
    tools = (f'<div class="chart-head">'
             f'<div class="chart-find"><span aria-hidden="true">{icon("search")}</span>'
             f'<input id="mapq" type="search" autocomplete="off" placeholder="{attr(ui["find"])}" aria-label="{attr(ui["find"])}" '
             f'role="combobox" aria-expanded="false" aria-controls="mapres" aria-autocomplete="list">'
             f'<div class="chart-res" id="mapres" role="listbox" hidden></div></div>'
             f'<div class="viewtabs" role="tablist" aria-label="{L("Views of the map", "نماهای نقشه")}">'
             f'{tab("over", icon("map"))}{tab("list", icon("toc"))}{tab("exp", icon("pin"))}{tab("path", icon("clock"))}</div>'
             f'<div class="chart-zoom" role="group" aria-label="{L("Zoom", "بزرگ‌نمایی")}">'
             f'<button type="button" data-zoom="in" aria-label="{ui["zin"]}" title="{ui["zin"]}">{icon("plus")}</button>'
             f'<button type="button" data-zoom="out" aria-label="{ui["zout"]}" title="{ui["zout"]}">{icon("minus")}</button>'
             f'<button type="button" data-zoom="fit" aria-label="{ui["fit"]}" title="{ui["fit"]}">{icon("fit")}</button></div></div>')
    part_keys = "".join(f'<button type="button" class="lg-part p{i}" data-map-go="part-{i + 1}"><i></i>{esc(p["r"] if lang == "en" else PARTS_FA[p["r"]][0])} · {esc(p["t"])}</button>'
                        for i, p in enumerate(parts))
    legend = (f'<div class="chart-legend">'
              f'<div class="lg-parts" role="group" aria-label="{L("The five parts", "پنج بخش")}">{part_keys}</div>'
              f'<div class="lg-keys" aria-hidden="true">'
              f'<span><i class="lg-med"></i>{L("a chapter, with its painting", "یک فصل، با نقاشیِ آن")}</span>'
              f'<span><i class="lg-dot"></i>{L("a section", "یک قسمت")}</span>'
              f'<span><i class="lg-con"></i>{L("a section with a concept entry", "قسمتی با مدخلِ مفهوم")}</span>'
              f'<span><i class="lg-chord"></i>{L("cross-references between chapters; thicker means more", "ارجاع‌های میانِ فصل‌ها؛ ضخیم‌تر یعنی بیشتر")}</span>'
              f'<span><i class="lg-prog"></i>{L("how far you have read", "چقدر خوانده‌اید")}</span></div></div>'
              f'<p class="chart-hint" data-hint-touch="{attr(L("Tap a chapter to explore it and its connections. Pinch with two fingers to zoom the wheel.", "روی فصلی بزنید تا آن و پیوندهایش را بکاوید. برای بزرگ‌نمایی چرخ با دو انگشت چنگ بزنید."))}">'
              f'{L("Click a chapter to turn the wheel to it, then a section to follow its links. The arrow keys step through the sections; drag to move, Ctrl + scroll to zoom.", "روی فصلی کلیک کنید تا چرخ به سوی آن بچرخد، سپس روی قسمتی تا پیوندهایش را دنبال کنید. کلیدهای جهت‌نما قسمت‌ها را پیش می‌برند؛ برای جابه‌جایی بکشید و برای بزرگ‌نمایی Ctrl و چرخِ موشواره را به کار ببرید.")}</p>')
    chart = (f'<section class="chart-wrap" id="chart" aria-label="{L("The map of the guide", "نقشهٔ راهنما")}">'
             f'<div class="chart" data-view="over">{tools}'
             f'<svg class="wheel" role="group" aria-label="{attr(L("Map of the guide: chapters, sections and their cross-references", "نقشهٔ راهنما: فصل‌ها، قسمت‌ها و ارجاع‌های میانِ آن‌ها"))}"></svg>'
             f'<div class="hood" hidden></div>'
             f'<aside class="chart-panel" aria-live="polite"></aside>'
             f'<noscript><p class="chart-nojs">{L("The interactive map needs JavaScript. The contents of the guide are on", "نقشهٔ تعاملی به جاوااسکریپت نیاز دارد. فهرستِ راهنما در")} '
             f'<a href="{h}guide/">{L("the guide’s contents page", "صفحهٔ فهرستِ راهنما")}</a>.</p></noscript></div>{legend}</section>')

    cards = []
    for i, p in enumerate(paths):
        chain = "".join(f'<li><img src="{root}assets/art/{chapters[n].art}-dot.jpg" alt="" loading="lazy" width="44" height="44">'
                        f'<span>{num(n)}</span></li>' for n, _ in p["st"])
        first = chapters[p["st"][0][0]]
        note = f'<p>{esc(p["m"])}</p>' if p["m"] else ""
        cards.append(f'<article class="pcard"><span class="kicker">{ui["path"]} · {ui["steps"].format(n=num(len(p["st"])))}</span>'
                     f'<h3>{esc(p["t"])}</h3>{note}<ol class="pchain" aria-label="{attr(", ".join(chapters[n].label for n, _ in p["st"]))}">{chain}</ol>'
                     f'<div class="pcard-foot"><a href="#chart" data-map-go="path-{i}">{icon("map")} {L("Show on the map", "نمایش روی نقشه")}</a>'
                     f'<a href="../guide/{first.href}">{L("Start with", "شروع با")} {esc(first.label)} {L("→", "←")}</a></div></article>')
    paths_html = (f'<section class="wrap map-paths" aria-labelledby="mp-h"><header class="sec-head">'
                  f'<span class="kicker">{ui["paths"]}</span>'
                  f'<h2 id="mp-h">{L("Routes across the map", "مسیرهایی روی نقشه")}</h2>'
                  f'<p>{L("The guide can be read from start to finish, but its contents page also suggests shorter routes for particular goals. Show one on the map to see which chapters it visits, and in what order.", "راهنما را می‌توان از آغاز تا پایان خواند، اما صفحهٔ فهرستِ آن مسیرهای کوتاه‌تری هم برای هدف‌های خاص پیشنهاد می‌کند. هر کدام را روی نقشه ببینید تا بدانید از کدام فصل‌ها و به چه ترتیبی می‌گذرد.")}</p></header>'
                  f'<div class="pgrid">{"".join(cards)}</div></section>')
    body = (f'{head}{label(art, "map")}<main id="main" class="mapmain">{chart}{paths_html}</main>'
            f'<script type="application/json" id="mapdata">{payload}</script>'
            f'<script src="{av(root, "reading-path-core.js")}" defer></script>'
            f'<script src="{av(root, "map.js")}" defer></script>')
    # an old link to the shared map in Persian (/map/?lang=fa) now opens the Persian edition's own map
    redirect = ('<script>if(/[?&]lang=fa\\b/.test(location.search))location.replace("../fa/map/"+location.hash)</script>'
                if lang == "en" else "")
    page("map/index.html", root=root, title=L("Map of the guide", "نقشهٔ راهنما"),
         desc=L(f"An interactive map of Mastering Epistemology: sixteen chapters, {len(sections)} sections, the cross-references "
                "between them, and every concept entry.",
                f"نقشهٔ تعاملیِ «تسلط بر معرفت‌شناسی»: شانزده فصل، {num(len(sections))} قسمت، ارجاع‌های میانِ آن‌ها و همهٔ مدخل‌های مفهومی."),
         body=body, current="map", hero_img=(art.src("map", root), art.srcset("map", root)), bar="clear", extra_head=redirect)


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
        home_ = concept_home(C, cid, idx)
        ch = chapters[home_[0]] if home_ else ch
        sec = home_ if home_ and home_[1] else None
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
            f'<div class="filter"><input id="cfilter" name="concept-filter" type="search" autocomplete="off" '
            f'placeholder="Filter concepts, thinkers, terms…" aria-label="Filter concepts"></div>'
            f'{"".join(blocks)}</main>')
    pages.append((ROOT / "concepts" / "index.html", root, "All concepts",
                  "Every concept in the epistemology map as a readable page, in English and Persian.", body, "concepts", "elephant"))


def build_concepts_fa(C, chapters, md, art, pages):
    root = up(1)
    idx = guide_heading_index(EN_CHAPTERS, md)
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
        crumbs = "".join(f'<a href="{a}.html">{esc(C.title(a, "fa"))}</a><span>‹</span>' for a in route)
        who = n.get("w", "")
        extra = (f'<div class="crumbs">{crumbs or "<span>نقشهٔ مفاهیم</span>"}</div>'
                 f'<h1>{esc(C.title(cid, "fa"))}</h1><div class="en-title" lang="en" dir="ltr">{esc(C.title(cid))}</div>'
                 f'<div class="who" dir="ltr">{esc(who)}</div>'
                 f'<div class="actions"><a class="btn" href="{map_url(root, cid)}" data-set-site-lang="fa">{icon("pin")} نمایش روی نقشه</a>'
                 f'<a class="btn" href="{root}concepts/{cid}.html" lang="en" data-set-site-lang="en">English</a></div>')
        head = hero(art, key, root, kicker="", title="", cls="band", title_html=extra)
        entry = f'<div class="entry"><div class="l-fa" lang="fa" dir="rtl">{concept_body(C, cid, "fa")}</div></div>'
        side = []
        kids = [k for k in n.get("c", []) if k in C.N]
        if kids:
            li = "".join(f'<li><a href="{k}.html"><b>{esc(C.title(k, "fa"))}</b><small>{esc(strip_tags(C.line(k, "fa")))}</small></a></li>' for k in kids)
            side.append(f'<section class="box"><h2>عمیق‌تر شوید · {num(len(kids))}</h2><ul>{li}</ul></section>')
        links = [k for k in n.get("k", []) if k in C.N]
        if links:
            li = "".join(f'<li><a href="{k}.html"><b>↖ {esc(C.title(k, "fa"))}</b></a></li>' for k in links)
            side.append(f'<section class="box"><h2>پیوندها در سراسر نقشه</h2><ul>{li}</ul></section>')
        ch = chapters[chn]
        home_ = concept_home(C, cid, idx)
        ch = chapters[home_[0]] if home_ else ch
        sec = home_ if home_ and home_[1] else None
        if sec:
            ch = chapters[sec[0]]
            head_fa = next((h[2] for h in EN_HEADS.get(sec[0], []) if h[1] == sec[1]), sec[2])
            href = f"../guide/{ch.href}#{sec[1]}"
            where = f"§ {esc(FA_HEADS.get((sec[0], sec[1]), head_fa))}"
        else:
            href, where = f"../guide/{ch.href}", "خواندنِ فصل"
        side.append(f'<section class="box"><h2>در راهنما</h2>'
                    f'<a class="guidebox" href="{href}"><img src="{art.src(ch.art, root, 640)}" alt="" loading="lazy">'
                    f'<span><small>{ch.label}</small><b>{esc(ch.title)}</b><small style="text-transform:none;letter-spacing:0">{where}</small></span></a></section>')
        q = n.get("q") or n["t"]
        side.append(f'<section class="box"><h2>مطالعهٔ بیشتر</h2><ul>'
                    f'<li><a href="https://fa.wikipedia.org/w/index.php?search={attr(C.title(cid, "fa").replace(" ", "+"))}" rel="noopener"><b>ویکی‌پدیای فارسی ↗</b><small>پیش‌زمینه و مطالعهٔ بیشتر</small></a></li>'
                    f'<li><a href="https://plato.stanford.edu/search/searcher.py?query={attr(q.replace(" ", "+"))}" rel="noopener"><b>دانشنامهٔ فلسفهٔ استنفورد ↗</b><small>مقاله‌های مرجعِ داوری‌شده (انگلیسی)</small></a></li>'
                    f'</ul></section>')
        par = C.parent.get(cid)
        sibs = [s_ for s_ in C.N[par]["c"] if s_ in C.N] if par else []
        i = sibs.index(cid) if cid in sibs else -1
        prev_id = sibs[i - 1] if i > 0 else None
        next_id = sibs[i + 1] if 0 <= i < len(sibs) - 1 else (kids[0] if kids else None)
        sib = '<nav class="sibs" aria-label="مفاهیمِ هم‌جوار">'
        if prev_id:
            sib += f'<a href="{prev_id}.html"><small>→ قبلی</small><b>{esc(C.title(prev_id, "fa"))}</b></a>'
        elif par:
            sib += f'<a href="{par}.html"><small>↑ بالاتر</small><b>{esc(C.title(par, "fa"))}</b></a>'
        if next_id:
            sib += f'<a class="n" href="{next_id}.html"><small>بعدی ←</small><b>{esc(C.title(next_id, "fa"))}</b></a>'
        sib += "</nav>"
        body = (f"{head}<main id=\"main\" class=\"cpage\">{entry}<aside class=\"aside\">{''.join(side)}</aside></main>{sib}")
        desc = strip_tags(C.line(cid, "fa")) or f"{C.title(cid, 'fa')}: مفهومی در معرفت‌شناسی."
        pages.append((OUT() / "concepts" / f"{cid}.html", root, f"{C.title(cid, 'fa')} · مفاهیم", desc, body, "concepts", key))

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
        hay = lambda cid: attr((C.title(cid) + " " + C.title(cid, "fa") + " " + strip_tags(C.line(cid, "fa")) + " " + C.N[cid].get("q", "")).lower())
        items = "".join(f'<a class="{"d3" if d else ""}" href="{c}.html" data-hay="{hay(c)}"><b>{esc(C.title(c, "fa"))}</b>'
                        f'<small>{esc(strip_tags(C.line(c, "fa")))}</small></a>' for c, d in members)
        key = BRANCH_ART.get(b, "home")
        blocks.append(f'<section class="branch" data-hay="{hay(b)}"><header><img src="{art.src(key, root, 640)}" alt="" loading="lazy">'
                      f'<div><a href="{b}.html"><b>{esc(C.title(b, "fa"))}</b></a>'
                      f'<p>{esc(strip_tags(C.line(b, "fa")))}</p></div></header>'
                      f'<div class="clist">{items}</div></section>')
    head = hero(art, "elephant", root, kicker="نقشهٔ مفاهیم به صورت صفحه", title="همهٔ مفاهیم", cls="short",
                lede=f"{num(135)} مفهوم در معرفت‌شناسی، هر یک با مدخلی کامل: مسئله‌ای که حل می‌کند، ایدهٔ اصلی، "
                     "اعتراض‌ها و پاسخ‌ها، اشتباه‌های رایج، و پرسشی برای خودآزمایی.",
                actions=f'<a class="btn" href="{map_url(root)}" data-set-site-lang="fa">{icon("map")} باز کردنِ نقشه</a><a class="btn" href="root.html">آغاز از ریشه</a>')
    body = (f'{head}{label(art, "elephant")}<main id="main" class="wrap" style="padding-top:36px;padding-bottom:80px">'
            f'<div class="filter"><input id="cfilter" name="concept-filter" type="search" autocomplete="off" placeholder="صافیِ مفاهیم، اندیشمندان، اصطلاحات…" aria-label="صافیِ مفاهیم"></div>'
            f'{"".join(blocks)}</main>')
    pages.append((OUT() / "concepts" / "index.html", root, "همهٔ مفاهیم",
                  "همهٔ مفاهیمِ نقشهٔ معرفت‌شناسی، هر یک در صفحه‌ای خواندنی.", body, "concepts", "elephant"))


FA_HEADS = {}  # (chapter, section id) -> Persian section title


# ----------------------------------------------------------------------------- other pages

def title_html(ch):
    """A chapter title; an English one on a Persian page keeps its own direction."""
    english = getattr(ch, "fallback", False) and ch.num not in FA_CHAPTERS
    return f'<span dir="ltr" lang="en">{esc(ch.title)}</span>' if english else esc(ch.title)


def chapter_card(art, ch, root):
    meta = f'<span>{icon("clock")} {num(ch.minutes)} {L("min", "دقیقه")}</span>'
    if ch.track:
        meta += f'<span>{icon("phones")} {minutes_label(ch.track["duration"])}</span>'
    blurb = re.sub(r"\*([^*]+)\*", r"\1", ch.blurb)
    return (f'<a class="card" href="{home(root)}guide/{ch.href}" data-slug="{ch.slug}"><div class="pic" style="--art:{art.color(ch.art)};--focus:{art.focus(ch.art)}">'
            f'{art.img(ch.art, root, sizes="(max-width:600px) 100vw, 320px", cls="")}<span class="num">{ch.label.upper()}</span></div>'
            f'<div class="body"><h4>{title_html(ch)}</h4><p>{esc(blurb)}</p><div class="meta">{meta}</div></div></a>')


def contents_parts(art, chapters, root):
    out = []
    for roman, name, nums in PARTS:
        cards = "".join(chapter_card(art, chapters[n], root) for n in nums)
        pl, pn = part_label(roman, name)
        out.append(f'<section class="part"><header><span class="kicker">{pl}</span>'
                   f'<h3>{esc(pn)}</h3></header><div class="grid">{cards}</div></section>')
    return "".join(out)


def readme_sections(md):
    text = (SRC() / "README.md").read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.M)
    intro = parts[0]
    secs = {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] for p in parts[1:]}
    return intro, secs


def build_guide_index(art, chapters, md, total_audio):
    root = up(1)
    intro, secs = readme_sections(md)
    intro = re.sub(r"^# .*\n", "", intro)
    intro, quotes = split_epigraphs(intro)
    intro = "\n".join(l for l in intro.split("\n") if l.strip() not in ("---",) and not l.startswith(("**A complete", "**راهنمای کامل")))
    intro_html, _ = md.render(intro, guide_links())
    intro_html = re.sub(r"^<p>", '<p class="lede">', intro_html.strip(), count=1)
    def sec(en, fa):
        body = secs.get(L(en, fa), "")
        body = "\n".join(l for l in body.split("\n") if l.strip() != "---")
        h, _ = md.render(body, guide_links())
        return polish(h)
    paths = sec("Learning paths", "مسیرهای یادگیری")
    how = sec("How each chapter works", "هر فصل چگونه کار می‌کند")
    connect = sec("How the ideas connect", "ایده‌ها چگونه به هم می‌پیوندند")
    companion = sec("The companion explorer", "نقشهٔ همراه")
    sources = sec("A note on sources and accuracy", "دربارهٔ منابع و دقت")
    q, c = quotes[0] if quotes else ("", "")
    epub = EPUB_NAME_FA if LANG == "fa" else EPUB_NAME
    head = hero(art, "guide", root, kicker=L("The guide · sixteen chapters, a glossary and a reading list", "راهنما · شانزده فصل، واژه‌نامه و فهرست مطالعه"),
                title=site_name(),
                dek=md.inline(q) if q else None, cite=md.inline(c) if c else None,
                facts=[f"{icon('book')} {L('16 chapters', '۱۶ فصل')}", f"{icon('clock')} {L('about 130,000 words', 'حدود ۱۳۰ هزار واژه')}",
                       f"{icon('phones')} {total_audio} {L('of audio', fa_audio('صوت', 'صوت انگلیسی'))}"],
                actions=f'<a class="btn primary" href="01-what-is-epistemology.html">{L("Start with chapter 1", "آغاز از فصل ۱")} {icon("arrow")}</a>'
                        f'<a class="btn" href="audio/">{icon("phones")} {L("Listen", "شنیدن")}</a>'
                        f'<a class="btn" href="{epub}" download>{icon("download")} EPUB</a>')
    h2s = 'style="border:0;padding:0;margin-top:0"'
    body = (f'{head}{label(art, "guide")}'
            f'<main id="main"><div class="wrap" style="padding-top:34px"><div id="resume"></div><div class="prose" style="max-width:46rem">{intro_html}</div></div>'
            f'<section class="section" style="padding-top:40px"><div class="wrap">{contents_parts(art, chapters, root)}</div></section>'
            f'<section class="section alt"><div class="wrap"><div class="section-head"><div><span class="kicker">{L("How the ideas connect", "پیوند ایده‌ها")}</span>'
            f'<h2>{L("One question, many branches", "یک پرسش، شاخه‌های بسیار")}</h2></div><p>{L("Every chapter answers part of a single question: what should I believe, and how sure should I be?", "هر فصل به بخشی از یک پرسش پاسخ می‌دهد: چه باید باور کنم، و تا چه اندازه مطمئن؟")}</p></div>'
            f'<div class="prose" style="max-width:none">{connect}</div></div></section>'
            f'<section class="section"><div class="wrap"><div class="section-head"><div><span class="kicker">{L("Learning paths", "مسیرهای یادگیری")}</span>'
            f'<h2>{L("Where to start", "از کجا شروع کنیم")}</h2></div></div>'
            f'<div id="rp-home"><p>{L("Start with your own question, choose a study mode, and find the sections that fit your time.", "از پرسش خودتان آغاز کنید، شیوهٔ مطالعه را انتخاب کنید و بخش‌های مناسب با زمانتان را پیدا کنید.")}</p><a class="btn primary" href="{home(root)}reading-path/">{L("Find my reading path →", "مسیر مطالعه‌ام را پیدا کن ←")}</a></div>'
            f'<div class="prose" style="max-width:52rem">{paths}</div></div></section>'
            f'<section class="section alt"><div class="wrap" style="display:grid;gap:40px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">'
            f'<div class="prose"><h2 {h2s}>{L("How each chapter works", "هر فصل چگونه کار می‌کند")}</h2>{how}</div>'
            f'<div class="prose"><h2 {h2s}>{L("The companion map", "نقشهٔ همراه")}</h2>{companion}'
            f'<h2 style="border:0;padding:0">{L("A note on sources", "دربارهٔ منابع")}</h2>{sources}</div></div></section></main>')
    return body


def build_home(art, chapters, md, total_audio, n_concepts):
    root = up(0)
    h = home(root)
    intro, secs = readme_sections(md)
    paths_md = secs.get(L("Learning paths", "مسیرهای یادگیری"), "")
    paths = []
    for m in re.finditer(r"^\*\*(.+?)\*\*(.*?)[:：]\s*(.+)$", paths_md, re.M):
        name, note, seq = m.group(1), m.group(2).strip(" ()"), m.group(3)
        nums = re.findall(r"\[(\d+)\]\((\d\d-[\w-]+)\.md", seq)
        if not nums:
            continue
        chips = "".join(f'<li><a href="{h}guide/{slug}.html" title="{attr(chapters[int(n)].title)}">{n}</a></li>' for n, slug in nums)
        paths.append(f'<div class="path"><h4>{esc(name)}</h4><p>{esc(note)}</p><ol>{chips}</ol></div>')
    n_c = num(n_concepts)
    head = hero(art, "home", root, kicker=L("A free course in the theory of knowledge", "دوره‌ای رایگان در نظریهٔ معرفت"),
                title=L("How do you know?", "از کجا می‌دانید؟"),
                lede=L(f"<b>{SITE}</b> is a complete guide to knowledge, evidence, and critical thinking: sixteen illustrated chapters, "
                       f"a bilingual map of {n_concepts} concepts, and {total_audio} of narrated audio.",
                       f"<b>{SITE_FA}</b> راهنمایی کامل دربارهٔ معرفت، شواهد و تفکر نقادانه است: شانزده فصلِ مصوّر، "
                       f"نقشهٔ دوزبانهٔ {n_c} مفهوم، و {total_audio} روایت صوتی{fa_audio('', ' به انگلیسی', ' به فارسی و انگلیسی')}."),
                facts=[f"{icon('book')} {L('16 chapters', '۱۶ فصل')}", f"{icon('map')} {L(f'{n_concepts} concepts · English &amp; فارسی', f'{n_c} مفهوم · فارسی و English')}",
                       f"{icon('phones')} {total_audio} {L('audio', 'صوت')}"],
                actions=(f'<a class="btn primary" href="{h}reading-path/">{L("Find my reading path", "مسیر مطالعه‌ام را پیدا کن")} {icon("arrow")}</a>'
                         f'<a class="btn" href="{h}guide/01-what-is-epistemology.html">{L("Start reading", "شروع خواندن")} {icon("arrow")}</a>'
                         f'<a class="btn" href="{map_url(root)}">{icon("map")} {L("Explore the map", "کاوش در نقشه")}</a>'
                         f'<a class="btn" href="{h}guide/audio/">{icon("phones")} {L("Listen", "شنیدن")}</a>'))
    doors = (f'<div class="doors">'
             + tile(art, "guide", root, f"{h}guide/", L("Read", "بخوانید"), L("The guide", "راهنما"),
                    L("Sixteen chapters, from the Gettier problem to Bayes' theorem, with worked examples and self-checks.",
                      "شانزده فصل، از مسئلهٔ گتیه تا قضیهٔ بیز، با مثال‌های حل‌شده و خودآزمایی."), cls="tile door")
             + tile(art, "map", root, map_url(root), L("Explore", "کاوش کنید"), L("The concept map", "نقشهٔ مفاهیم"),
                    L(f"{n_concepts} ideas as a living map you can pan and expand, in English and Persian, each with a full entry.",
                      f"{n_c} ایده در نقشه‌ای زنده که می‌توانید جابه‌جا و باز کنید، به فارسی و انگلیسی، هر یک با مدخلی کامل."), cls="tile door")
             + tile(art, "audio", root, f"{h}guide/audio/", L("Listen", "بشنوید"), L("The audio edition", "نسخهٔ صوتی"),
                    L(f"Every chapter narrated, {total_audio} in all, with section markers and a quiz after each chapter.",
                      f"همهٔ فصل‌ها روایت شده‌اند، روی‌هم {total_audio}{fa_audio('', ' به انگلیسی', ' به فارسی یا انگلیسی')}، با نشانگرِ بخش‌ها و آزمونکی در پایان هر فصل."), cls="tile door")
             + "</div>")
    stats = (f'<div class="statline"><div><b>{L("16", "۱۶")}</b><span>{L("chapters in five parts", "فصل در پنج بخش")}</span></div>'
             f'<div><b>{n_c}</b><span>{L("concepts, in English and Persian", "مفهوم، به فارسی و انگلیسی")}</span></div>'
             f'<div><b>{total_audio.split()[0]}</b><span>{L("hours of narration", "ساعت روایت صوتی")}</span></div><div><b>{L("200", "۲۰۰")}</b><span>{L("glossary terms", "اصطلاح در واژه‌نامه")}</span></div></div>')
    body = (f'{head}<main id="main">'
            f'<div class="wrap" id="rp-home" style="padding-top:28px"><a class="btn" href="{h}reading-path/">{L("A path built around your question →", "مسیری بر پایهٔ پرسش شما ←")}</a></div>'
            f'<section class="section"><div class="wrap"><div id="resume"></div><div class="section-head"><div><span class="kicker">{L("Three ways in", "سه راهِ ورود")}</span>'
            f'<h2>{L("Read it, map it, or hear it", "بخوانید، روی نقشه ببینید، یا بشنوید")}</h2></div><p>{L("The same ideas, three ways. Start wherever suits you; everything is cross-linked.", "همان ایده‌ها، از سه راه. از هر جا که مناسب شماست آغاز کنید؛ همه‌چیز به هم پیوند خورده است.")}</p></div>{doors}'
            f'<div style="margin-top:28px">{stats}</div></div></section>'
            + about_site(root) +
            f'<section class="section alt"><div class="wrap"><div class="section-head"><div><span class="kicker">{L("The course", "دوره")}</span>'
            f'<h2>{L("Sixteen chapters, each with a masterpiece", "شانزده فصل، هر یک با یک شاهکار")}</h2></div><p>'
            + L("Every chapter opens with a painting or photograph that captures its question, from Raphael's <i>School of Athens</i> to the <i>Earthrise</i> photograph.",
                "هر فصل با نقاشی یا عکسی آغاز می‌شود که پرسشِ آن را در خود دارد، از «مکتب آتن» رافائل تا عکسِ «طلوع زمین».")
            + f'</p></div>{contents_parts(art, chapters, root)}</div></section>'
            f'<section class="quoteband"><img src="{art.src("cave", root, 2000)}" alt="{attr(art.alt("cave"))}" loading="lazy">'
            f'<div class="wrap"><blockquote><p>'
            + L("“The duty of the man who investigates the writings of scientists, if learning the truth is his goal, is to make himself an enemy of all that he reads.”",
                "«وظیفهٔ کسی که نوشته‌های دانشمندان را می‌کاود، اگر هدفش شناختِ حقیقت است، این است که خود را دشمنِ هر آنچه می‌خوانَد کند.»")
            + f'</p><footer>{L("— Ibn al-Haytham, Doubts Concerning Ptolemy, c. 1025", "— ابن هیثم، «الشکوک علی بطلمیوس»، حدود ۱۰۲۵")}</footer></blockquote></div></section>'
            f'<section class="section"><div class="wrap"><div class="section-head"><div><span class="kicker">{L("Learning paths", "مسیرهای یادگیری")}</span>'
            f'<h2>{L("Short on time?", "وقت کمی دارید؟")}</h2></div><p>{L("Follow a path through the chapters that fits your goal.", "مسیری از میان فصل‌ها را دنبال کنید که با هدفتان جور است.")}</p></div><div class="paths">{"".join(paths)}</div></div></section>'
            f'</main>')
    return body


def about_site(root):
    """On the home page: what the site does, including what Google sign-in is for, with the privacy policy and terms."""
    h = home(root)
    items = [
        (L("Read, explore and listen", "بخوانید، کاوش کنید و بشنوید"),
         L("A free guide to knowledge, evidence and critical thinking: sixteen chapters with self-checks, a glossary, a map of the concepts in "
           "English and Persian, and every chapter narrated, to play here, offline, or in a podcast app.",
           "راهنمایی رایگان دربارهٔ معرفت، شواهد و تفکرِ نقادانه: شانزده فصل با خودآزمایی، واژه‌نامه، نقشهٔ مفاهیم به فارسی و انگلیسی، و "
           "روایتِ صوتیِ همهٔ فصل‌ها برای شنیدن در همین‌جا، بی‌اینترنت، یا در برنامهٔ پادکست.")),
        (L("Study tools", "ابزارهای مطالعه"),
         L("Highlights and notes, reading progress, spaced review questions, and an optional AI study companion that answers questions about "
           "the page you are reading, using your own Claude or ChatGPT API key. Everything works without an account and is kept in your browser.",
           "نشانه‌گذاری و یادداشت، پیشرفتِ خواندن، پرسش‌های مرورِ فاصله‌دار، و همراهِ هوشمندِ مطالعهٔ اختیاری که با کلیدِ API خودتان برای "
           "Claude یا ChatGPT به پرسش‌هایتان دربارهٔ صفحه‌ای که می‌خوانید پاسخ می‌دهد. همه‌چیز بدونِ حساب کار می‌کند و در مرورگرتان می‌ماند.")),
        (L("Optional Google sign-in", "ورودِ اختیاری با حساب گوگل"),
         L("Sign in with Google to keep your progress, notes, review deck and settings in sync across your devices. The site uses your name, "
           "email and picture only to show who is signed in, and saves your study data in a private app folder in your own Google Drive; "
           "it cannot see your other files. There is no server of ours, no ads and no tracking.",
           "با حساب گوگل وارد شوید تا پیشرفت، یادداشت‌ها، دستهٔ مرور و تنظیماتتان در همهٔ دستگاه‌هایتان هماهنگ بماند. سایت نام، ایمیل و "
           "تصویرتان را فقط برای نشان دادنِ حسابِ واردشده به کار می‌برد و داده‌های مطالعه را در پوشه‌ای خصوصی در گوگل‌درایوِ خودتان ذخیره "
           "می‌کند؛ پرونده‌های دیگرتان را نمی‌بیند. هیچ سروری از ما، هیچ تبلیغ و هیچ ردیابی‌ای در کار نیست.")),
    ]
    cards = "".join(f'<div class="about-item"><h3>{t}</h3><p>{p}</p></div>' for t, p in items)
    links = (f'<p class="about-links"><a href="{h}privacy.html">{L("Privacy policy", "سیاستِ حریم خصوصی")}</a>'
             f'<span aria-hidden="true">·</span><a href="{h}terms.html">{L("Terms of service", "شرایطِ استفاده")}</a>'
             f'<span aria-hidden="true">·</span><a href="{h}account/">{L("Sign in and sync", "ورود و همگام‌سازی")}</a></p>')
    lede = L(f"{SITE} is a free, open-source web app for learning epistemology and critical thinking.",
             f"{SITE_FA} وب‌سایتی رایگان و متن‌باز برای آموختنِ معرفت‌شناسی و تفکرِ نقادانه است.")
    return (f'<section class="section" id="about"><div class="wrap"><div class="section-head"><div><span class="kicker">{L("About this site", "دربارهٔ این سایت")}</span>'
            f'<h2>{L("What this site does", "این سایت چه می‌کند")}</h2></div><p>{lede}</p></div>'
            f'<div class="about-grid">{cards}</div>{links}</div></section>')


def audiobook_section(tracks, feed):
    """Three ways to take the audiobook along: saved in this browser, downloaded as a ZIP, or in a podcast app."""
    size = megabytes(sum(track_bytes(t) for t in tracks))
    feed = feed or LIVE + "guide/audio/feed.xml"
    partial = LANG == "fa" and FA_AUDIO and len(FA_TRACKS) < 16
    mixed = " فصل‌هایی که هنوز روایتِ فارسی ندارند، با روایتِ انگلیسی می‌آیند." if partial else ""
    growing = (f" این خوراک فعلاً {num(len(FA_TRACKS))} فصلِ روایت‌شده به فارسی را دارد و هر فصلِ تازه، همین‌که روایت شود، "
               "در برنامهٔ شما هم ظاهر می‌شود.") if partial else ""
    box = lambda ic, h, p, actions: (f'<div class="ab">{icon(ic)}<h3>{h}</h3><p>{p}</p>{actions}</div>')
    return (f'<section class="audiobook" id="audiobook" aria-labelledby="ab-h"><h2 id="ab-h">'
            f'{L("Take the audiobook with you", "کتاب صوتی را همراه داشته باشید")}</h2><div class="ab-grid">'
            + box("phones", L("Listen offline here", "شنیدنِ بی‌اینترنت در همین‌جا"),
                  L("Save the chapters in this browser; they then play on this page without a connection. "
                    "Single chapters can be saved from the list above.",
                    "فصل‌ها را در همین مرورگر ذخیره کنید تا در همین صفحه بدون اینترنت هم پخش شوند. "
                    "هر فصل را جداگانه هم می‌توانید از فهرستِ بالا ذخیره کنید.") + mixed,
                  f'<button type="button" class="btn" data-save-all hidden>{L("Save all chapters", "ذخیرهٔ همهٔ فصل‌ها")} ({size})</button>'
                  f'<p class="note" data-save-all-note hidden></p>')
            + box("download", L("Download the audiobook", "دریافتِ کتاب صوتی"),
                  L("Every chapter as an MP3 file, with a playlist, in one ZIP file for any music or audiobook app; each file carries "
                    "markers for its sections. For one chapter, use MP3 under Now playing.",
                    "همهٔ فصل‌ها به صورتِ فایل‌های MP3، همراه با فهرستِ پخش، در یک فایلِ ZIP، برای هر برنامهٔ موسیقی یا کتابِ صوتی؛ "
                    "هر فایل نشانگرِ بخش‌هایش را دارد. برای یک فصل، دکمهٔ MP3 را در کادرِ «در حال پخش» بزنید.") + mixed,
                  f'<button type="button" class="btn" data-zip>{L("Download ZIP", "دریافتِ ZIP")} ({size})</button>'
                  f'<p class="note" data-zip-note hidden></p>')
            + box("rss", L("In your podcast app", "در برنامهٔ پادکست"),
                  L("Subscribe to the audiobook's feed in Apple Podcasts, Pocket Casts, AntennaPod or any podcast app: it downloads the "
                    "chapters, plays them offline and remembers your place. In apps other than Apple Podcasts, choose to add a podcast "
                    "by its address and paste the feed address.",
                    "خوراکِ کتابِ صوتی را در Apple Podcasts، Pocket Casts، AntennaPod یا هر برنامهٔ پادکستِ دیگری دنبال کنید: برنامه فصل‌ها را "
                    "دریافت می‌کند، بی‌اینترنت پخش می‌کند و یادش می‌ماند تا کجا گوش داده‌اید. در برنامه‌های دیگر، گزینهٔ افزودنِ پادکست با "
                    "نشانی را بزنید و نشانیِ خوراک را بچسبانید.") + growing,
                  f'<div class="row"><a class="btn" href="podcast://{feed.split("://", 1)[1]}">{L("Open in Apple Podcasts", "باز کردن در Apple Podcasts")}</a>'
                  f'<button type="button" class="btn" data-copy="{feed}">{L("Copy the feed address", "کپیِ نشانیِ خوراک")}</button></div>'
                  f'<p class="note feed" dir="ltr">{feed}</p>')
            + '</div></section>')


def build_audio_page(art, chapters, tracks, feed=None):
    root = up(2)
    head = hero(art, "audio", root, kicker=L("The audio edition", "نسخهٔ صوتی"), title=L("Listen", "شنیدن"), cls="short",
                lede=L("Every chapter of the guide, narrated. Pick up where you left off, jump to any section, and change the speed. "
                       "Each chapter ends with a spoken quiz, with time to think.",
                       f"همهٔ فصل‌های راهنما، روایت‌شده به زبان {fa_audio('فارسی', 'انگلیسی', f'فارسی ({num(len(FA_TRACKS))} فصل تا اینجا؛ فصل‌های دیگر فعلاً به انگلیسی)')}. از همان‌جا که ماندید ادامه دهید، به هر بخش بپرید و سرعت را تغییر دهید. "
                       "هر فصل با آزمونکی شفاهی پایان می‌یابد که فرصتِ فکرکردن می‌دهد."),
                facts=[f"{icon('phones')} {minutes_label(sum(t['duration'] for t in tracks))}", L("16 chapters", "۱۶ فصل"),
                       L("MP3 with chapter markers", "MP3 با نشانگرِ فصل‌ها")])
    def title(t):
        if LANG == "en":
            return t["title"]
        ch = chapters[int(t["file"][:2])]
        return f"{ch.label} — {ch.title}" + ("" if t.get("fa") or not FA_AUDIO else " (به انگلیسی)")
    data = [{"file": ("" if LANG == "en" else audio_dir(root, t)) + t["file"], "title": title(t),
             "duration": t["duration"], "size": track_bytes(t), "page": f"../{t['text'][3:].replace('.md', '.html')}", "sections": t["sections"],
             "readalong": (f"../listen/{t['file'][:-4]}.html" if chapter_sync(chapters[int(t["file"][:2])]) else "")} for t in tracks]
    thumbs = [art.src(f"ch{i + 1:02d}", root, 640) for i in range(len(tracks))]
    body = (f'{head}<main id="main" class="wrap" style="padding-bottom:80px">'
            f'<section class="player" id="player" aria-label="{L("Player", "پخش‌کننده")}"><span class="kicker" style="color:var(--accent)">{L("Now playing", "در حال پخش")}</span>'
            f'<h2>{L("Choose a chapter", "یک فصل انتخاب کنید")}</h2><div class="sec"></div><audio controls preload="metadata"></audio>'
            f'<div class="ctl" dir="ltr"><button id="prev" type="button">⏮ {L("Chapter", "فصل")}</button><button id="back" type="button">↺ 15 s</button>'
            f'<button id="fwd" type="button">30 s ↻</button><button id="next" type="button">{L("Chapter", "فصل")} ⏭</button>'
            f'<label>{L("Speed", "سرعت")} <select id="rate"><option>0.8</option><option>0.9</option><option selected>1</option><option>1.1</option>'
            f'<option>1.25</option><option>1.5</option><option>1.75</option></select></label>'
            f'<a class="btn" id="read" href="../01-what-is-epistemology.html" style="min-height:40px">{icon("book")} {L("Read this chapter", "خواندن این فصل")}</a>'
            f'<a class="btn" id="ra" href="" hidden style="min-height:40px">{L("Read along", "خواندن همراه با صدا")}</a>'
            f'<a class="btn" id="dl" href="" download style="min-height:40px" title="{L("Download this chapter as an MP3 file", "دریافتِ این فصل به صورتِ فایلِ MP3")}">{icon("download")} MP3</a></div></section>'
            f'<div class="tracks"><section><h2 class="kicker" style="color:var(--dim)">{L("Chapters", "فصل‌ها")}</h2><ol id="chapters"></ol></section>'
            f'<section class="secs"><h2 class="kicker" style="color:var(--dim)">{L("Sections in this chapter", "بخش‌های این فصل")}</h2><ol id="sections"></ol></section></div>'
            + audiobook_section(tracks, feed) +
            f'<p style="color:var(--dim);font-size:.95rem;margin-top:30px">'
            + L(re.sub(r"<[^>]+>", "", en_voices_credit()) + 'The scripts are adapted for listening. '
                '<a href="about.html">How the audio was made</a>. Keyboard: <kbd>k</kbd> or space to play and pause, <kbd>j</kbd> and <kbd>l</kbd> to skip.',
                fa_audio(f'روایت با صداهای ساختگی ({fa_engines_phrase()})، از متن‌هایی ساخته شده که برای شنیدن بازنویسی شده‌اند. ',
                         'روایت با صدایی ساختگی، با مدلِ متن‌به‌گفتارِ متن‌باز Kokoro-82M، از متن‌هایی ساخته شده که برای شنیدن بازنویسی شده‌اند. '
                         'این مدل صدای فارسی ندارد، به همین دلیل روایت به زبان انگلیسی است. ',
                         f'روایت با صداهای ساختگی ({fa_engines_phrase()})، از متن‌هایی ساخته شده که برای شنیدن بازنویسی شده‌اند. '
                         'روایتِ فارسی فصل‌به‌فصل آماده می‌شود؛ تا آن زمان فصل‌های دیگر با روایتِ انگلیسیِ مدلِ Kokoro-82M پخش می‌شوند. ')
                + '<a href="about.html">صوت چگونه ساخته شد</a>. '
                'صفحه‌کلید: <kbd>k</kbd> یا فاصله برای پخش و توقف، <kbd>j</kbd> و <kbd>l</kbd> برای جابه‌جایی.')
            + '</p></main>'
            f'<script>window.TRACKS={json.dumps(data, ensure_ascii=False)};window.TRACK_ART={json.dumps(thumbs)};</script>')
    return body


def build_download_page(art, chapters, tracks, feed):
    """Everything to take away, in one place (linked from the main menu): the audiobook (offline, ZIP,
    podcast), each chapter's MP3 and read-along EPUB, the guide as an EPUB, and offline reading."""
    root = up(1)
    head = hero(art, "audio", root, kicker=L("Take it with you", "همراه داشته باشید"), title=L("Download", "دریافت"), cls="short",
                lede=L("The audiobook, the e-book and offline reading, in one place.",
                       "کتاب صوتی، کتاب الکترونیکی و خواندنِ بی‌اینترنت، یک‌جا."))
    epub = EPUB_NAME_FA if LANG == "fa" else EPUB_NAME
    data = []
    for t in tracks:
        ch = chapters[int(t["file"][:2])]
        data.append({"file": audio_dir(root, t) + t["file"], "title": f"{ch.label} — {ch.title}", "duration": t["duration"],
                     "size": track_bytes(t), "page": ch.href, "epub": f"epub/{ch.slug}/files.json" if chapter_sync(ch) else ""})
    has_ra = any(d["epub"] for d in data)
    ra_text = L("One EPUB per chapter, with the audio inside: the text is highlighted as it is read (EPUB 3 read-aloud), "
                "and a player at the start of the chapter plays it in any reader. Choose EPUB next to a chapter below.",
                "برای هر فصل یک EPUB که صدا هم در آن است: متن همراهِ خواندن نشان داده می‌شود (خواندنِ همراه با صدای EPUB 3) "
                "و در آغازِ فصل پخش‌کننده‌ای هست که در هر کتاب‌خوانی صدا را پخش می‌کند. دکمهٔ EPUB را کنارِ هر فصل در پایین بزنید.")
    ebook = (f'<section class="dl-sec" aria-labelledby="dl-eb"><h2 id="dl-eb">{L("The e-book", "کتاب الکترونیکی")}</h2>'
             f'<div class="ab-grid"><div class="ab">{icon("book")}<h3>{L("The guide as an EPUB", "راهنما به صورت EPUB")}</h3>'
             f'<p>{L("Every chapter, for Apple Books, Kobo, Thorium, Calibre or any e-reader.", "همهٔ فصل‌ها، برای Apple Books، کوبو، Thorium، Calibre یا هر کتاب‌خوانِ دیگر.")}</p>'
             f'<a class="btn" href="{epub}" download>{icon("download")} {L("Download EPUB", "دریافتِ EPUB")}</a></div>'
             + (f'<div class="ab">{icon("phones")}<h3>{L("Chapters with their narration", "فصل‌ها همراه با روایت")}</h3>'
                f'<p>{ra_text}</p><p class="note" data-epub-note hidden></p></div>' if has_ra else "")
             + f'<div class="ab">{icon("save")}<h3>{L("Read without a connection", "خواندنِ بی‌اینترنت")}</h3>'
               f'<p>{L("Save the whole site in this browser: the guide, the concepts and the map then open offline.", "کلِ سایت را در همین مرورگر ذخیره کنید تا راهنما، مفاهیم و نقشه بدون اینترنت هم باز شوند.")}</p>'
               f'<button type="button" class="btn" data-offline-page>{L("Save for offline reading", "ذخیره برای خواندنِ بی‌اینترنت")}</button>'
               f'<p class="note" data-offline-page-note hidden></p></div></div></section>')
    listing = (f'<section class="dl-sec" aria-labelledby="dl-ch"><h2 id="dl-ch">{L("Chapter by chapter", "فصل به فصل")}</h2>'
               f'<p class="dl-legend">{L("Save a chapter for offline listening here, download its MP3", "هر فصل را برای شنیدنِ بی‌اینترنت در همین‌جا ذخیره کنید، MP3 آن را دریافت کنید")}'
               f'{L(", or its EPUB with the narration.", " یا EPUBِ همراه با روایتش را.") if has_ra else L(".", ".")}</p><ol class="dl-list" id="dl-list"></ol></section>')
    other = (f'<p class="dl-other">{L("The narration in Persian is on the ", "روایتِ انگلیسی در ")}'
             f'<a href="{L("../fa/guide/download.html", "../../guide/download.html")}" lang="{L("fa", "en")}">{L("Persian download page", "صفحهٔ دریافتِ انگلیسی")}</a>'
             f'{L(".", " است.")}</p>')
    return (f'{head}<main id="main" class="wrap dl-page" style="padding-bottom:80px">'
            + audiobook_section(tracks, feed) + ebook + listing + other + '</main>'
            f'<script>window.TRACKS={json.dumps(data, ensure_ascii=False)};</script>')


def build_audio_about(art, md):
    root = up(2)
    if LANG == "fa":
        src = GUIDE / "fa" / "audio" / "README.md" if FA_AUDIO else SRC() / "audio-README.md"
    else:
        src = GUIDE / "audio" / "README.md"
    text = src.read_text(encoding="utf-8")
    text = re.sub(r"^# .*\n", "", text)

    def links(href):
        if href == "index.html":
            return "./"
        if href == "../../audio/README.md":  # from the Persian audio notes to the English ones
            return f"{root}guide/audio/about.html"
        if href.endswith(".mp3"):
            return href if LANG == "en" else f"{root}guide/{'fa/' if FA_AUDIO else ''}audio/{href}"
        if href.startswith(("scripts/", "tools/", "transcripts/", "sync/")):
            return f"{REPO}/tree/main/guide/{'fa/' if LANG == 'fa' and FA_AUDIO else ''}audio/{href}"
        return href
    body_html, heads = md.render(text, links)
    head = hero(art, "audio", root, kicker=L("The audio edition", "نسخهٔ صوتی"), title=L("How the audio was made", "صوت چگونه ساخته شد"), cls="band")
    return (f'{head}<main id="main" class="wrap" style="padding-top:36px;padding-bottom:80px">'
            f'<div class="prose" style="max-width:46rem;margin:0 auto">{polish(body_html)}</div></main>')


def build_credits(art):
    root = up(0)
    cards = []
    for key, i in art.info.items():
        if not art.has(key):
            continue
        c = art.credits.get(key, {})
        src = c.get("source") or ""
        meta = art.meta(key)
        place = f" {esc(meta['place'])}." if meta.get("place") else ""
        lic = c.get("license") or "Public domain"
        if LANG == "fa" and lic.lower().startswith("public domain"):
            lic = "مالکیت عمومی"
        cards.append(f'<div class="credit"><img src="{art.src(key, root, 640)}" alt="" loading="lazy"><div><b>{art.caption(key)}</b>'
                     f'<p>{place.strip()} {esc(lic)}{L(", via ", "، از ")}'
                     f'<a href="{attr(src)}" rel="noopener">{L("Wikimedia Commons", "ویکی‌انبار")}</a>.</p></div></div>')
    head = hero(art, "ch18", root, kicker=L("Credits", "منابع"), title=L("Artwork, sound and type", "آثار هنری، صدا و حروف"), cls="band")
    faces = [("Cormorant Garamond", "cormorant-garamond"), ("Source Serif 4", "source-serif-4"), ("Space Grotesk", "space-grotesk"),
             ("IBM Plex Mono", "ibm-plex-mono"), ("Vazirmatn", "vazirmatn"), ("Noto Naskh Arabic", "noto-naskh-arabic"),
             ("Atkinson Hyperlegible", "atkinson-hyperlegible")]
    names = [f'<a href="{root}assets/fonts/licenses/{slug}-OFL.txt">{name}</a>' for name, slug in faces]
    fonts = L(", ".join(names[:-1]) + " and " + names[-1], "، ".join(names[:-1]) + " و " + names[-1])
    audio = f"{home(root)}guide/audio/about.html"
    body = (f'{head}<main id="main" class="wrap" style="padding-top:36px;padding-bottom:80px"><div class="prose" style="max-width:46rem">'
            + L('<p class="lede">The paintings, prints and photographs on this site are in the public domain. The images come from Wikimedia Commons; '
                'follow each link for the source file and its description.</p>',
                '<p class="lede">نقاشی‌ها، چاپ‌ها و عکس‌های این سایت در مالکیت عمومی‌اند. تصاویر از ویکی‌انبار آمده‌اند؛ '
                'برای دیدنِ پروندهٔ اصلی و توضیحِ آن، پیوندِ هر مورد را دنبال کنید.</p>')
            + f'</div><div class="credits">{"".join(cards)}</div>'
            f'<div class="prose" style="max-width:46rem;margin-top:40px"><h2>{L("Sound", "صدا")}</h2><p>'
            + L(f'{en_voices_credit()}See <a href="{audio}">how the audio was made</a>.',
                fa_audio(fa_voices_credit(), '') + en_voices_credit() + f'<a href="{audio}">صوت چگونه ساخته شد</a> را ببینید.')
            + f'</p><h2>{L("Type", "حروف")}</h2><p>{fonts}{L(", all under the SIL Open Font License (follow a name for its licence).", "؛ همه با مجوزِ SIL Open Font License (برای دیدنِ مجوز، روی نام کلیک کنید).")}</p></div></main>')
    return body


POLICY_DATE = ("30 September 2026", "۳۰ سپتامبر ۲۰۲۶ (۸ مهر ۱۴۰۵)")
ISSUES = REPO + "/issues"


def legal_page(art, root, kicker, title, sections, rel):
    """A plain page of numbered sections: [(heading, html)], in the language being built (rel: its path)."""
    head = hero(art, "ch18", root, kicker=kicker, title=title, cls="band")
    toc = "".join(f'<li><a href="#s{i}">{h}</a></li>' for i, (h, _) in enumerate(sections, 1))
    body = "".join(f'<h2 id="s{i}">{h}</h2>{html_}' for i, (h, html_) in enumerate(sections, 1))
    policy_date = ("2 October 2026", "۲ اکتبر ۲۰۲۶ (۱۰ مهر ۱۴۰۵)") if rel == "privacy.html" else POLICY_DATE
    date = L(f"Last updated: {policy_date[0]}", f"آخرین به‌روزرسانی: {policy_date[1]}")
    note = ("" if LANG == "en" else
            f'<p class="note">این ترجمهٔ فارسیِ متنِ انگلیسی است؛ اگر میانِ دو متن اختلافی باشد، <a href="../{rel}" lang="en">متنِ انگلیسی</a> '
            'ملاک است.</p>')
    return (f'{head}<main id="main" class="wrap" style="padding-top:36px;padding-bottom:80px"><div class="prose" style="max-width:46rem">'
            f'<p class="note"><b>{date}</b></p>{note}<nav aria-label="{L("On this page", "در این صفحه")}"><ol>{toc}</ol></nav>{body}</div></main>')


def build_privacy(art):
    root = up(0)
    h = home(root)
    signin = f'<a href="{h}account/">{L("My study", "مطالعهٔ من")}</a>'
    return legal_page(art, root, L("Privacy", "حریم خصوصی"), L("Privacy policy", "سیاستِ حریم خصوصی"), [
        (L("Who we are", "ما که هستیم"),
         L(f"<p><b>{SITE}</b> (<a href=\"{LIVE}\">{LIVE}</a>, in English and Persian) is a free, open-source guide to epistemology and critical "
           f"thinking: sixteen chapters, a concept map, an audio edition, and optional study tools. It is a static website hosted on GitHub Pages. "
           f"We run no server of our own, and we (the site's author) never receive your personal data. The source code is public on "
           f"<a href=\"{REPO}\">GitHub</a>, so you can check everything this page says.</p>",
           f"<p><b>{SITE_FA}</b> (<a href=\"{LIVE}fa/\">{LIVE}fa/</a>، به فارسی و انگلیسی) راهنمایی رایگان و متن‌باز دربارهٔ معرفت‌شناسی و تفکرِ نقادانه است: "
           f"شانزده فصل، نقشهٔ مفاهیم، نسخهٔ صوتی و ابزارهای اختیاریِ مطالعه. این سایتی ایستا است که روی GitHub Pages میزبانی می‌شود. "
           f"ما هیچ سروری نداریم و ما (نویسندهٔ سایت) هرگز داده‌های شخصیِ شما را دریافت نمی‌کنیم. کدِ منبع در "
           f"<a href=\"{REPO}\">گیت‌هاب</a> عمومی است، پس می‌توانید درستیِ همهٔ آنچه در این صفحه آمده را خودتان وارسی کنید.</p>")),
        (L("In short", "به‌طورِ خلاصه"),
         L("<ul><li>You can use the whole site without an account.</li>"
           "<li>There are no ads, no analytics, no tracking cookies, and no third-party trackers.</li>"
           "<li>If you sign in with Google, your study data is saved in a private app folder in <i>your own</i> Google Drive, which only this site "
           "can open. It is not sent to us or to anyone else.</li>"
           "<li>We do not sell, rent or share personal data, and we do not use it for advertising.</li></ul>",
           "<ul><li>همهٔ سایت را بدونِ حساب کاربری می‌توانید به کار ببرید.</li>"
           "<li>هیچ تبلیغ، آمارگیری، کوکیِ ردیابی یا ردیابِ شخصِ ثالثی در کار نیست.</li>"
           "<li>اگر با حساب گوگل وارد شوید، داده‌های مطالعه‌تان در پوشه‌ای خصوصی در گوگل‌درایوِ <i>خودتان</i> ذخیره می‌شود که فقط همین سایت "
           "می‌تواند بازش کند. این داده‌ها نه برای ما فرستاده می‌شوند و نه برای کسِ دیگری.</li>"
           "<li>ما داده‌های شخصی را نمی‌فروشیم، اجاره نمی‌دهیم، با کسی در میان نمی‌گذاریم و برای تبلیغ به کار نمی‌بریم.</li></ul>")),
        (L("What stays in your browser", "آنچه در مرورگرِ شما می‌ماند"),
         L("<p>So that you can pick up where you left off, the site stores these in your browser's local storage: your reading progress, "
           "highlights and notes, your review deck, your reading and theme settings, your AI study companion settings and chats, and, if you choose "
           "to save them, chapters and audio for offline use. This data stays on your device. You can remove it at any time by clearing this "
           "site's data in your browser settings.</p>"
           "<p>The reading-path questionnaire also saves your question, answers, reading path and completed steps in this browser. "
           "These are not included in Google Drive sync. Use “Forget this path” on the reading-path page to delete them.</p>",
           "<p>برای اینکه بتوانید از همان‌جا که ماندید ادامه دهید، سایت این‌ها را در حافظهٔ محلیِ مرورگرتان نگه می‌دارد: پیشرفتِ خواندن، "
           "نشانه‌گذاری‌ها و یادداشت‌ها، دستهٔ مرور، تنظیماتِ خواندن و ظاهر، تنظیمات و گفت‌وگوهای همراهِ هوشمندِ مطالعه، و اگر خودتان بخواهید، "
           "فصل‌ها و صوت برای استفادهٔ بی‌اینترنت. این داده‌ها روی دستگاهِ شما می‌مانند و هر وقت بخواهید، با پاک کردنِ دادهٔ این سایت در "
           "تنظیماتِ مرورگر، حذف می‌شوند.</p>"
           "<p>پرسش‌نامهٔ مسیرِ مطالعه نیز پرسش، پاسخ‌ها، مسیر و گام‌های تکمیل‌شده را در همین مرورگر نگه می‌دارد. این داده‌ها با گوگل‌درایو "
           "همگام نمی‌شوند. برای حذفشان، در صفحهٔ مسیرِ مطالعه «Forget this path» را بزنید.</p>")),
        (L("Google sign-in (optional)", "ورود با حساب گوگل (اختیاری)"),
         L(f"<p>Signing in (on {signin}) lets your study data follow you to other browsers and devices. Sign-in uses Google's OAuth 2.0 in your "
           "browser and asks for these permissions:</p><ul>"
           "<li><b>Your name, email address and profile picture</b> (the <code>openid</code>, <code>email</code> and <code>profile</code> scopes), "
           "used only to show which account is signed in. They are kept in your browser.</li>"
           "<li><b>A private app folder in your Google Drive</b> (the <code>drive.appdata</code> scope), used to create, read and update one "
           "file, <code>epis-sync.json</code>, that holds the study data listed above. This folder is hidden and separate from your files: "
           "the site cannot see, open or change any other file in your Drive.</li></ul>"
           "<p>Your browser talks to Google directly. The access token Google issues is short-lived, is kept in your browser, and is sent only "
           "to Google's servers. Your profile picture is loaded from Google. We never see your Google data, your token or your synced file.</p>"
           "<p>The use and transfer of information received from Google APIs by this site adheres to the "
           "<a href=\"https://developers.google.com/terms/api-services-user-data-policy\">Google API Services User Data Policy</a>, including "
           "the Limited Use requirements. Google user data is used only to provide the sign-in and sync features described here; it is not "
           "used for advertising, not sold, not transferred to anyone, and not read by any person.</p>",
           f"<p>ورود (در صفحهٔ {signin}) باعث می‌شود داده‌های مطالعه‌تان در مرورگرها و دستگاه‌های دیگر هم همراهتان باشد. ورود با OAuth 2.0ِ گوگل "
           "در خودِ مرورگرتان انجام می‌شود و این اجازه‌ها را می‌خواهد:</p><ul>"
           "<li><b>نام، نشانیِ ایمیل و تصویرِ نمایه</b> (دامنه‌های <code>openid</code>، <code>email</code> و <code>profile</code>)، فقط برای "
           "اینکه نشان داده شود کدام حساب وارد شده است. این‌ها در مرورگرِ شما می‌مانند.</li>"
           "<li><b>یک پوشهٔ خصوصیِ برنامه در گوگل‌درایوِ شما</b> (دامنهٔ <code>drive.appdata</code>)، برای ساختن، خواندن و به‌روز کردنِ یک "
           "پرونده، <code>epis-sync.json</code>، که داده‌های مطالعهٔ بالا را نگه می‌دارد. این پوشه پنهان و جدا از پرونده‌های شماست: سایت هیچ "
           "پروندهٔ دیگری را در درایوتان نمی‌بیند، باز نمی‌کند و تغییر نمی‌دهد.</li></ul>"
           "<p>مرورگرِ شما مستقیم با گوگل گفت‌وگو می‌کند. توکنِ دسترسی‌ای که گوگل می‌دهد کوتاه‌عمر است، در مرورگرِ شما می‌ماند و فقط به "
           "سرورهای گوگل فرستاده می‌شود. تصویرِ نمایه‌تان از گوگل بارگذاری می‌شود. ما هرگز داده‌های گوگلِ شما، توکن یا پروندهٔ همگام‌سازی‌تان را نمی‌بینیم.</p>"
           "<p>استفاده و انتقالِ اطلاعاتی که این سایت از APIهای گوگل دریافت می‌کند، از "
           "<a href=\"https://developers.google.com/terms/api-services-user-data-policy\">سیاستِ دادهٔ کاربرانِ خدماتِ API گوگل</a>، از جمله "
           "الزام‌های «استفادهٔ محدود»، پیروی می‌کند. دادهٔ کاربرانِ گوگل فقط برای ورود و همگام‌سازی‌ای که اینجا شرح داده شد به کار می‌رود؛ "
           "برای تبلیغ به کار نمی‌رود، فروخته نمی‌شود، به کسی منتقل نمی‌شود و هیچ انسانی آن را نمی‌خواند.</p>")),
        (L("Removing your data and access", "حذفِ داده‌ها و دسترسی"),
         L("<ul><li><b>Sign out</b> on the My study page: this revokes the site's access token and removes your profile and AI keys from the browser.</li>"
           "<li><b>Delete the synced file</b>: in Google Drive, open Settings, then Manage apps, find this site's app, and choose "
           "“Delete hidden app data”.</li>"
           "<li><b>Remove the site's access to your Google account</b> at any time at "
           "<a href=\"https://myaccount.google.com/permissions\">myaccount.google.com/permissions</a>.</li>"
           "<li><b>Clear the data in your browser</b> by clearing this site's data in your browser settings.</li></ul>",
           "<ul><li><b>خروج</b> در صفحهٔ «مطالعهٔ من»: توکنِ دسترسیِ سایت باطل می‌شود و نمایه و کلیدهای هوش مصنوعی از مرورگر پاک می‌شوند.</li>"
           "<li><b>حذفِ پروندهٔ همگام‌سازی</b>: در گوگل‌درایو، «تنظیمات» و بعد «مدیریتِ برنامه‌ها» را باز کنید، برنامهٔ این سایت را پیدا کنید و "
           "«حذفِ دادهٔ پنهانِ برنامه» را بزنید.</li>"
           "<li><b>برداشتنِ دسترسیِ سایت به حساب گوگلتان</b>، هر وقت بخواهید، در "
           "<a href=\"https://myaccount.google.com/permissions\">myaccount.google.com/permissions</a>.</li>"
           "<li><b>پاک کردنِ داده‌ها در مرورگر</b> با پاک کردنِ دادهٔ این سایت در تنظیماتِ مرورگر.</li></ul>")),
        (L("The AI study companion (optional)", "همراهِ هوشمندِ مطالعه (اختیاری)"),
         L("<p>The chat panel can answer questions about the page you are reading. If you add your own API key for Anthropic (Claude), OpenAI "
           "(ChatGPT), OpenRouter or another OpenAI-compatible service, your browser sends your questions, the chat so far and the text of the "
           "page you are reading directly to that provider, and that provider's privacy policy and terms apply to them. Your key is stored in "
           "your browser and, if you are signed in, in your own Drive sync file; it is sent only to the provider it belongs to.</p>"
           "<p>Without a key, the panel can prepare your question for you to paste into the ChatGPT or Claude website yourself. If a free "
           "on-page assistant is offered, the service answering is named in the chat panel, and your questions and the page text are sent "
           "to it. Please do not enter sensitive personal information in the chat.</p>"
           "<p>If the optional AI reading-path interview is enabled, it runs only when you choose it. Your question and study mode "
           "are sent to the AI service named beside that option to suggest a follow-up question. That provider’s privacy policy applies. "
           "The curated questionnaire works without sending those answers to an AI service.</p>",
           "<p>کادرِ گفت‌وگو می‌تواند به پرسش‌هایتان دربارهٔ صفحه‌ای که می‌خوانید پاسخ دهد. اگر کلیدِ API خودتان را برای Anthropic (Claude)، "
           "OpenAI (ChatGPT)، OpenRouter یا خدمتِ سازگارِ دیگری وارد کنید، مرورگرتان پرسش‌ها، گفت‌وگوی تا آن لحظه و متنِ صفحه‌ای را که "
           "می‌خوانید مستقیم برای همان خدمت می‌فرستد، و سیاستِ حریم خصوصی و شرایطِ همان خدمت دربارهٔ آن‌ها صدق می‌کند. کلیدتان در مرورگرتان و، "
           "اگر وارد شده باشید، در پروندهٔ همگام‌سازیِ درایوِ خودتان نگه داشته می‌شود و فقط برای خدمتی فرستاده می‌شود که کلید از آنِ آن است.</p>"
           "<p>بدونِ کلید، کادرِ گفت‌وگو می‌تواند پرسشتان را آماده کند تا خودتان آن را در وب‌سایتِ ChatGPT یا Claude بچسبانید. اگر دستیارِ "
           "رایگانی روی همین صفحه در دسترس باشد، نامِ خدمتی که پاسخ می‌دهد در کادرِ گفت‌وگو آمده است و پرسش‌ها و متنِ صفحه برای آن فرستاده "
           "می‌شود. لطفاً اطلاعاتِ شخصیِ حساس را در گفت‌وگو ننویسید.</p>"
           "<p>اگر مصاحبهٔ هوشمندِ مسیرِ مطالعه فعال باشد، فقط با انتخاب شما اجرا می‌شود. پرسش و شیوهٔ مطالعهٔ شما برای پیشنهادِ "
           "پرسشِ بعدی به خدمتی فرستاده می‌شود که نامش کنارِ آن گزینه آمده است؛ سیاستِ حریم خصوصیِ همان خدمت صدق می‌کند. "
           "پرسش‌نامهٔ ازپیش‌تنظیم‌شده بدونِ فرستادنِ این پاسخ‌ها به هوش مصنوعی کار می‌کند.</p>")),
        (L("Hosting", "میزبانی"),
         L("<p>GitHub Pages serves this site's files. Like any web host, GitHub may process technical data such as your IP address when your "
           "browser requests a page; see the <a href=\"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement\">"
           "GitHub General Privacy Statement</a>. Fonts, images and audio are served from this site itself, not from other services.</p>",
           "<p>پرونده‌های این سایت را GitHub Pages ارائه می‌کند. مانندِ هر میزبانِ وب، گیت‌هاب ممکن است وقتی مرورگرتان صفحه‌ای را درخواست "
           "می‌کند، داده‌های فنی‌ای مانندِ نشانیِ IP را پردازش کند؛ "
           "<a href=\"https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement\">بیانیهٔ حریم خصوصیِ گیت‌هاب</a> "
           "را ببینید. قلم‌ها، تصویرها و صوت از خودِ همین سایت ارائه می‌شوند، نه از خدماتِ دیگر.</p>")),
        (L("Children", "کودکان"),
         L("<p>The site is an educational resource for a general audience and is not directed at children under 13. We do not knowingly "
           "collect personal information from children.</p>",
           "<p>این سایت منبعی آموزشی برای عمومِ مخاطبان است و برای کودکانِ زیرِ ۱۳ سال طراحی نشده است. ما آگاهانه اطلاعاتِ شخصیِ کودکان را "
           "گردآوری نمی‌کنیم.</p>")),
        (L("Changes to this policy", "تغییرِ این سیاست"),
         L("<p>If this policy changes, the new version will be posted on this page with a new date. The history of every change is public "
           f"in the site's <a href=\"{REPO}\">source repository</a>.</p>",
           "<p>اگر این سیاست تغییر کند، نسخهٔ تازه با تاریخِ تازه در همین صفحه منتشر می‌شود. تاریخچهٔ همهٔ تغییرها در "
           f"<a href=\"{REPO}\">مخزنِ کدِ منبعِ سایت</a> عمومی است.</p>")),
        (L("Contact", "تماس"),
         L(f"<p>Questions about privacy, or a request about your data: please open an issue at <a href=\"{ISSUES}\">{ISSUES}</a>.</p>",
           f"<p>برای پرسش دربارهٔ حریم خصوصی یا درخواستی دربارهٔ داده‌هایتان، لطفاً در <a href=\"{ISSUES}\">{ISSUES}</a> یک issue باز کنید.</p>")),
    ], "privacy.html")


def build_terms(art):
    root = up(0)
    h = home(root)
    privacy = f'<a href="{h}privacy.html">{L("Privacy policy", "سیاستِ حریم خصوصی")}</a>'
    return legal_page(art, root, L("Terms", "شرایط"), L("Terms of service", "شرایطِ استفاده"), [
        (L("Agreement", "پذیرش"),
         L(f"<p>These terms apply to your use of <b>{SITE}</b> at <a href=\"{LIVE}\">{LIVE}</a>, in English and Persian (the “site”). By "
           f"using the site you agree to them. How the site handles your data is described in the {privacy}, which is part of these terms.</p>",
           f"<p>این شرایط دربارهٔ استفادهٔ شما از <b>{SITE_FA}</b> در <a href=\"{LIVE}\">{LIVE}</a>، به فارسی و انگلیسی («سایت»)، صدق می‌کند. "
           f"با استفاده از سایت این شرایط را می‌پذیرید. شیوهٔ رفتارِ سایت با داده‌هایتان در {privacy} آمده است که بخشی از همین شرایط است.</p>")),
        (L("The service", "خدمت"),
         L("<p>The site is a free educational resource: a guide to epistemology and critical thinking, a concept map, a narrated audio "
           "edition, and optional study tools (progress, notes, review questions, Google sign-in and sync, and an AI study companion). It is "
           "provided free of charge, and features may change or be withdrawn at any time.</p>",
           "<p>سایت منبعی آموزشیِ رایگان است: راهنمایی دربارهٔ معرفت‌شناسی و تفکرِ نقادانه، نقشهٔ مفاهیم، نسخهٔ صوتیِ روایت‌شده و ابزارهای "
           "اختیاریِ مطالعه (پیشرفت، یادداشت‌ها، پرسش‌های مرور، ورود با گوگل و همگام‌سازی، و همراهِ هوشمندِ مطالعه). سایت رایگان ارائه می‌شود "
           "و ویژگی‌هایش ممکن است هر زمان تغییر کنند یا برداشته شوند.</p>")),
        (L("Your Google account", "حساب گوگلِ شما"),
         L("<p>Signing in is optional. When you sign in with Google, you remain responsible for your Google account and bound by Google's "
           "terms. Your synced study data is stored in your own Google Drive, and you can delete it and revoke the site's access at any time, "
           f"as the {privacy} explains.</p>",
           "<p>ورود اختیاری است. وقتی با حساب گوگل وارد می‌شوید، مسئولیتِ حساب گوگلتان با خودتان است و شرایطِ گوگل درباره‌اش صدق می‌کند. "
           f"داده‌های همگام‌شدهٔ مطالعه‌تان در گوگل‌درایوِ خودتان ذخیره می‌شود و هر وقت بخواهید، می‌توانید آن را حذف کنید و دسترسیِ سایت را بردارید؛ "
           f"{privacy} شیوه‌اش را توضیح می‌دهد.</p>")),
        (L("The AI study companion", "همراهِ هوشمندِ مطالعه"),
         L("<p>If you use your own API key with Anthropic, OpenAI, OpenRouter or another provider, you use that provider's service under "
           "its terms, and any charges it makes are yours. Keep your keys private. AI answers can be wrong or incomplete: check them against "
           "the guide and other sources, and do not rely on them for medical, legal, financial or other professional advice.</p>",
           "<p>اگر کلیدِ API خودتان را با Anthropic، OpenAI، OpenRouter یا خدمتِ دیگری به کار ببرید، از خدمتِ آن شرکت طبقِ شرایطِ خودش "
           "استفاده می‌کنید و هزینه‌هایی که می‌گیرد بر عهدهٔ شماست. کلیدهایتان را پنهان نگه دارید. پاسخ‌های هوش مصنوعی ممکن است نادرست یا "
           "ناقص باشند: آن‌ها را با راهنما و منابعِ دیگر بسنجید و برای مشاورهٔ پزشکی، حقوقی، مالی یا هر مشاورهٔ تخصصیِ دیگری به آن‌ها "
           "تکیه نکنید.</p>")),
        (L("Content and copyright", "محتوا و حقِ نشر"),
         L(f"<p>The guide's text belongs to its author. You are welcome to read it, link to it, and quote short passages with a link to the "
           f"source. The artwork is in the public domain, the fonts are under the SIL Open Font License, and the audio is narrated by synthetic "
           f"voices; see the <a href=\"{h}credits.html\">credits</a>. The source code is published on <a href=\"{REPO}\">GitHub</a>.</p>",
           f"<p>متنِ راهنما از آنِ نویسنده‌اش است. می‌توانید آن را بخوانید، به آن پیوند دهید و بخش‌های کوتاهی از آن را همراه با پیوند به منبع "
           f"نقل کنید. آثارِ هنری در مالکیتِ عمومی‌اند، قلم‌ها با مجوزِ SIL Open Font License منتشر شده‌اند و صوت را صداهای ساختگی روایت "
           f"کرده‌اند؛ <a href=\"{h}credits.html\">منابع</a> را ببینید. کدِ منبع در <a href=\"{REPO}\">گیت‌هاب</a> منتشر شده است.</p>")),
        (L("Acceptable use", "استفادهٔ مجاز"),
         L("<p>Please do not use the site in a way that breaks the law, interferes with the site or with other people's use of it, tries to "
           "get around its security, or uses someone else's account or API key without permission.</p>",
           "<p>لطفاً سایت را طوری به کار نبرید که قانون را زیرِ پا بگذارد، در کارِ سایت یا استفادهٔ دیگران از آن اختلال ایجاد کند، بخواهد "
           "امنیتش را دور بزند، یا بی‌اجازه از حساب یا کلیدِ API کسِ دیگری استفاده کند.</p>")),
        (L("No warranty", "بدونِ ضمانت"),
         L("<p>The site and everything on it are provided “as is”, without warranties of any kind. The guide is for education; it is "
           "written with care, but it may contain errors.</p>",
           "<p>سایت و همهٔ محتوایش «همان‌طور که هست» و بدونِ هیچ‌گونه ضمانتی ارائه می‌شود. راهنما برای آموزش است؛ با دقت نوشته شده، اما "
           "ممکن است خطا داشته باشد.</p>")),
        (L("Limitation of liability", "محدودیتِ مسئولیت"),
         L("<p>To the extent permitted by law, the site's author is not liable for any loss or damage arising from your use of the site, "
           "including the loss of data stored in your browser or your Google Drive, or charges made by an AI provider.</p>",
           "<p>تا جایی که قانون اجازه می‌دهد، نویسندهٔ سایت مسئولِ هیچ زیان یا خسارتی نیست که از استفادهٔ شما از سایت پیش بیاید، از جمله از "
           "دست رفتنِ داده‌هایی که در مرورگر یا گوگل‌درایوتان ذخیره شده‌اند، یا هزینه‌هایی که یک خدمتِ هوش مصنوعی می‌گیرد.</p>")),
        (L("Changes and ending", "تغییر و پایان"),
         L("<p>These terms may be updated; the new version will be posted on this page with a new date. You can stop using the site at any "
           f"time and remove your data as the {privacy} describes.</p>",
           "<p>این شرایط ممکن است به‌روز شوند؛ نسخهٔ تازه با تاریخِ تازه در همین صفحه منتشر می‌شود. هر وقت بخواهید می‌توانید استفاده از سایت "
           f"را کنار بگذارید و داده‌هایتان را همان‌طور که {privacy} می‌گوید حذف کنید.</p>")),
        (L("Contact", "تماس"),
         L(f"<p>Questions about these terms: please open an issue at <a href=\"{ISSUES}\">{ISSUES}</a>.</p>",
           f"<p>برای پرسش دربارهٔ این شرایط، لطفاً در <a href=\"{ISSUES}\">{ISSUES}</a> یک issue باز کنید.</p>")),
    ], "terms.html")


def en_engines():
    """Which English chapters each narration engine made, from the sync files: {"ElevenLabs": [1], "Kokoro": [2, 3]}."""
    out = {}
    for mp3 in sorted((GUIDE / "audio").glob("[01][0-9]-*.mp3")):
        p = GUIDE / "audio" / "sync" / (mp3.stem + ".json")
        engine = (json.loads(p.read_text(encoding="utf-8")).get("narration") or {}).get("engine") if p.exists() else None
        out.setdefault(engine or "Kokoro", []).append(int(mp3.name[:2]))
    return out


def en_chapters_phrase(nums, fa=False):
    """«chapter 1», «chapters 1–3 and 5» (runs as ranges); in Persian with Persian digits."""
    runs, start = [], None
    for i, n in enumerate(nums):
        if start is None:
            start = n
        if i + 1 == len(nums) or nums[i + 1] != n + 1:
            runs.append((start, n))
            start = None
    d = (lambda x: num(x)) if fa else str
    parts = [x for a, b in runs for x in ([d(a)] if a == b else [d(a), d(b)] if b == a + 1 else [f"{d(a)}–{d(b)}"])]
    if fa:
        return ("فصلِ " if len(nums) == 1 else "فصل‌های ") + ("، ".join(parts[:-1]) + " و " + parts[-1] if len(parts) > 1 else parts[0])
    return ("chapter " if len(nums) == 1 else "chapters ") + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0])


KOKORO = ('<a href="https://huggingface.co/hexgrad/Kokoro-82M">Kokoro-82M</a> text-to-speech model (Apache License 2.0), '
          'with pronunciation by <a href="https://github.com/hexgrad/misaki">misaki</a>')
KOKORO_FA = ('مدلِ متن‌به‌گفتارِ <a href="https://huggingface.co/hexgrad/Kokoro-82M">Kokoro-82M</a> (مجوز آپاچی ۲٫۰)، '
             'با تلفظِ <a href="https://github.com/hexgrad/misaki">misaki</a>')


def en_voices_credit():
    """Credits for the English narration, chapter by chapter engine (in the language being built)."""
    e = en_engines()
    eleven, kokoro = e.get("ElevenLabs", []), e.get("Kokoro", [])
    if LANG == "fa":
        out = ""
        if eleven:
            out += ((f"{en_chapters_phrase(eleven, True)} نسخهٔ صوتیِ انگلیسی را " if kokoro else "نسخهٔ صوتیِ انگلیسی را ")
                    + 'سه صدای ساختگیِ <a href="https://elevenlabs.io">ElevenLabs</a> خوانده‌اند: آرتور راوی است، '
                    'جین هر بخشِ سوم و پرسش‌های آزمونک را می‌خواند، و آدام استون نقل‌قول‌ها را. ')
        if kokoro:
            out += ("فصل‌های دیگرِ آن را " if eleven else "نسخهٔ صوتیِ انگلیسی را ") + f"صدایی ساختگی روایت کرده است: {KOKORO_FA}. "
        return out
    out = ""
    if eleven:
        who = en_chapters_phrase(eleven) if kokoro else "The English audio edition"
        out += (f'{who[0].upper() + who[1:]} {"is" if len(eleven) == 1 and kokoro else "are" if kokoro else "is"} read by three synthetic '
                '<a href="https://elevenlabs.io">ElevenLabs</a> voices: Arthur narrates, Jane reads every third section and asks the quiz '
                'questions, and Adam Stone reads the quotations. ')
    if kokoro:
        out += ("The other chapters are" if eleven else "The audio edition is") + f" narrated by a synthetic voice: the {KOKORO}. "
    return out


def fa_engines():
    """Which Persian chapters each narration engine made, from the sync files: {"ElevenLabs": [1], "Gooya": [2, 3]}."""
    out = {}
    for n, t in sorted(FA_TRACKS.items()):
        p = GUIDE / "fa" / "audio" / "sync" / (t["file"][:-4] + ".json")
        engine = (json.loads(p.read_text(encoding="utf-8")).get("narration") or {}).get("engine", "Gooya") if p.exists() else "Gooya"
        out.setdefault(engine, []).append(n)
    return out


def fa_engines_phrase():
    """«ElevenLabs با دو راوی برای فصلِ ۱؛ مدلِ گویا بزرگ برای فصل‌های ۲ و ۳»."""
    names = {"ElevenLabs": "ElevenLabs با دو راوی", "Gooya": "مدلِ فارسیِ «گویا بزرگ»"}
    engines = fa_engines()
    if len(engines) == 1:
        return names.get(next(iter(engines)), next(iter(engines)))
    return "؛ ".join(f"{names.get(e, e)} برای {fa_chapters_phrase(ns)}" for e, ns in engines.items())


def fa_chapters_phrase(nums):
    """«فصلِ ۱» or «فصل‌های ۲ و ۳»."""
    nums = [num(n) for n in nums]
    if len(nums) == 1:
        return f"فصلِ {nums[0]}"
    return "فصل‌های " + "، ".join(nums[:-1]) + " و " + nums[-1]


def fa_voices_credit():
    """Credits for the Persian narration, chapter by chapter engine."""
    engines = fa_engines()
    eleven, gooya = engines.get("ElevenLabs", []), engines.get("Gooya", [])
    out = ""
    if eleven:
        out += (f'روایتِ فارسیِ {fa_chapters_phrase(eleven)} را دو صدای ساختگیِ <a href="https://elevenlabs.io">ElevenLabs</a> '
                'خوانده‌اند: صدای مردانه راویِ اصلی است و صدای زنانه بخش‌ها را به نوبت با او می‌خواند. ')
        sync = {n: json.loads((GUIDE / "fa" / "audio" / "sync" / (FA_TRACKS[n]["file"][:-4] + ".json")).read_text(encoding="utf-8"))
                for n in eleven}
        v2 = [n for n in eleven if sync[n].get("narration", {}).get("edition") == "v2"]
        if v2:
            out += (f'متنِ {fa_chapters_phrase(v2)} پیش از روایت برای گوش بازنویسی شده است: جمله‌های کوتاه‌تر و مکث‌های واقعی، '
                    'با همان عنوان‌ها، نقل‌قول‌ها و اصطلاح‌ها. ')
        if all(sync[n].get("heading_pauses") for n in eleven):
            out += 'پس از هر عنوان مکثی در صدا گذاشته شده است، تا عنوان به جملهٔ بعد نچسبد. '
    if gooya:
        out += ((f"روایتِ فارسیِ {fa_chapters_phrase(gooya)} را " if eleven else "نسخهٔ صوتیِ فارسی را ") + FA_GOOYA_CREDIT)
    return out


FA_GOOYA_CREDIT = (
    'صدایی ساختگی خوانده است: مدلِ متن‌به‌گفتارِ '
    '<a href="https://huggingface.co/Reza2kn/Gooya-Bozorg-v1.5">گویا بزرگ ۱٫۵</a>، که همان '
    '<a href="https://huggingface.co/Thomcles/Chatterbox-TTS-Persian-Farsi">Chatterbox-TTS-Persian-Farsi</a> '
    '(مدلِ Chatterbox از Resemble AI، آموزش‌دیده برای فارسی) است، با مجوزِ CC BY-NC 4.0 (فقط برای استفادهٔ غیرتجاری)، '
    'همراه با رمزگشای صدای <a href="https://huggingface.co/ResembleAI/chatterbox-turbo">Chatterbox Turbo</a> (مجوزِ MIT). '
    'صدای راوی از صدای گوینده‌ای ایرانی در مجموعه‌دادهٔ '
    '<a href="https://huggingface.co/datasets/MahtaFetrat/Mana-TTS">Mana-TTS</a> (مالکیتِ عمومی، CC0) الگو گرفته است. ')


BASE_404 = ('<script>(function(){var p=location.pathname.split("/"),b="/";'
            'if(/\\.github\\.io$/.test(location.hostname)&&p.length>2)b="/"+p[1]+"/";'
            'document.write(\'<base href="\'+b+\'">\')})();</script>')


def build_notebook(art):
    root = up(1)
    head = hero(art, "ch18", root, kicker=L("Your notebook", "دفترچهٔ شما"), title=L("Highlights and notes", "نشانه‌گذاری‌ها و یادداشت‌ها"), cls="band",
                lede=L("Everything you have highlighted or written, from every chapter and concept page. "
                       "It is kept in this browser; export it to keep a copy or to move it to another device.",
                       "هر آنچه در فصل‌ها و صفحه‌های مفاهیم نشانه‌گذاری کرده یا نوشته‌اید. "
                       "در همین مرورگر نگه داشته می‌شود؛ برای داشتنِ نسخهٔ پشتیبان یا بردن به دستگاهی دیگر، آن را برون‌بری کنید."))
    filters = ""
    for c in ("all", "yellow", "green", "blue", "pink"):
        cls = "" if c == "all" else f' class="c-{c}"'
        filters += (f'<button type="button" data-filter="{c}" aria-pressed="{"true" if c == "all" else "false"}"{cls}>'
                    f'{L("All", "همه") if c == "all" else ""}<span class="sr">{c}</span></button>')
    return (f'{head}<main id="main" class="wrap notebook-page">'
            f'<div class="nb-tools"><input id="nb-q" type="search" placeholder="{L("Search your notes", "جست‌وجو در یادداشت‌ها")}" aria-label="{L("Search your notes", "جست‌وجو در یادداشت‌ها")}">'
            f'<div class="nb-filters" role="group" aria-label="{L("Filter by colour", "صافی بر اساس رنگ")}">{filters}</div>'
            f'<div class="nb-actions"><button type="button" id="nb-md">{icon("download")} Markdown</button>'
            f'<button type="button" id="nb-json">{icon("download")} {L("Backup (.json)", "پشتیبان (.json)")}</button>'
            f'<button type="button" id="nb-import">{L("Import backup", "درون‌بری پشتیبان")}</button><input id="nb-file" type="file" accept=".json,application/json" hidden></div>'
            f'<p id="nb-count" class="nb-count"></p></div>'
            f'<div id="notebook" aria-live="polite"></div></main>')


def build_404(art):
    head = hero(art, "cave", "", kicker="Error 404", title="Only shadows here",
                lede="The page you were looking for isn't on this site. Perhaps it was only ever an appearance.",
                actions='<a class="btn primary" href="./">Go to the start</a>')
    return f'<main id="main">{head}</main>'


# ----------------------------------------------------------------------------- terms, search and questions

# Everyday words that are glossary terms too; linking every mention of them would be noise.
TERM_SKIP = {"acceptance", "ambiguity", "analytic", "anchoring", "argument", "belief", "contingent", "crux", "deduction",
             "evidence", "epistemology", "fallacy", "heuristic", "induction", "justification", "normative", "open-mindedness",
             "overconfidence", "paradigm", "proposition", "safety", "sensitivity", "skepticism", "synthetic", "testimony",
             "tracking", "truth", "understanding", "vagueness", "validity", "soundness", "warrant", "memory", "perception",
             "introspection", "calibration", "reason", "knowledge", "confounding"}
TERM_SKIP_FA = {"باور", "معرفت", "شاهد", "شواهد", "استدلال", "توجیه", "حقیقت", "صدق", "ادراک", "ادراک حسی", "حافظه", "گواهی",
                "درون‌نگری", "عقل", "فهم", "استقرا", "قیاس", "مغالطه", "پارادایم", "گزاره", "ایمنی", "حساسیت", "شکاکیت",
                "معرفت‌شناسی", "اعتبار", "درستی", "ابهام", "پذیرش", "تحلیلی", "ترکیبی", "کالیبراسیون", "ضمانت", "ردیابی",
                "هنجاری", "ممکن", "دانش", "علم", "باور صادق", "نظریه", "اطمینان", "یقین", "پیش‌فرض", "اعتماد", "تبیین"}
LEARN = {}
EN_CHAPTERS = {}


def reset_learning():
    LEARN.clear()
    LEARN.update({"terms": {}, "forms": {}, "regex": None, "deeper": {}, "search": [], "questions": [], "glossary_ids": {}})


reset_learning()


def lang_prefix():
    return "fa/" if LANG == "fa" else ""


def plain_inline(md, text):
    return html.unescape(strip_tags(md.inline(text)))


def prepare_learning(md, C, chapters):
    """Collect the glossary and the concepts into one set of terms, and decide which concepts each chapter covers."""
    terms, seen, by_en = {}, {}, {}
    P = lang_prefix()
    text = (SRC() / "17-glossary.md").read_text(encoding="utf-8") if (SRC() / "17-glossary.md").exists() else ""
    norm = lambda t: re.sub(r"^the\s+", "", re.sub(r"\s*\(.*?\)", "", t.lower().replace("’", "'"))).strip()
    for m in re.finditer(r"^\*\*(.+?)\.\*\*\s*(.*)$", text, re.M):
        term, rest = m.group(1), m.group(2)
        definition, _, where = rest.partition("→")
        link = re.search(r"\[([^\]]+)\]\((\d\d-[\w-]+)\.md(#[\w-]*)?\)", where)
        full = plain_inline(md, term)
        if LANG == "fa":
            eng = re.search(r"\(([^()]*[A-Za-z][^()]*)\)\s*$", full)
            en_name = eng.group(1).strip() if eng else full
            name = re.sub(r"\s*\([^()]*[A-Za-z][^()]*\)\s*$", "", full).strip()
            gid = "g-" + github_slug(plain_inline(md, en_name), {})
        else:
            en_name, name = full, full
            gid = "g-" + github_slug(name, seen)
        LEARN["glossary_ids"][full] = gid
        by_en[norm(en_name)] = gid
        terms[gid] = {"id": gid, "t": name, "e": en_name if LANG == "fa" else "",
                      "d": re.sub(r"</?a\b[^>]*>", "", md.inline(definition.strip())),
                      "g": f"{P}guide/17-glossary.html#{gid}",
                      "s": f"{P}guide/{link.group(2)}.html{link.group(3) or ''}" if link else "", "sl": link.group(1) if link else ""}
    idx = guide_heading_index(EN_CHAPTERS or chapters, md)
    deeper = {}
    lang = "fa" if LANG == "fa" else "en"
    for cid, n in C.N.items():
        if cid == "root" or cid in BRANCH_CHAPTER:
            continue
        home_ = concept_home(C, cid, idx)
        sec = home_ if home_[1] else None
        num_ = home_[0]
        deeper.setdefault(num_, []).append(cid)
        where = f"{P}guide/{chapters[sec[0]].href}#{sec[1]}" if sec else ""
        key = by_en.get(norm(C.title(cid))) or by_en.get(re.sub(r"s$", "", norm(C.title(cid))))
        other = C.title(cid, "en" if lang == "fa" else "fa")
        if key:
            terms[key].update(c=cid, f=other)
            terms[key]["s"] = terms[key]["s"] or where
        elif not C.title(cid).endswith("?"):
            tid = "c-" + cid
            terms[tid] = {"id": tid, "t": C.title(cid, lang), "f": other, "d": C.line(cid, lang), "c": cid, "s": where,
                          "sl": (L(f"Ch. {sec[0]}", f"فصل {num(sec[0])}") if sec else "")}
            by_en[norm(C.title(cid))] = tid
    forms = {}
    skip = TERM_SKIP_FA if LANG == "fa" else TERM_SKIP
    for tid, v in terms.items():
        f = norm(v["t"]).replace("\u0650", "")  # the ezafe kasra is written inconsistently in Persian
        if len(f) < 4 or f in skip or " vs " in f or "≠" in f or " در برابر " in f:
            continue
        forms.setdefault(f, tid)
    LEARN.update(terms=terms, forms=forms, deeper=deeper)
    alts = sorted(forms, key=len, reverse=True)
    pattern = "|".join(re.escape(a).replace("'", "['’]").replace("\\ ", "\u0650?\\ ") for a in alts) or "(?!)"
    suffix = r"(?:‌?ها(?:ی)?)?" if LANG == "fa" else r"(?:e?s)?"
    LEARN["regex"] = re.compile(r"(?<![\w-])(?:" + pattern + r")" + suffix + r"(?![\w-])", re.I)


SKIP_TAGS = {"a", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre", "summary", "button", "figure", "svg", "script", "style", "blockquote"}


def link_terms(body):
    """Link the first mention of each glossary term or concept in a chapter to its definition."""
    used, depth = set(), 0
    forms = LEARN["forms"]

    def repl(m):
        found = m.group(0).lower().replace("’", "'").replace("\u0650", "")
        tid = (forms.get(found) or forms.get(re.sub(r"e?s$", "", found)) or forms.get(found[:-1])
               or forms.get(re.sub(r"‌?ها(?:ی)?$", "", found)))
        if not tid or tid in used:
            return m.group(0)
        used.add(tid)
        t = LEARN["terms"][tid]
        href = f"../concepts/{t['c']}.html" if t.get("c") else f"17-glossary.html#{tid}"
        return f'<a class="term" href="{href}" data-term="{tid}">{m.group(0)}</a>'
    out = []
    for part in re.split(r"(<[^>]+>)", body):
        if part.startswith("<"):
            tag = re.match(r"</?\s*([a-zA-Z0-9]+)", part)
            if tag and tag.group(1).lower() in SKIP_TAGS and not part.endswith("/>"):
                depth += -1 if part.startswith("</") else 1
            out.append(part)
        else:
            out.append(LEARN["regex"].sub(repl, part) if depth == 0 and part.strip() else part)
    return "".join(out)


def collect_sections(ch, body):
    """Search entries for a chapter's sections, and its self-check questions."""
    P = lang_prefix()
    LEARN["search"].append({"k": "ch", "t": ch.title, "c": ch.label, "u": f"{P}guide/{ch.href}", "x": html.unescape(strip_tags(ch.blurb.replace("*", "")))})
    for chunk in re.split(r'(?=<h2 id=")', body):
        m = re.match(r'<h2 id="([^"]+)"[^>]*>(.*?)</h2>', chunk, re.S)
        if not m:
            continue
        title = html.unescape(strip_tags(re.sub(r"<button.*?</button>", "", m.group(2), flags=re.S)))
        text = html.unescape(strip_tags(re.sub(r"<button.*?</button>", "", chunk[m.end():], flags=re.S)))
        LEARN["search"].append({"k": "s", "t": title, "c": f"{ch.label}: {ch.title}", "u": f"{P}guide/{ch.href}#{m.group(1)}", "x": text})
        if '<p class="q">' in chunk:
            for q in re.finditer(r'<p class="q"><span class="n">(\d+)</span>(.*?)</p>\s*((?:(?!<p class="q">).)*?)<details>\s*<summary>.*?</summary>(.*?)</details>',
                                 chunk, re.S):
                LEARN["questions"].append({"id": f"{ch.slug}-q{int(q.group(1))}", "n": int(q.group(1)), "ch": ch.num, "label": ch.label,
                                           "title": ch.title, "u": f"{P}guide/{ch.href}#{m.group(1)}", "sec": title,
                                           "q": q.group(2) + q.group(3), "a": q.group(4).strip()})


def write_learning_data(C):
    sfx = "-fa" if LANG == "fa" else ""
    P = lang_prefix()
    lang = "fa" if LANG == "fa" else "en"
    other = "en" if lang == "fa" else "fa"
    terms = {k: {kk: vv for kk, vv in v.items() if vv} for k, v in LEARN["terms"].items()}
    write(ASSETS / "data" / f"terms{sfx}.json", json.dumps(terms, ensure_ascii=False, separators=(",", ":")))
    search = list(LEARN["search"])
    for v in LEARN["terms"].values():
        if v["id"].startswith("g-"):
            search.append({"k": "g", "t": v["t"], "f": v.get("e", ""), "u": v["g"], "x": html.unescape(strip_tags(v["d"]))})
    for cid in C.N:
        if cid == "root":
            continue
        search.append({"k": "c", "t": C.title(cid, lang), "f": C.title(cid, other), "u": f"{P}concepts/{cid}.html",
                       "x": html.unescape(strip_tags(C.line(cid, lang))), "y": html.unescape(strip_tags(C.line(cid, other)))})
    write(ASSETS / "data" / f"search{sfx}.json", json.dumps(search, ensure_ascii=False, separators=(",", ":")))
    write(ASSETS / "data" / f"questions{sfx}.json", json.dumps(LEARN["questions"], ensure_ascii=False, separators=(",", ":")))


def deeper_box(ch, C, root):
    ids = LEARN["deeper"].get(ch.num, [])
    lang = "fa" if LANG == "fa" else "en"
    chips = "".join(f'<a href="../concepts/{cid}.html" data-term="{attr(next((k for k, v in LEARN["terms"].items() if v.get("c") == cid), ""))}">'
                    f'{esc(C.title(cid, lang))}</a>' for cid in ids)
    links = [f'<a href="{map_url(root, f"ch{ch.num}")}">{icon("map")} {L("See this chapter on the map of the guide", "این فصل را روی نقشهٔ راهنما ببینید")}</a>']
    if any(q["ch"] == ch.num for q in LEARN["questions"]):
        links.append(f'<a href="../review/#{ch.slug}">{icon("clock")} {L("Practise this chapter&#39;s questions", "تمرینِ پرسش‌های این فصل")}</a>')
    if not ids:
        return f'<section class="deeper"><span class="kicker">{L("Go deeper", "عمیق‌تر شوید")}</span><div class="more">{"".join(links)}</div></section>'
    return (f'<section class="deeper"><span class="kicker">{L("Go deeper", "عمیق‌تر شوید")}</span><h2>{L("Concepts from this chapter", "مفاهیمِ این فصل")}</h2>'
            f'<p>{L("Each has its own page with the key idea, objections and replies, common mistakes, and a self-check, in English and Persian.", "هر یک صفحهٔ خود را دارد، با ایدهٔ اصلی، اعتراض‌ها و پاسخ‌ها، خطاهای رایج و یک خودآزمایی.")}</p>'
            f'<div class="chips">{chips}</div><div class="more">{"".join(links)}</div></section>')


def build_account(art):
    root = up(1)
    head = hero(art, "ch01", root, kicker=L("My study", "مطالعهٔ من"), title=L("Your progress, notes and AI companion", "پیشرفت، یادداشت‌ها و همراهِ هوشمندِ شما"), cls="band",
                lede=L("Sign in with Google to carry everything between your devices, and to use your own Claude or ChatGPT key with the study companion.",
                       "با حساب گوگل وارد شوید تا همه‌چیز میان دستگاه‌هایتان جابه‌جا شود، و بتوانید کلیدِ Claude یا ChatGPT خودتان را برای همراهِ مطالعه به کار ببرید."))
    return (f'{head}<main id="main" class="wrap account-page"><div id="account">'
            f'<div data-slot="error"></div>'
            f'<section class="acc-card"><span class="kicker">{L("Account", "حساب")}</span><h2>{L("Sign in", "ورود")}</h2><div data-slot="signin"></div></section>'
            f'<section class="acc-card"><span class="kicker">{L("Your study", "مطالعهٔ شما")}</span><h2>{L("Where you are", "کجا هستید")}</h2><div id="resume"></div>'
            f'<div class="acc-tiles" data-slot="study"></div></section>'
            f'<section class="acc-card" id="ai"><span class="kicker">{L("Study companion", "همراهِ مطالعه")}</span><h2>{L("AI assistant", "دستیار هوشمند")}</h2>'
            + L(f'<p>On every chapter and concept page, the {icon("chat")} button (or the <b>Explain</b> button that appears when you select text) '
                f'opens a companion that has read the page. It can explain, quiz you, question you Socratically, or argue the other side.</p>',
                f'<p>در هر فصل و صفحهٔ مفهوم، دکمهٔ {icon("chat")} (یا دکمهٔ <b>توضیح</b> که هنگامِ انتخابِ متن ظاهر می‌شود) '
                f'همراهی را باز می‌کند که صفحه را خوانده است. می‌تواند توضیح دهد، از شما آزمون بگیرد، به شیوهٔ سقراطی پرسش کند، یا از طرفِ مقابل دفاع کند.</p>')
            + f'<div id="ai-settings"></div></section>'
            f'<section class="acc-card"><span class="kicker">{L("Your data", "داده‌های شما")}</span><h2>{L("Export or delete", "برون‌بری یا حذف")}</h2>'
            + L('<p>Everything is stored in this browser and, when you are signed in, in a private app folder in your Google Drive that only this site can open. '
                'There is no server of ours.</p>',
                '<p>همه‌چیز در همین مرورگر ذخیره می‌شود و، وقتی وارد شده باشید، در پوشه‌ای خصوصی در گوگل‌درایوِ شما که فقط این سایت می‌تواند بازش کند. '
                'ما هیچ سروری نداریم.</p>')
            + f'<div class="acc-actions"><button type="button" class="btn" data-act="export">{icon("download")} {L("Download everything (.json)", "دریافتِ همه‌چیز (.json)")}</button>'
            f'<button type="button" class="btn" data-act="wipe">{L("Delete from this browser", "حذف از این مرورگر")}</button></div></section>'
            f'</div></main>')


def build_review(art):
    root = up(1)
    head = hero(art, "ch13", root, kicker=L("Practice", "تمرین"), title=L("Review questions", "مرور پرسش‌ها"), cls="band",
                lede=L("The self-check questions from every chapter, brought back just before you are likely to forget them. "
                       "Answer honestly: questions you get right come back later and later; the ones you miss come back tomorrow.",
                       "پرسش‌های خودآزماییِ همهٔ فصل‌ها، درست پیش از آنکه احتمالاً فراموششان کنید، دوباره پیش رویتان می‌آیند. "
                       "صادقانه پاسخ دهید: پرسش‌هایی که درست جواب می‌دهید دیرتر و دیرتر برمی‌گردند؛ آن‌هایی که از دست می‌دهید فردا."))
    return (f'{head}<main id="main" class="wrap review-page"><div id="review" aria-live="polite">'
            f'<p class="nb-none">{L("Loading questions…", "در حال بارگذاری پرسش‌ها…")}</p></div></main>')


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
    pages = ["", "index.html", "guide/", "guide/index.html", "concepts/", "credits.html", "guide/audio/", "guide/audio/index.html", "guide/download.html",
             "guide/audio/about.html", "notes/", "review/", "account/"]
    paths = list(pages) + ["fa/" + p for p in pages]
    paths += ["map/", "map/index.html", "fa/map/", "fa/map/index.html", "assets/map.js", "assets/data/map-cards.json", "assets/data/map-cards-fa.json", "assets/data/map-passages.json", "assets/data/map-passages-fa.json", "guide/audio/tracks.js"] + (["guide/fa/audio/tracks.js"] if FA_AUDIO else [])
    paths += ["reading-path/", "reading-path/index.html", "fa/reading-path/", "fa/reading-path/index.html",
              "assets/reading-path.css", "assets/reading-path-core.js", "assets/reading-path-i18n.js",
              "assets/reading-path.js", "assets/data/reading-path.json", "assets/data/reading-path-fa.json"]
    paths += [
              "assets/site.css", "assets/site.js", "assets/notes.js", "assets/learn.js", "assets/ai-config.js", "assets/account.js", "assets/ai.js",
              "assets/data/terms.json", "assets/data/search.json", "assets/data/questions.json",
              "assets/data/terms-fa.json", "assets/data/search-fa.json", "assets/data/questions-fa.json",
              "assets/favicon.svg", "assets/fonts/fonts.css", "manifest.webmanifest", "assets/icon-192.png"]
    for base in ("", "fa/"):
        paths += sorted(f"{base}guide/{p.name}" for p in (ROOT / base / "guide").glob("[01][0-9]-*.html"))
        paths += sorted(f"{base}concepts/{p.name}" for p in (ROOT / base / "concepts").glob("*.html"))
    for base in ("", "fa/"):
        paths += sorted(f"{base}guide/listen/{p.name}" for p in (ROOT / base / "guide" / "listen").glob("*.html"))
    paths += sorted(f"deeper/{p.relative_to(ROOT / 'deeper').as_posix()}" for p in (ROOT / "deeper").glob("**/*.html"))
    paths += sorted(f"fa/deeper/{p.relative_to(ROOT / 'fa' / 'deeper').as_posix()}" for p in (ROOT / "fa" / "deeper").glob("**/*.html"))
    paths += sorted(f"assets/fonts/{p.name}" for p in (ASSETS / "fonts").glob("*.woff2"))
    paths += sorted(f"assets/art/{p.name}" for p in ART_DIR.glob("*-640.jpg"))
    paths += sorted(f"assets/art/{p.name}" for p in ART_DIR.glob("*-dot.jpg"))
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


EPUB_CSS_FA = """html,body{direction:rtl}
body{line-height:1.9}
th,td{text-align:right}
blockquote{font-style:normal}
em,i,cite{font-style:normal}
.kicker{letter-spacing:0;text-transform:none}
"""


def epub_links(href):
    """Links inside the EPUB: between chapters stay inside the book, everything else goes to the website."""
    live = LIVE + lang_prefix()
    if re.match(r"^[a-z]+:", href) or href.startswith("#"):
        return href
    path, _, frag = href.partition("#")
    frag = "#" + frag if frag else ""
    m = re.match(r"^(\d\d-[\w-]+)\.md$", path)
    if m:
        return m.group(1) + ".xhtml" + frag
    if path in ("../index.html", "../../index.html"):
        return LIVE + "map/" + frag
    if path == "README.md":
        return live + "guide/" + frag
    if path.startswith("audio/"):
        return live + "guide/" + (path.replace("README.md", "about.html")) + frag
    if path in ("../README.md", "../../README.md"):
        return REPO + "#readme"
    return live + "guide/" + href


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
    LANGATTR = 'lang="fa" xml:lang="fa" dir="rtl"' if LANG == "fa" else 'lang="en" xml:lang="en"'
    rtl_spine = ' page-progression-direction="rtl"' if LANG == "fa" else ""
    for n, ch in sorted(chapters.items()):
        body, heads = md.render(clean_chapter_markdown(ch.text), epub_links)
        body = re.sub(r"<!--MERMAID:\w+-->",
                      L(f'<p class="note">This diagram is in the web edition: <a href="{LIVE}guide/{ch.href}">{html.escape(ch.title)}</a>.</p>',
                        f'<p class="note">این نمودار در نسخهٔ وب آمده است: <a href="{LIVE}fa/guide/{ch.href}">{html.escape(ch.title)}</a>.</p>'), body)
        pic = ""
        if (ART_DIR / f"{ch.art}-640.jpg").exists():
            images.append(ch.art)
            cap = art.caption(ch.art) if hasattr(art, "caption") else ""
            pic = (f'<figure class="cover"><img src="images/{ch.art}.jpg" alt="{attr(art.alt(ch.art))}"/>'
                   f'{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>')
        roman, part = PART_OF.get(ch.num, ("", ""))
        if roman:
            pl, pn = part_label(roman, part)
            kicker = f"{pl} · {pn} · {ch.label}"
        else:
            kicker = L("Appendix", "پیوست")
        name = f"{ch.slug}.xhtml"
        page = (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
                f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" {LANGATTR}>'
                f'<head><meta charset="utf-8"/><title>{html.escape(ch.title)}</title><link rel="stylesheet" href="book.css"/></head>'
                f'<body><section epub:type="chapter">{pic}<p class="kicker">{html.escape(kicker)}</p><h1>{html.escape(ch.title)}</h1>'
                f'{xhtml(body)}</section></body></html>')
        docs.append((name, page))
        subs = "".join(f'<li><a href="{name}#{slug}">{html.escape(plain)}</a></li>' for level, slug, plain, _ in heads if level == 2)
        nav.append(f'<li><a href="{name}">{html.escape(ch.label + ": " + ch.title if ch.num <= 16 else ch.title)}</a>'
                   f'{f"<ol>{subs}</ol>" if subs else ""}</li>')
    cover = ("<?xml version='1.0' encoding='utf-8'?>\n<!DOCTYPE html>\n"
             f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" {LANGATTR}>'
             f'<head><meta charset="utf-8"/><title>{L("Cover", "جلد")}</title><link rel="stylesheet" href="book.css"/></head>'
             f'<body><section epub:type="cover"><figure class="cover"><img src="images/cover.jpg" alt="{attr(art.alt("home"))}"/></figure>'
             f'<h1>{site_name()}</h1><p>{L("A complete guide to knowledge, evidence, and critical thinking.", "راهنمایی کامل دربارهٔ معرفت، شواهد و تفکر نقادانه.")}</p>'
             f'<p>{L("The illustrated web edition, the concept map and the audio:", "نسخهٔ مصوّرِ وب، نقشهٔ مفاهیم و نسخهٔ صوتی:")} <a href="{LIVE}{lang_prefix()}">{LIVE}{lang_prefix()}</a></p></section></body></html>')
    nav_doc = ("<?xml version='1.0' encoding='utf-8'?>\n<!DOCTYPE html>\n"
               f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" {LANGATTR}>'
               f'<head><meta charset="utf-8"/><title>{L("Contents", "فهرست")}</title><link rel="stylesheet" href="book.css"/></head>'
               f'<body><nav epub:type="toc" id="toc"><h1>{L("Contents", "فهرست")}</h1><ol>{"".join(nav)}</ol></nav></body></html>')
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
           f'<dc:identifier id="uid">urn:uuid:5f0c7c1e-3f47-4c55-9a0c-6d2a9b1e7e{L("11", "fa")}</dc:identifier>'
           f'<dc:title>{site_name()}</dc:title><dc:creator>{site_name()}</dc:creator><dc:language>{L("en", "fa")}</dc:language>'
           f'<dc:source>{LIVE}{lang_prefix()}</dc:source><meta property="dcterms:modified">{stamp}</meta></metadata>'
           f'<manifest>{"".join(items)}</manifest><spine{rtl_spine}>{spine}</spine></package>')
    container = ('<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    out = OUT() / "guide" / L(EPUB_NAME, EPUB_NAME_FA)
    out.parent.mkdir(parents=True, exist_ok=True)
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
        add(z, "OEBPS/book.css", EPUB_CSS + L("", EPUB_CSS_FA))
        add(z, "OEBPS/images/cover.jpg", (ART_DIR / "home-1200.jpg").read_bytes(), compress=False)
        for k in images:
            add(z, f"OEBPS/images/{k}.jpg", (ART_DIR / f"{k}-640.jpg").read_bytes(), compress=False)
        for name, page in docs:
            add(z, f"OEBPS/{name}", page)
    return out


# ----------------------------------------------------------------------------- deeper study

# A second layer beside the chapters, kept apart from them: the narrated chapters (guide/NN-*.md and their audio)
# are frozen. Each substantive section of a chapter can have a Deeper study page (deeper/src/<chapter>/<section>.md),
# written in layers for the different reasons a reader arrives: to learn the idea again, for the full story, for
# what the chapter leaves out, or for the sources. The chapter page gets a link at the end of each section that has
# a page; the link is added here, never in the Markdown.
DEEPER = ROOT / "deeper"
DEEPER_DRAFTS = os.environ.get("EPIS_DEEPER_DRAFTS") == "1"  # build drafts too, for a local preview
DEEP = {}  # chapter slug -> {section id: page}, the English pages
DEEP_FA = {}  # the same for the Persian translations (deeper/src-fa/), which follow the English page one for one
NOT_SUBSTANTIVE = {"in-this-chapter", "check-your-understanding", "further-reading"}
CITE = re.compile(r"\[(@[^\[\]]+)\]")
# The layers, in order: id, heading, the reader's reason (the chooser), what the layer holds.
LAYERS = [("re-learn", "Re-learn", "I didn't get it", "The idea again, step by step, and the usual confusions"),
          ("the-full-story", "The full story", "I want the whole story",
           "Where the idea came from, the original texts, the arguments, and where the debate stands"),
          ("beyond-the-chapter", "Beyond the chapter", "Something felt missing",
           "What the chapter leaves out or simplifies, and how this connects to the rest"),
          ("sources", "Sources", "Show me the sources", "What to read next, and every work cited")]
# the chooser's wording in Persian: the reader's reason and what the layer holds (a page's own layer headings are its translator's)
LAYERS_FA = {"re-learn": ("نفهمیدم", "ایده را دوباره، گام‌به‌گام و با کژفهمی‌های رایجش مرور می‌کنیم"),
             "the-full-story": ("همهٔ ماجرا را می‌خواهم", "ایده از کجا آمد، متن‌های اصلی، استدلال‌ها و جای امروزِ بحث"),
             "beyond-the-chapter": ("چیزی کم بود", "آنچه فصل نیاورده یا ساده کرده، و پیوندِ این بحث با بقیه"),
             "sources": ("منبع‌ها را نشانم بده", "چه بخوانید، و همهٔ کارهای ذکرشده")}
LAYER_IDS = [l[0] for l in LAYERS]
REQUIRED_LAYERS = {"A": LAYER_IDS, "B": ["re-learn", "beyond-the-chapter", "sources"]}
BLOCK = re.compile(r"(?ms)^::: *([a-z]+)(?: +([^\n]*?))? *\n(.*?)\n::: *$")
BLOCK_KINDS = {"original": "Read the original", "argument": "The argument, step by step", "timeline": "Timeline",
               "positions": "The positions", "box": ""}
BLOCK_LABELS_FA = {"original": "متنِ اصلی را بخوانید", "argument": "استدلال، گام‌به‌گام", "timeline": "گاه‌شمار",
                   "positions": "دیدگاه‌ها", "box": ""}


def read_front_matter(text):
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def fa_normalize(text, layers):
    """A Persian page, made ready to build like the English one: its i-th ## heading takes the English layer heading (which
    gives the layer its id), its opening note takes the English marker, and the translator's own wording is returned to be
    shown in their place. Returns (text, {layer id: Persian heading}, Persian marker)."""
    titles, lids = {}, list(layers)
    def heading(m):
        i = len(titles)
        if i >= len(lids):
            return m.group(0)
        titles[lids[i]] = m.group(1).strip()
        return "## " + dict((l[0], l[1]) for l in LAYERS)[lids[i]]
    text = re.sub(r"(?m)^## (.+?)\s*$", heading, text)
    marker = []
    def short(m):
        marker.append(m.group(2))
        return m.group(1) + "> **In short.**"
    text = re.sub(r"^(\s*)> \*\*(.+?)\*\*", short, text, count=1)
    return text, titles, marker[0] if marker else ""


def load_deeper(md):
    """The Deeper study pages in deeper/src/ (English) and deeper/src-fa/ (their Persian translations). A draft is built only
    with EPIS_DEEPER_DRAFTS=1, so the live site shows nothing of a page until its front matter says status: published."""
    DEEP.clear()
    DEEP_FA.clear()
    for p in sorted((DEEPER / "src").glob("[01][0-9]-*/*.md")):
        meta, text = read_front_matter(p.read_text(encoding="utf-8"))
        if meta.get("status") != "published" and not DEEPER_DRAFTS:
            continue
        _, heads = md.render(CITE.sub("", BLOCK.sub(lambda m: m.group(3), text)), lambda h: h)
        DEEP.setdefault(p.parent.name, {})[p.stem] = {"meta": meta, "text": text, "path": p,
                                                       "layers": [h[1] for h in heads if h[0] == 2]}
    for p in sorted((DEEPER / "src-fa").glob("[01][0-9]-*/*.md")):
        meta, raw = read_front_matter(p.read_text(encoding="utf-8"))
        en = DEEP.get(p.parent.name, {}).get(p.stem)
        if not en or (meta.get("status") != "published" and not DEEPER_DRAFTS):
            continue
        text, titles, label = fa_normalize(raw, en["layers"])
        _, heads = md.render(CITE.sub("", BLOCK.sub(lambda m: m.group(3), text)), lambda h: h)
        DEEP_FA.setdefault(p.parent.name, {})[p.stem] = {"meta": meta, "text": text, "raw": raw, "path": p, "titles": titles, "label": label,
                                                          "layers": [h[1] for h in heads if h[0] == 2], "of": en}


def deeper_links(ch, body):
    """After each chapter section that has a Deeper study page, a small link to it."""
    pages = (DEEP_FA if LANG == "fa" else DEEP).get(ch.slug)
    if not pages:
        return body
    parts = re.split(r'(?=<h2 id=")', body)
    for i, part in enumerate(parts):
        m = re.match(r'<h2 id="([^"]+)"', part)
        if m and m.group(1) in pages:
            parts[i] = (part.rstrip() + f'\n<p class="sch-link"><a href="../deeper/{ch.slug}/{m.group(1)}.html">'
                        f'<span>{L("Go deeper on this section", "این بخش را عمیق‌تر بخوانید")}</span> <span aria-hidden="true">{L("→", "←")}</span></a></p>\n')
    return "".join(parts)


def deeper_data():
    """The shared bibliography (deeper/data/sources.json)."""
    p = DEEPER / "data" / "sources.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def family(name):
    name = (name or "").strip()
    return name.split(",")[0].strip() if "," in name else (name.split() or ["?"])[-1]


def short_cite(src):
    names = src.get("authors") or src.get("editors") or [src.get("org") or src.get("title", "?")]
    who = (family(names[0]) if len(names) == 1 else f"{family(names[0])} and {family(names[1])}" if len(names) == 2
           else f"{family(names[0])} et al.")
    return f"{who} {src.get('year', 'n.d.')}"


def full_ref(src):
    """A reference in author-date style, with its DOI, ISBN or stable link."""
    x = html.escape
    names = src.get("authors") or []
    def name_list(ns, first_inverted=True):
        out = [n if (i == 0 and first_inverted) or "," not in n else " ".join(reversed([t.strip() for t in n.split(",", 1)]))
               for i, n in enumerate(ns)]
        return out[0] if len(out) == 1 else ", ".join(out[:-1]) + (", and " if len(out) > 2 else " and ") + out[-1]
    who = name_list(names) if names else src.get("org", "")
    year = str(src.get("year", "n.d."))
    if src.get("original_year"):
        year = f"[{src['original_year']}] {year}"
    t, title, cont = src.get("type", "book"), x(src.get("title", "")), x(src.get("container", ""))
    eds = name_list(src["editors"], first_inverted=False) if src.get("editors") else ""
    trans = f" Translated by {x(src['translator'])}." if src.get("translator") else ""
    pub = ": ".join(v for v in (x(src.get("place", "")), x(src.get("publisher", ""))) if v)
    pub = pub + "." if pub else ""
    if t == "article":
        vol = x(str(src.get("volume", "")))
        vol += f" ({x(str(src['issue']))})" if src.get("issue") else ""
        body = f"“{title}.” <i>{cont}</i> {vol}" + (f": {x(src['pages'])}" if src.get("pages") else "") + "."
    elif t in ("chapter", "entry"):
        body = (f"“{title}.” In <i>{cont}</i>" + (f", {x(src['edition'])}" if src.get("edition") else "")
                + (f", edited by {x(eds)}" if eds else "") + (f", {x(src['pages'])}" if src.get("pages") else "") + "."
                + (f" {pub}" if pub else ""))
    else:
        body = f"<i>{title}</i>." + (f" {x(src['edition'])}." if src.get("edition") else "") + trans + (f" {pub}" if pub else "")
    ids = []
    if src.get("doi"):
        ids.append(f'<a href="https://doi.org/{x(src["doi"])}">doi:{x(src["doi"])}</a>')
    if src.get("isbn"):
        ids.append(f"ISBN {x(src['isbn'])}")
    if src.get("url"):
        label = {"open-access": "Full text (open access)", "public-domain": "Full text (public domain)"}.get(src.get("access"), "Stable link")
        ids.append(f'<a href="{x(src["url"])}">{label}</a>')
    return f"{x(who).rstrip('.')}. {year.rstrip('.')}. {body}" + (" " + " · ".join(ids) if ids else "")


def cited_keys(text):
    """Every [@key, locator] in a page, as (key, locator) pairs, and any malformed citations."""
    out, bad = [], []
    for c in CITE.finditer(text):
        for part in c.group(1).split(";"):
            km = re.match(r"\s*@([\w:.-]+)\s*(?:,\s*(.+?))?\s*$", part)
            (out.append((km.group(1), (km.group(2) or "").strip())) if km else bad.append(c.group(1)))
    return out, bad


def deeper_problems(sid, pg, chapter_heads, sources, prov):
    """Everything wrong with a page: not a section of the chapter, missing or unknown layers, citations of unknown
    or unverifiable sources, and (once published) cited sources without evidence in the provenance record."""
    errs = []
    h2 = [h[1] for h in chapter_heads if h[0] == 2]
    if sid not in h2:
        errs.append("not a section of the chapter")
    elif sid in NOT_SUBSTANTIVE:
        errs.append("not a substantive section")
    tier = pg["meta"].get("tier")
    if tier not in REQUIRED_LAYERS:
        errs.append(f"tier must be A or B, not {tier!r}")
    else:
        for lid in REQUIRED_LAYERS[tier]:
            if lid not in pg["layers"]:
                errs.append(f"missing layer ## {dict((l[0], l[1]) for l in LAYERS)[lid]}")
    for lid in pg["layers"]:
        if lid not in LAYER_IDS:
            errs.append(f"## heading #{lid} is not one of the layers ({', '.join(l[1] for l in LAYERS)})")
    if [l for l in LAYER_IDS if l in pg["layers"]] != [l for l in pg["layers"] if l in LAYER_IDS]:
        errs.append("layers out of order")
    if not re.match(r"\s*> \*\*In short\.\*\*", pg["text"]):
        errs.append("a page starts with > **In short.**")
    for m in BLOCK.finditer(pg["text"]):
        if m.group(1) not in BLOCK_KINDS:
            errs.append(f"unknown block ::: {m.group(1)}")
    keys, bad = cited_keys(pg["text"])
    errs += [f"malformed citation [{b}]" for b in bad]
    for k in dict.fromkeys(k for k, _ in keys):
        src = sources.get(k)
        if not src:
            errs.append(f"unknown source @{k}")
        elif not (src.get("doi") or src.get("isbn") or src.get("url")):
            errs.append(f"@{k}: no DOI, ISBN or stable link")
        elif not src.get("verified"):
            errs.append(f"@{k}: bibliographic details not marked as verified")
    if pg["meta"].get("status") == "published":
        have = {s.get("key"): s for s in (prov or {}).get("sources", [])}
        if not prov:
            errs.append("no provenance record")
        for k in dict.fromkeys(k for k, _ in keys):
            if k not in have or not have[k].get("evidence"):
                errs.append(f"@{k} is cited without evidence in the provenance record")
    return errs


def deeper_problems_fa(sid, pg, chapter_heads):
    """What is wrong with a Persian page: anything that makes it differ in structure from the English page it translates, whose
    provenance it shares. It must cite the same sources, have the same layers, blocks and links, and carry the same tier."""
    en, errs = pg["of"], []
    if sid not in [h[1] for h in chapter_heads if h[0] == 2]:
        errs.append("not a section of the chapter")
    if pg["meta"].get("tier") != en["meta"].get("tier"):
        errs.append("tier differs from the English page")
    if pg["layers"] != en["layers"]:
        errs.append(f"layers differ from the English page ({len(pg['layers'])} vs {len(en['layers'])} ## headings)")
    if not pg.get("label"):
        errs.append("a page starts with > **به‌کوتاهی.** (its opening note)")
    if sorted(k for k, _ in cited_keys(pg["text"])[0]) != sorted(k for k, _ in cited_keys(en["text"])[0]):
        a, b = {k for k, _ in cited_keys(pg["text"])[0]}, {k for k, _ in cited_keys(en["text"])[0]}
        errs.append("citations differ from the English page: missing " + (", ".join(sorted(b - a)) or "none") + "; extra " + (", ".join(sorted(a - b)) or "none"))
    kinds = lambda t: sorted(m.group(1) for m in BLOCK.finditer(t))
    if kinds(pg["text"]) != kinds(en["text"]):
        errs.append("blocks differ from the English page")
    links = lambda t: sorted(m.group(1) for m in re.finditer(r"\]\(((?:\d\d-[\w-]+\.md|deeper:)[^)\s]*)\)", t))
    if links(pg["text"]) != links(en["text"]):
        errs.append("links to chapters and Deeper study pages differ from the English page")
    if len(re.findall(r"(?m)^### ", pg["text"])) != len(re.findall(r"(?m)^### ", en["text"])):
        errs.append("### headings differ in number from the English page")
    if not pg["meta"].get("of"):
        errs.append("front matter lacks `of:` (the fingerprint of the English page it translates; tools/deeper/fa_fingerprint.py writes it)")
    elif pg["meta"]["of"] != fingerprint(en["text"]):
        print(f"  deeper: note: the English page changed since {pg['path'].relative_to(ROOT)} was translated")
    if pg["meta"].get("translation_of") and pg["meta"].get("status") == "published":
        if pg["meta"]["translation_of"] != f"{pg['path'].parent.name}/{sid}":
            errs.append("translation_of does not identify the matching English page")
        sys.path.insert(0, str(ROOT / "tools" / "deeper"))
        from check_fa import validate_page
        sys.path.pop(0)
        provenance_path = DEEPER / "data" / pg["path"].parent.name / f"{sid}.json"
        annotation_path = DEEPER / "data-fa" / pg["path"].parent.name / f"{sid}.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.exists() else {}
        annotations = json.loads(annotation_path.read_text(encoding="utf-8")) if annotation_path.exists() else {}
        errs.extend(validate_page(en["path"].read_text(encoding="utf-8"),
                                  pg["path"].read_text(encoding="utf-8"), provenance, annotations))
    return errs


def fingerprint(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


AFTER_BLOCK = re.compile(r"\n[ \t]*\n(\[@[^\[\]]+\])\.?[ \t]*")  # a citation opening the paragraph right after a block


def lift_block_sources(text):
    """Move a citation that opens the paragraph right after a block onto the block's title line."""
    out, pos = [], 0
    for m in BLOCK.finditer(text):
        a = AFTER_BLOCK.match(text, m.end())
        if a:
            eol = text.index("\n", m.start())
            out.append(text[pos:eol].rstrip() + " " + a.group(1) + text[eol:m.end()] + "\n\n")
            pos = a.end()
    return "".join(out) + text[pos:]


def label_cells(body):
    """Give each table cell its column heading, so a narrow screen can show a row as a small card."""
    def table(m):
        heads = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", m.group(0), re.S)]
        def row(r):
            names = iter(heads)
            return re.sub(r"<td(?=[ >])", lambda c: f'<td data-label="{html.escape(next(names, ""), quote=True)}"', r.group(0))
        return re.sub(r"<tr>.*?</tr>", row, m.group(0), flags=re.S)
    return re.sub(r"<table>.*?</table>", table, body, flags=re.S)


def deeper_blocks(text):
    """::: original|argument|timeline|positions|box [title] ... ::: as a styled box around ordinary Markdown.
    A citation that opens the paragraph right after a block gives the block's sources; it goes on the block's title."""
    text = lift_block_sources(text)
    def box(m):
        kind, title, inner = m.group(1), (m.group(2) or "").strip(), m.group(3)
        label = (BLOCK_LABELS_FA if LANG == "fa" else BLOCK_KINDS).get(kind, "")
        title = re.sub(r"\*(.+?)\*", r"<i>\1</i>", html.escape(title, quote=False))
        head = (f'<p class="blk-k">{label}</p>' if label else "") + (f'<p class="blk-h">{title}</p>' if title else "")
        return f'<div class="blk blk-{kind}">{head}\n\n{inner}\n\n</div>'
    return BLOCK.sub(box, text)


def deeper_body(ch, sid, pg, md, sources, prov):
    """A page: In short, the chooser, then the layers. Re-learn names its sources in one line; the other layers
    carry numbered notes; Sources ends with the works cited."""
    groups = []
    def mark(m):
        groups.append(cited_keys(m.group(0))[0])
        return f"⁅CITEMARK{len(groups) - 1}Z⁆"  # bracketed by punctuation so a quote before it still closes
    text = re.sub(r"[ \t]*" + CITE.pattern, mark, deeper_blocks(pg["text"]))  # a note number sits right after the word
    def rewrite(href):
        m = re.match(r"^(\d\d-[\w-]+)\.md(#.*)?$", href)
        if m:
            return f"../../guide/{m.group(1)}.html{m.group(2) or ''}"
        m = re.match(r"^deeper:(\d\d-[\w-]+)/([\w-]+)$", href)  # another Deeper study page
        if m and LANG == "fa" and m.group(2) not in DEEP_FA.get(m.group(1), {}):  # not yet translated: the English page
            return f"../../../deeper/{m.group(1)}/{m.group(2)}.html"
        return f"../{m.group(1)}/{m.group(2)}.html" if m else href
    body, heads = md.render(text, rewrite)
    if LANG == "fa":
        body = body.replace("<strong>In short.</strong>", f"<strong>{html.escape(pg.get('label', ''))}</strong>", 1)
    body = label_cells(polish(body))
    annotations = {s["key"]: s["annotation"] for s in (prov or {}).get("sources", []) if s.get("annotation")}
    if LANG == "fa":
        annotation_path = DEEPER / "data-fa" / ch.slug / f"{sid}.json"
        if annotation_path.exists():
            annotations = json.loads(annotation_path.read_text(encoding="utf-8")).get("annotations", {})
    order, notes_n = [], 0
    def remember(k):
        if k not in order:
            order.append(k)
    out = []
    for part in re.split(r'(?=<h2 id=")', body):
        m = re.match(r'<h2 id="([^"]+)">(.*?)</h2>', part, re.S)
        lid = m.group(1) if m else ""
        if lid == "re-learn" or not m:  # no note numbers in the intro or in Re-learn: one quiet line of sources instead
            used = []
            def quiet(mm):
                for k, loc in groups[int(mm.group(1))]:
                    remember(k)
                    if (k, loc) not in used:
                        used.append((k, loc))
                return ""
            part = re.sub(r"⁅CITEMARK(\d+)Z⁆", quiet, part)
            if used and m:
                line = "; ".join(f'<a href="#src-{k}">{html.escape(short_cite(sources.get(k, {"title": k})))}</a>'
                                 + (f", {html.escape(loc)}" if loc else "") for k, loc in used)
                part = part.rstrip() + f'<p class="sch-srcline"><span>{L("Sources for this part:", "منبع‌های این بخش:")}</span> {line}.</p>'
        else:
            notes = []
            def cite(mm):
                nonlocal notes_n
                notes_n += 1
                n = notes_n
                bits = []
                for k, loc in groups[int(mm.group(1))]:
                    remember(k)
                    bits.append(f'<a href="#src-{k}">{html.escape(short_cite(sources.get(k, {"title": k})))}</a>'
                                + (f", {html.escape(loc)}" if loc else ""))
                notes.append(f'<li id="note-{n}" value="{n}">{"; ".join(bits)}. <a class="back" href="#cite-{n}" aria-label="{L("Back to the text", "بازگشت به متن")}">↩</a></li>')
                return f'<sup class="cite"><a id="cite-{n}" href="#note-{n}" aria-label="{L("Note", "یادداشت")} {n}">{num(n)}</a></sup>'
            part = re.sub(r"⁅CITEMARK(\d+)Z⁆", cite, part)
            if notes:
                part = (part.rstrip() + f'<div class="sch-apparatus"><h3 class="sch-ap">{L("Notes", "یادداشت‌ها")}</h3>'
                        f'<ol class="sch-notes">{"".join(notes)}</ol></div>')
        if m:
            n = LAYER_IDS.index(lid) + 1 if lid in LAYER_IDS else 0
            kicker = f'<span class="layer-k">{L("Layer", "لایهٔ")} {num(n)}</span>' if n else ""
            shown = html.escape(pg.get("titles", {}).get(lid, "")) if LANG == "fa" and pg.get("titles", {}).get(lid) else m.group(2)
            part = part.replace(m.group(0), f'<h2 id="{lid}" class="layer">{kicker}<span class="ht">{shown}</span></h2>', 1)
        if lid == "sources" and order:
            refs = "".join(f'<li id="src-{k}">{full_ref(sources.get(k, {"title": k}))}'
                           + (f'<span class="ann" dir="{L("ltr", "rtl")}">{html.escape(annotations[k])}</span>' if k in annotations else "") + "</li>"
                           for k in sorted(order, key=lambda k: (family((sources.get(k, {}).get("authors") or [sources.get(k, {}).get("org", k)])[0]).lower(),
                                                               str(sources.get(k, {}).get("year", "")))))
            part = part.rstrip() + f'<h3 id="works-cited">{L("Works cited", "منبع‌های ذکرشده")}</h3><ul class="sch-refs biblio" dir="ltr">{refs}</ul>'
        out.append(part)
    present = [l for l in LAYERS if l[0] in pg["layers"]]
    if LANG == "fa":
        present = [(lid, t, *LAYERS_FA[lid]) for lid, t, _, _ in present]
    chooser = (f'<nav class="deep-choose" aria-label="{L("What brought you here?", "چه چیزی شما را به این‌جا آورد؟")}"><span class="kicker">{L("What brought you here?", "چه چیزی شما را به این‌جا آورد؟")}</span>'
               + "".join(f'<a href="#{lid}"><b>{reason}</b><span>{what}</span></a>' for lid, _, reason, what in present) + "</nav>")
    return out[0] + chooser + "".join(out[1:]), heads


def first_sentences(text, n):
    """The first n sentences of text, never cut inside a quotation."""
    inq, cuts = False, []
    for i, c in enumerate(text):
        if c == '"':
            inq = not inq
        elif c == "«":
            inq = True
        elif c == "»":
            inq = False
        after = text[i + 1:i + 2]
        if not inq and (after == "" or after.isspace()) and (c in ".!?؟" or (c in '"»' and text[i - 1:i] in (".", "!", "?", "؟"))):
            cuts.append(i + 1)
            if len(cuts) == n:
                break
    return text[:cuts[-1]].strip() if cuts else text.strip()


def deeper_words(text):
    return len(re.sub(r"\[@[^\]]+\]|[#>*_|:`-]", " ", text).split())


def build_deeper(chapters, md, art):
    """Write deeper/<chapter>/<section>.html for each page (fa/deeper/ for the Persian translations), a hub per chapter and
    deeper/index.html, after checking every page. A problem in a published page stops the build."""
    sources = deeper_data()
    fa = LANG == "fa"
    deep = DEEP_FA if fa else DEEP
    problems, built, rendered, hubs = 0, set(), [], []
    for slug in sorted(deep):
        ch = next((c for c in chapters.values() if c.slug == slug), None)
        if not ch:
            print(f"  deeper: {slug}: no such chapter")
            problems += 1
            continue
        heads = EN_HEADS.get(ch.num, [])
        titles = ({sid: html.escape(FA_HEADS.get((ch.num, sid), sid)) for sid in deep[slug]} if fa
                  else {h[1]: h[3] for h in heads if h[0] == 2})
        order_ids = [h[1] for h in heads if h[0] == 2 and h[1] in deep[slug]]
        order = order_ids + sorted(s_ for s_ in deep[slug] if s_ not in order_ids)
        root = up(2)
        rows = []
        for i, sid in enumerate(order):
            pg = deep[slug][sid]
            pp = DEEPER / "data" / slug / f"{sid}.json"
            prov = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
            errs = deeper_problems_fa(sid, pg, heads) if fa else deeper_problems(sid, pg, heads, sources, prov)
            for e in errs:
                print(f"  deeper: {'fa/' if fa else ''}{slug}/{sid}: {e}")
            if errs and pg["meta"].get("status") == "published":
                problems += len(errs)
            title = titles.get(sid, sid)
            body, pheads = deeper_body(ch, sid, pg, md, sources, prov)
            toc, sub = [], []
            for h in pheads:
                if h[0] == 2:
                    toc.append([h, []])
                elif h[0] == 3 and toc:
                    toc[-1][1].append(h)
            toc_html = "".join(f'<li><a href="#{h[1]}">{(html.escape(pg["titles"].get(h[1], "")) if fa and pg["titles"].get(h[1]) else h[3])}</a>'
                               + (("<ol>" + "".join(f'<li><a href="#{s_[1]}">{s_[3]}</a></li>' for s_ in subs) + "</ol>") if subs else "")
                               + "</li>" for h, subs in toc)
            draft = pg["meta"].get("status") != "published"
            minutes = max(1, round(deeper_words(pg["text"]) / (200 if fa else 230)))
            tier = pg["meta"].get("tier", "B")
            full_ = L("Full study", "مطالعهٔ کامل") if tier == "A" else L("Short study", "مطالعهٔ کوتاه")
            note = (f'<p class="sch-status{" draft" if draft else ""}">'
                    + (L("Draft: not yet reviewed, and not linked from the live site. ", "پیش‌نویس: هنوز بازبینی نشده و در سایتِ زنده پیوندی به آن نیست. ") if draft else "")
                    + f'{full_} · {L("about", "حدود")} {num(minutes)} {L("min", "دقیقه")}'
                    + (f' · {L("updated", "به‌روزرسانی")} <bdi dir="ltr">{num(html.escape(pg["meta"]["updated"]))}</bdi>' if pg["meta"].get("updated") else "")
                    + f'<br><a href="../../guide/{ch.href}#{sid}"><span aria-hidden="true">{L("←", "→")}</span> {L("This section in", "این بخش در")} {html.escape(ch.label)}</a>'
                    + f' · <a href="index.html">{L("All Deeper study for", "همهٔ مطالعه‌های عمیق‌ترِ")} {html.escape(ch.label)}</a></p>')
            if fa:
                note += (f'<p class="deep-translation">نقل‌قول‌های این صفحه برگردان فارسی‌اند. '
                         f'<a href="{root}deeper/{slug}/{sid}.html" hreflang="en">متن انگلیسی و ارجاع‌های آن</a> '
                         'در نسخهٔ انگلیسی در دسترس است؛ مشخصات کتاب‌شناختی به زبان منبع حفظ شده‌اند.</p>')
            prev_ = order[i - 1] if i else None
            next_ = order[i + 1] if i + 1 < len(order) else None
            pager = (f'<nav class="deep-pager" aria-label="{L("More Deeper study", "مطالعه‌های عمیق‌ترِ بیشتر")}">'
                     + (f'<a class="prev" href="{prev_}.html"><small>{L("Previous", "قبلی")}</small><b>{titles.get(prev_, prev_)}</b></a>' if prev_ else "<span></span>")
                     + (f'<a class="next" href="{next_}.html"><small>{L("Next", "بعدی")}</small><b>{titles.get(next_, next_)}</b></a>' if next_ else "<span></span>")
                     + "</nav>")
            head = hero(art, ch.art, root, kicker=f"{L('Deeper study', 'مطالعهٔ عمیق‌تر')} · {ch.label}", title=title, cls="band",
                        lede=L(f"Going deeper on a section of “{html.escape(ch.title)}”.", f"ژرف‌تر رفتن در یکی از بخش‌های «{html.escape(ch.title)}»."))
            page_body = (f'{head}<main id="main" class="page"><aside class="side"><nav class="toc" aria-label="{L("On this page", "در این صفحه")}">'
                         f'<span class="kicker">{L("On this page", "در این صفحه")}</span><ol>{toc_html}</ol></nav></aside>'
                         f'<article class="scholarly deep-page">{note}<details class="mini-toc"><summary>{L("On this page", "در این صفحه")}</summary><ol>{toc_html}</ol></details>'
                         f'<div class="prose">{body}</div>{pager}</article></main>')
            rendered.append((f"deeper/{slug}/{sid}.html", page_body, root, ch, title, sid))
            built.add(f"{slug}/{sid}.html")
            short = re.match(r"\s*> \*\*In short\.\*\*\s*(.+?)(?:\n\n|\n(?!>))", pg["text"], re.S)
            gist = re.sub(r"\s*\n>\s*", " ", short.group(1)) if short else ""
            gist = first_sentences(CITE.sub("", gist), 2)
            rows.append(f'<li><a href="{sid}.html"><span class="kicker">{full_} · {num(minutes)} {L("min", "دقیقه")}'
                        f'{L(" · draft", " · پیش‌نویس") if draft else ""}</span><b>{title}</b><span class="gist">{md.inline(gist)}</span></a></li>')
        hub = (hero(art, ch.art, root, kicker=f"{L('Deeper study', 'مطالعهٔ عمیق‌تر')} · {ch.label}", title=html.escape(ch.title), cls="band",
                    lede=L("For when a section didn't click, or left you wanting more: each page explains the idea again, "
                           "tells the full story, fills in what the chapter leaves out, and gives the sources.",
                           "برای وقتی که بخشی جا نیفتاد یا دلتان بیشتر خواست: هر صفحه ایده را دوباره توضیح می‌دهد، "
                           "داستانِ کاملش را می‌گوید، آنچه فصل نیاورده را پر می‌کند و منبع‌ها را می‌دهد."))
               + f'<main id="main" class="wrap" style="padding-top:30px;padding-bottom:80px">'
               f'<p class="sch-status"><a href="../../guide/{ch.href}"><span aria-hidden="true">{L("←", "→")}</span> {L("Back to", "بازگشت به")} {html.escape(ch.label)}</a></p>'
               f'<ul class="deep-hub">{"".join(rows)}</ul></main>')
        rendered.append((f"deeper/{slug}/index.html", hub, root, ch, f"{ch.label}: {ch.title}", None))
        built.add(f"{slug}/index.html")
        hubs.append((ch, len(order)))
    svgs = render_mermaid(md, prune=False) if rendered else {}
    for path, body, root, ch, title, sid in rendered:
        hub = path.endswith("/index.html")
        slug = path.split("/")[1]
        # the same page in the other language: Persian for an English page that has a translation, the English page for a Persian one
        if fa:
            other = path
        elif hub:
            other = path if DEEP_FA.get(slug) else f"guide/{ch.href}"
        else:
            other = path if sid in DEEP_FA.get(slug, {}) else f"guide/{ch.href}"
        page(path, other_rel=other, root=root, title=L("Deeper study: ", "مطالعهٔ عمیق‌تر: ") + title,
             desc=((L(f"Deeper study for {ch.label}, {ch.title}.", f"مطالعهٔ عمیق‌تر برای {ch.label}، {ch.title}.")) if hub else
                   L(f"{title}: the idea again, the full story, what the chapter leaves out, and sources.",
                     f"{title}: ایده را دوباره بیاموزید، داستانِ کامل، آنچه فصل نیاورده و منبع‌ها.")),
             body=place_diagrams(body, md, svgs), current="guide", hero_img=(art.src(ch.art, root), art.srcset(ch.art, root)),
             bar="clear", reader=not hub)
    if hubs:
        rows = "".join(f'<li><a href="{c.slug}/index.html"><span class="kicker">{html.escape(c.label)} · {num(n)} {L("page" + ("s" if n != 1 else ""), "صفحه")}</span>'
                       f'<b>{html.escape(c.title)}</b></a></li>' for c, n in sorted(hubs, key=lambda t: t[0].num))
        idx = (hero(art, "guide", up(1), kicker=L("Deeper study", "مطالعهٔ عمیق‌تر"), title=L("Going deeper", "ژرف‌تر برویم"), cls="band",
                    lede=L("For each section of the guide that rewards it: the idea explained again, the full story behind it, "
                           "what the chapter leaves out, and the sources.",
                           "برای هر بخشِ راهنما که ارزشش را دارد: ایده دوباره توضیح داده می‌شود، داستانِ کامل پشتِ آن، "
                           "آنچه فصل نیاورده، و منبع‌ها."))
               + f'<main id="main" class="wrap" style="padding-top:30px;padding-bottom:80px"><ul class="deep-hub">{rows}</ul></main>')
        page("deeper/index.html", other_rel="deeper/index.html" if (DEEP_FA and not fa) or fa else "guide/index.html", root=up(1),
             title=L("Deeper study", "مطالعهٔ عمیق‌تر"),
             desc=L("The sections of the guide explained further: the full story, what the chapters leave out, and sources.",
                    "بخش‌های راهنما با توضیحِ بیشتر: داستانِ کامل، آنچه فصل‌ها نیاورده‌اند، و منبع‌ها."),
             body=idx, current="guide", hero_img=(art.src("guide", up(1)), art.srcset("guide", up(1))), bar="clear")
        built.add("index.html")
    ddir = OUT() / "deeper"
    skip = ("src", "src-fa", "data", "fa") if not fa else ()
    for p in ddir.glob("**/*.html"):  # a page no longer built (a draft, after a preview) leaves nothing behind
        if p.relative_to(ddir).parts[0] not in skip and p.relative_to(ddir).as_posix() not in built:
            p.unlink()
    if ddir.exists():
        for d in sorted((p for p in ddir.glob("*/") if p.is_dir() and p.name not in skip), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
    if problems:
        raise SystemExit(f"deeper: {problems} problem(s) in published pages")


# ----------------------------------------------------------------------------- read-along (the narration with its text)

def sync_stamp(ch):
    """When a chapter's sync file last changed in git, as the EPUB's modification date (stable across builds)."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", sync_path(ch).relative_to(ROOT).as_posix()], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not out:
        return None
    return datetime.fromisoformat(out).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sync_path(ch, lang=None):
    """Where a chapter's narration line timings are kept: guide/fa/audio/sync/ (Persian) or guide/audio/sync/ (English)."""
    return GUIDE / ("fa/audio" if (lang or LANG) == "fa" else "audio") / "sync" / f"{ch.slug}.json"


def chapter_sync(ch):
    """The narration's line timings for a chapter in the language being built, when it has them."""
    if not (fa_voice(ch) if LANG == "fa" else ch.track):
        return None
    p = sync_path(ch)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def curly(t):
    """Typographic quotes and apostrophes for English narration text, which keeps straight ones for the voices."""
    t = re.sub(r"'(?=\d0s\b)", "’", t)
    t = re.sub(r'(^|[\s(\[{—–-])"', "\\1“", t).replace('"', "”")
    return re.sub(r"(^|[\s(\[{—–-])'", "\\1‘", t).replace("'", "’")


def readalong_lines(sync, times=False):
    """The narration's lines as XHTML, one element per spoken line, with ids l0001… (and, for the web
    page, their times). The same markup goes into the EPUB, where the Media Overlay points at the ids.
    Dialogue lines carry their speaker's label from the chapter (A, B; الف, ب), which is not spoken; lines
    read by the second voice (and, in English, the third) are marked, so a reader can see the voices take turns."""
    out = []
    tag = {"opening": ("h1", ""), "section": ("h2", ""), "subsection": ("h3", ""), "quote": ("p", "quote"),
           "attr": ("p", "attr"), "cue": ("p", "label"), "label": ("p", "label"), "question": ("p", "question"),
           "answer": ("p", "answer"), "item": ("p", "item"), "aside": ("p", "aside")}
    who = {"voice1": "الف", "voice2": "ب", "voice3": "ج"} if LANG == "fa" else {"voice1": "A", "voice2": "B", "voice3": "C"}
    mark = {"second": "v2", "third": "v3"}
    for i, line in enumerate(sync["lines"], 1):
        kind = line["kind"]
        el, cls = tag.get(kind, ("p", "dialogue" if kind in who else ""))
        classes = " ".join(c for c in ("line", cls, mark.get(line.get("voice"), "")) if c)
        at = f' data-b="{line["begin"]}" data-e="{line["end"]}"' if times else ""
        label = f'<span class="who">{who[kind]}:</span> ' if kind in who else ""
        out.append(f'<{el} id="l{i:04d}" class="{classes}"{at}>{label}{html.escape(line["text"] if LANG == "fa" else curly(line["text"]), quote=False)}</{el}>')
    return "".join(out)


def narration_credit(sync):
    """Who narrates a chapter, for its read-along page and EPUB: (credit, narrators, rights)."""
    n = sync.get("narration") or {}
    if LANG == "en":
        return ("Read by three synthetic ElevenLabs voices: Arthur narrates; Jane reads every third section, asks the quiz "
                "questions and is B in dialogues; Adam Stone reads the quotations and is A in dialogues.",
                ["Arthur (ElevenLabs synthetic voice)", "Jane (ElevenLabs synthetic voice)", "Adam Stone (ElevenLabs synthetic voice)"],
                "Narration: ElevenLabs synthetic voices.")
    if n.get("engine") == "ElevenLabs":
        return ("روایت با دو صدای ساختگیِ ElevenLabs: صدای مردانه راویِ اصلی است و صدای زنانه بخش‌ها را به نوبت با او می‌خواند، "
                "نقل‌قول‌ها و پرسش‌های آزمونک را می‌خواند، و در گفت‌وگوها نقشِ «ب» را دارد.",
                ["صدای ساختگیِ مردانه (ElevenLabs)", "صدای ساختگیِ زنانه (ElevenLabs)"],
                "روایت: صداهای ساختگیِ ElevenLabs.")
    return ("روایت با صدایی ساختگی، با مدلِ متن‌به‌گفتارِ فارسیِ «گویا بزرگ ۱٫۵» (Chatterbox، آموزش‌دیده برای فارسی).",
            ["صدای ساختگی (گویا بزرگ ۱٫۵)"],
            "روایت: مدلِ «گویا بزرگ ۱٫۵»، مجوزِ CC BY-NC 4.0 (فقط استفادهٔ غیرتجاری).")


def clock_value(sec):
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return f"{int(h)}:{int(m):02d}:{s:06.3f}"


READALONG_CSS_FA = """@font-face{font-family:"Vazirmatn";font-weight:100 900;src:url(fonts/vazirmatn.woff2) format("woff2")}
@font-face{font-family:"Vazirmatn";font-weight:100 900;src:url(fonts/vazirmatn-latin.woff2) format("woff2");unicode-range:U+0000-024F}
body{font-family:"Vazirmatn",serif;line-height:1.95;text-align:right;margin:0 5%}
h1{font-size:1.6em;line-height:1.4;margin:1.2em 0 .8em}
h2{font-size:1.3em;margin:1.6em 0 .5em}
h3{font-size:1.1em;margin:1.3em 0 .4em}
p{margin:0 0 .8em}
.quote{margin:1em 1.5em .3em;font-size:1.05em}
.attr{margin:0 1.5em 1em;color:#555;font-size:.9em}
.label,.question{font-weight:bold}
.dialogue{margin-right:1.2em}
.item{margin-right:1em}
.who{font-weight:bold;color:#6b4b2a}
.v2{border-right:3px solid #c9a27a;padding-right:.6em}
.-epub-media-overlay-active{background-color:#fde68a;color:#111;border-radius:4px}
.title-page{text-align:center;margin-top:18%}
.title-page .book{font-size:2em;font-weight:bold;margin:0 0 .3em}
.title-page .sub{color:#555;margin:0 0 2.5em}
.title-page .chapter{font-size:1.4em;margin:0 0 .4em}
.title-page .kind{color:#555}
.colophon h2{font-size:1.2em;margin-top:1.4em}
.colophon p,.colophon li{font-size:.95em}
.player{margin:.6em 0 1.6em;padding:.6em .8em;border:1px solid #d8c9b5;border-radius:10px;text-align:center}
.player p{margin:0 0 .4em;font-size:.9em;color:#555}
.player audio{width:100%}
.cover{text-align:center;margin:0;padding:0}
.cover img{max-width:100%;max-height:100vh}
pre.license{white-space:pre-wrap;text-align:left;font-size:.8em;font-family:serif}
"""

READALONG_CSS_EN = """@font-face{font-family:"Source Serif 4";font-weight:200 900;src:url(fonts/sourceserif4.woff2) format("woff2")}
@font-face{font-family:"Source Serif 4";font-weight:200 900;src:url(fonts/sourceserif4-ext.woff2) format("woff2");unicode-range:U+0100-024F,U+1E00-1EFF}
body{font-family:"Source Serif 4",serif;line-height:1.7;margin:0 5%}
h1{font-size:1.6em;line-height:1.3;margin:1.2em 0 .8em}
h2{font-size:1.3em;margin:1.6em 0 .5em}
h3{font-size:1.1em;margin:1.3em 0 .4em}
p{margin:0 0 .8em}
.quote{margin:1em 1.5em .3em;font-size:1.05em;font-style:italic}
.attr{margin:0 1.5em 1em;color:#555;font-size:.9em}
.label,.question{font-weight:bold}
.dialogue{margin-left:1.2em}
.item{margin-left:1em}
.who{font-weight:bold;color:#6b4b2a}
.v2{border-left:3px solid #c9a27a;padding-left:.6em}
.v3{border-left:3px dotted #7a8fa6;padding-left:.6em}
.-epub-media-overlay-active{background-color:#fde68a;color:#111;border-radius:4px}
.title-page{text-align:center;margin-top:18%}
.title-page .book{font-size:2em;font-weight:bold;margin:0 0 .3em}
.title-page .sub{color:#555;margin:0 0 2.5em}
.title-page .chapter{font-size:1.4em;margin:0 0 .4em}
.title-page .kind{color:#555}
.colophon h2{font-size:1.2em;margin-top:1.4em}
.colophon p,.colophon li{font-size:.95em}
.player{margin:.6em 0 1.6em;padding:.6em .8em;border:1px solid #d8c9b5;border-radius:10px;text-align:center}
.player p{margin:0 0 .4em;font-size:.9em;color:#555}
.player audio{width:100%}
.cover{text-align:center;margin:0;padding:0}
.cover img{max-width:100%;max-height:100vh}
pre.license{white-space:pre-wrap;font-size:.8em;font-family:serif}
"""


def build_readalong(ch, sync, art, stamp):
    """For a narrated chapter: a read-along web page, and the parts of a chapter EPUB 3 with
    Media Overlays, which the page's "EPUB" button packs together with the MP3 in the reader's browser
    (so the site keeps one copy of the audio). The EPUB stands on its own as a published ebook: cover,
    title page, the chapter with its synchronized narration, a colophon with credits and licences, a table
    of contents and landmarks, and full publication and accessibility metadata."""
    import uuid
    fa = LANG == "fa"
    lng, dirn = ("fa", "rtl") if fa else ("en", "ltr")
    book = SITE_FA if fa else SITE
    title = f"{ch.label}: {ch.title}"
    audio = sync["file"]
    body = readalong_lines(sync)
    parts = OUT() / "guide" / "epub" / ch.slug
    x = lambda v: html.escape(str(v), quote=True)
    credit, narrators, narration_rights = narration_credit(sync)
    blurb = html.unescape(strip_tags(Markdown().inline(ch.blurb))) if ch.blurb else ""
    heads = [(i, l["text"]) for i, l in enumerate(sync["lines"], 1) if l["kind"] == "section"]
    uid = uuid.uuid5(uuid.NAMESPACE_URL, f"{LIVE}{lang_prefix()}guide/{ch.href}#readalong")
    doc = lambda name, t, inner, epub_type="": (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{lng}" xml:lang="{lng}" dir="{dirn}">'
        f'<head><meta charset="utf-8"/><title>{x(t)}</title><link rel="stylesheet" href="style.css"/></head>'
        f'<body{f" epub:type={chr(34)}{epub_type}{chr(34)}" if epub_type else ""}>{inner}</body></html>')
    cover = doc("cover", L("Cover", "جلد"), f'<section class="cover" epub:type="cover"><img src="cover.jpg" alt="{x(art.alt("audio"))}"/></section>')
    titlepage = doc("title", book, '<section class="title-page" epub:type="titlepage">'
                    f'<p class="book">{x(book)}</p><p class="sub">{L("A complete guide to knowledge, evidence and critical thinking", "راهنمای کاملِ معرفت، شواهد و تفکرِ نقادانه")}</p>'
                    f'<p class="chapter">{x(title)}</p><p class="kind">{L("Audiobook with text", "کتابِ صوتی همراه با متن")}</p></section>')
    # a plain player at the start: every reader that plays audio shows it (Apple Books plays read-along only in
    # fixed-layout books, so there this is the way to listen); where Media Overlays work, the text follows the voice
    narr = L("This chapter’s narration", "روایتِ صوتیِ این فصل")
    player = (f'<aside class="player" epub:type="sidebar" aria-label="{narr}"><p>{narr} · {x(minutes_label(sync["duration"]))}</p>'
              f'<audio controls="controls" preload="metadata" src="audio/{x(audio)}"><p>'
              + L("This app does not play audio; the audio file is inside this book.", "این برنامه صدا را پخش نمی‌کند؛ فایلِ صوتی در همین کتاب است.")
              + '</p></audio></aside>')
    chapter = doc("chapter", title, f'<section epub:type="chapter" role="doc-chapter">{player}{body}</section>', "bodymatter")
    how = L("This file holds the chapter’s text and its narration together. A player at the start of the chapter plays the "
            "narration in any app that plays audio, Apple Books included. In apps that support EPUB 3 read-aloud (Media Overlays) "
            "in ordinary books, such as Thorium Reader, press the app’s own play button: the narration starts and the sentence "
            "being read is highlighted. (Apple Books shows this only in fixed-layout books.) In apps without sound, the text "
            "reads like any ebook.",
            "این فایل متن و روایتِ فصل را با هم دارد. در آغازِ فصل پخش‌کننده‌ای هست که در هر برنامه‌ای که صدا پخش می‌کند، "
           "از جمله Apple Books، روایت را پخش می‌کند. در برنامه‌هایی که «خواندنِ همراه با صدا»ی EPUB 3 (Media Overlays) را در "
           "کتاب‌های معمولی پشتیبانی می‌کنند، مانندِ Thorium Reader، دکمهٔ پخشِ خودِ برنامه را بزنید: روایت شروع می‌شود و جمله‌ای که "
           "خوانده می‌شود رنگی می‌شود. (Apple Books این همراهی را فقط در کتاب‌های با صفحه‌آراییِ ثابت نشان می‌دهد.) "
           "در برنامه‌های بی‌صدا، متن مثلِ هر کتابِ الکترونیکی خوانده می‌شود.")
    font_name, font_ofl = ("Vazirmatn", "vazirmatn-OFL.txt") if fa else ("Source Serif 4", "source-serif-4-OFL.txt")
    about = L("About this book", "دربارهٔ این کتاب")
    colophon = doc("colophon", about, '<section class="colophon" epub:type="colophon">'
                   f'<h1>{about}</h1>'
                   + (f'<p>{x(title)}، از «{x(SITE_FA)}»{("؛ " + x(blurb)) if blurb else ""}</p>' if fa else
                      f'<p>{x(title)}, from {x(SITE)}{("; " + x(blurb)) if blurb else ""}</p>')
                   + f'<h2>{L("How to listen and read", "چگونه بشنوید و بخوانید")}</h2><p>{x(how)}</p>'
                   + L('<h2>The text</h2><p>The text of this book is what the narration reads: the chapter, adapted for listening. '
                       'Numbers and symbols are written out in words, tables are read as sentences, diagrams are left out, and the '
                       'chapter ends with a spoken quiz. In dialogues the speaker’s letter (A, B) is shown but not read.</p>',
                       '<h2>متن</h2><p>متنِ این کتاب همان است که روایت می‌کند: متنِ فصل، که برای شنیدن تنظیم شده است. عددها و نمادها به کلمه '
                   'درآمده‌اند، جدول‌ها جمله‌به‌جمله خوانده می‌شوند، نمودارها کنار گذاشته شده‌اند، و فصل با آزمونکی شفاهی تمام می‌شود. '
                   'در گفت‌وگوها نامِ گوینده («الف»، «ب») فقط نوشته شده و خوانده نمی‌شود.</p>')
                   + f'<h2>{L("Narration", "روایت")}</h2><p>{x(credit)}</p>'
                   + L(f'<h2>Cover image and typeface</h2><ul><li>Cover image: {art.caption("audio")}; public domain, via Wikimedia Commons.</li>'
                       '<li>Typeface: Source Serif 4, under the <a href="license.xhtml">SIL Open Font License 1.1</a>.</li></ul>'
                       f'<p>Identifier: urn:uuid:{uid}</p></section>',
                       '<h2>تصویرِ جلد و قلم</h2><ul>'
                       f'<li>تصویرِ جلد: {art.caption("audio")}؛ مالکیتِ عمومی، از ویکی‌انبار.</li>'
                       '<li>قلم: Vazirmatn، با <a href="license.xhtml">مجوزِ SIL Open Font License 1.1</a>.</li></ul>'
                       f'<p>شناسه: urn:uuid:{uid}</p></section>'))
    ofl = (ASSETS / "fonts" / "licenses" / font_ofl).read_text(encoding="utf-8")
    license_doc = doc("license", L("Typeface licence", "مجوزِ قلم"),
                      f'<section epub:type="appendix"><h1>{L("Licence for the Source Serif 4 typeface", "مجوزِ قلمِ Vazirmatn")}</h1>'
                      f'<pre class="license" lang="en" xml:lang="en" dir="ltr">{x(ofl)}</pre></section>')
    smil = ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<smil xmlns="http://www.w3.org/ns/SMIL" xmlns:epub="http://www.idpf.org/2007/ops" version="3.0">'
            '<body><seq id="chapter-seq" epub:textref="chapter.xhtml" epub:type="chapter">'
            + "".join(f'<par id="p{i:04d}"><text src="chapter.xhtml#l{i:04d}"/>'
                      # a clip must not be empty (EPUB 3): a line the audio has no time for gets a millisecond
                      f'<audio src="audio/{x(audio)}" clipBegin="{l["begin"]:.3f}s" clipEnd="{max(l["end"], l["begin"] + 0.001):.3f}s"/></par>'
                      for i, l in enumerate(sync["lines"], 1))
            + "</seq></body></smil>")
    duration = clock_value(sync["duration"])
    access = L("The full text with synchronized narration (EPUB 3 Media Overlays): read only, listen only, or both together; "
               "a table of contents and section headings for navigation. The only image is the cover, which has alternative text.",
               "متنِ کامل همراه با روایتِ هم‌زمان (EPUB 3 Media Overlays): می‌توان فقط خواند، فقط شنید، یا هر دو را با هم؛ "
              "فهرستِ مطالب و عنوان‌های بخش‌ها برای جابه‌جایی آمده‌اند. تنها تصویر، جلد است و متنِ جایگزین دارد.")
    meta = [f'<dc:identifier id="uid">urn:uuid:{uid}</dc:identifier>',
            f'<dc:title id="t1">{x(title)}</dc:title>', '<meta refines="#t1" property="title-type">main</meta>',
            f'<dc:title id="t2">{x(book)}</dc:title>', '<meta refines="#t2" property="title-type">collection</meta>',
            f'<dc:language>{lng}</dc:language>', f'<dc:creator>{x(book)}</dc:creator>', f'<dc:publisher>{x(book)}</dc:publisher>',
            f'<dc:description>{x(blurb or title)}</dc:description>',
            *[f'<dc:subject>{v}</dc:subject>' for v in (("معرفت‌شناسی", "فلسفه", "تفکرِ نقادانه") if fa else
                                                        ("Epistemology", "Philosophy", "Critical thinking"))],
            f'<dc:rights>{x(("متن: «" + SITE_FA + "». " + narration_rights + " تصویرِ جلد: مالکیتِ عمومی. قلم: Vazirmatn (SIL OFL 1.1).") if fa else ("Text: " + SITE + ". " + narration_rights + " Cover image: public domain. Typeface: Source Serif 4 (SIL OFL 1.1)."))}</dc:rights>',
            f'<meta property="dcterms:modified">{stamp}</meta>',
            f'<meta property="belongs-to-collection" id="series">{x(book)}</meta>',
            '<meta refines="#series" property="collection-type">series</meta>',
            f'<meta refines="#series" property="group-position">{ch.num}</meta>',
            f'<meta property="media:duration" refines="#overlay">{duration}</meta>', f'<meta property="media:duration">{duration}</meta>',
            *[f'<meta property="media:narrator">{x(n)}</meta>' for n in narrators],
            '<meta property="media:active-class">-epub-media-overlay-active</meta>',
            *[f'<meta property="schema:accessMode">{v}</meta>' for v in ("textual", "auditory", "visual")],
            *[f'<meta property="schema:accessModeSufficient">{v}</meta>' for v in ("textual", "auditory")],
            *[f'<meta property="schema:accessibilityFeature">{v}</meta>'
              for v in ("synchronizedAudioText", "tableOfContents", "readingOrder", "structuralNavigation", "alternativeText")],
            '<meta property="schema:accessibilityHazard">none</meta>',
            f'<meta property="schema:accessibilitySummary">{x(access)}</meta>']
    items = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
             '<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>',
             '<item id="title-page" href="title.xhtml" media-type="application/xhtml+xml"/>',
             '<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml" media-overlay="overlay"/>',
             '<item id="colophon" href="colophon.xhtml" media-type="application/xhtml+xml"/>',
             '<item id="license" href="license.xhtml" media-type="application/xhtml+xml"/>',
             '<item id="overlay" href="chapter.smil" media-type="application/smil+xml"/>',
             f'<item id="audio" href="audio/{x(audio)}" media-type="audio/mpeg"/>',
             '<item id="css" href="style.css" media-type="text/css"/>',
             *([f'<item id="font" href="fonts/vazirmatn.woff2" media-type="font/woff2"/>',
                '<item id="font-latin" href="fonts/vazirmatn-latin.woff2" media-type="font/woff2"/>'] if fa else
               ['<item id="font" href="fonts/sourceserif4.woff2" media-type="font/woff2"/>',
                '<item id="font-ext" href="fonts/sourceserif4-ext.woff2" media-type="font/woff2"/>']),
             '<item id="cover" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>']
    spine = ('<itemref idref="cover-page"/><itemref idref="title-page"/><itemref idref="chapter"/>'
             '<itemref idref="colophon"/><itemref idref="license" linear="no"/>')
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="{lng}" dir="{dirn}">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{"".join(meta)}</metadata>'
           f'<manifest>{"".join(items)}</manifest><spine page-progression-direction="{dirn}">{spine}</spine></package>')
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
           f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{lng}" xml:lang="{lng}" dir="{dirn}">'
           f'<head><meta charset="utf-8"/><title>{L("Contents", "فهرست")}</title><link rel="stylesheet" href="style.css"/></head><body>'
           f'<nav epub:type="toc" id="toc" role="doc-toc"><h1>{L("Contents", "فهرست")}</h1><ol>'
           f'<li><a href="title.xhtml">{x(book)}</a></li>'
           f'<li><a href="chapter.xhtml">{x(title)}</a>'
           + (f'<ol>{"".join(f"<li><a href={chr(34)}chapter.xhtml#l{i:04d}{chr(34)}>{x(t)}</a></li>" for i, t in heads)}</ol>' if heads else "")
           + f'</li><li><a href="colophon.xhtml">{about}</a></li></ol></nav>'
           f'<nav epub:type="landmarks" id="landmarks" hidden="hidden"><h2>{L("Guide", "راهنما")}</h2><ol>'
           f'<li><a epub:type="cover" href="cover.xhtml">{L("Cover", "جلد")}</a></li>'
           f'<li><a epub:type="titlepage" href="title.xhtml">{L("Title page", "صفحهٔ عنوان")}</a></li>'
           f'<li><a epub:type="bodymatter" href="chapter.xhtml">{L("Start of text", "آغازِ متن")}</a></li>'
           f'<li><a epub:type="colophon" href="colophon.xhtml">{about}</a></li></ol></nav></body></html>')
    container = ('<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    texts = (("container.xml", container), ("package.opf", opf), ("nav.xhtml", nav), ("cover.xhtml", cover),
             ("title.xhtml", titlepage), ("chapter.xhtml", chapter), ("colophon.xhtml", colophon), ("license.xhtml", license_doc),
             ("chapter.smil", smil), ("style.css", READALONG_CSS_FA if fa else READALONG_CSS_EN))
    for name, text in texts:
        write(parts / name, text)
    top = up(3)  # from (fa/)guide/epub/<chapter>/ to the site root
    audio_at = "guide/fa/audio/" if fa else "guide/audio/"
    files = [["META-INF/container.xml", "container.xml"]] + [[f"OEBPS/{name}", name] for name, _ in texts[1:]]
    fonts = ([["OEBPS/fonts/vazirmatn.woff2", "vazirmatn-arabic-wght-normal.woff2"], ["OEBPS/fonts/vazirmatn-latin.woff2", "vazirmatn-latin-wght-normal.woff2"]]
             if fa else [["OEBPS/fonts/sourceserif4.woff2", "source-serif-4-latin-wght-normal.woff2"],
                         ["OEBPS/fonts/sourceserif4-ext.woff2", "source-serif-4-latin-ext-wght-normal.woff2"]])
    files += [[name, top + "assets/fonts/" + src] for name, src in fonts]
    files += [["OEBPS/cover.jpg", top + "assets/art/audiobook-cover.jpg"],
              [f"OEBPS/audio/{audio}", top + audio_at + audio]]
    write(parts / "files.json", json.dumps({"name": f"{ch.slug}-readalong{'-fa' if fa else ''}.epub", "files": files}, indent=0) + "\n")

    root = up(2)
    size = megabytes(track_bytes(ch.track))
    head = hero(art, ch.art, root, kicker=f'{L("Read along", "خواندن همراه با صدا")} · {ch.label}', title=html.escape(ch.title), cls="band")
    page_body = head + (
        f'<main id="main" class="wrap readalong" style="padding-top:26px;padding-bottom:90px">'
        f'<p class="ra-note">{L("The text follows the narration: the line being read is highlighted. Tap a line to listen from there.", "متن همراهِ روایت پیش می‌رود و خطی که خوانده می‌شود رنگی است. روی هر خط بزنید تا از همان‌جا بشنوید.")}'
        f' {html.escape(credit)}{L(" Lines read by Jane have a colored rule beside them, and lines read by Adam Stone a dotted one.", " خط‌هایی که صدای دوم می‌خواند، در کنارشان خطی رنگی دارند.") if sync.get("narration") else ""}</p>'
        f'<div class="ra-bar" role="region" aria-label="{L("Player", "پخش‌کننده")}">'
        f'<audio controls preload="metadata" src="{root}{audio_at}{audio}"></audio>'
        f'<div class="ra-tools"><label>{L("Speed", "سرعت")} <select class="ra-rate">'
        + "".join(f"<option{' selected' if v == '1' else ''}>{v}</option>" for v in ("0.8", "0.9", "1", "1.1", "1.25", "1.5", "1.75"))
        + '</select></label>'
        f'<button type="button" class="btn" data-epub="../epub/{ch.slug}/files.json">{icon("download")} EPUB ({size})</button>'
        f'<a class="btn" href="../{ch.href}">{icon("book")} {L("Chapter text", "متنِ فصل")}</a></div>'
        f'<p class="note" data-epub-note hidden></p></div>'
        f'<article class="ra-text" lang="{lng}" dir="{dirn}">{readalong_lines(sync, times=True)}</article>'
        f'<p class="ra-foot">{L("The EPUB holds this text and the narration together, for reading and listening offline. A player at the start of the chapter plays the narration in any e-reader, Apple Books included; the lines are highlighted as they are read in apps that support EPUB 3 read-aloud (Media Overlays) in ordinary books, such as Thorium Reader. Apple Books highlights along only in fixed-layout books.", "فایلِ EPUB همین متن و روایت را با هم دارد، برای خواندن و شنیدنِ بی‌اینترنت. پخش‌کننده‌ای در آغازِ فصل روایت را در هر کتاب‌خوانی، از جمله Apple Books، پخش می‌کند؛ رنگی‌شدنِ خط‌ها همراهِ خواندن در برنامه‌هایی کار می‌کند که «خواندنِ همراه با صدا»ی EPUB 3 (Media Overlays) را در کتاب‌های معمولی پشتیبانی می‌کنند، مانند Thorium Reader. Apple Books این همراهی را فقط در کتاب‌های با صفحه‌آراییِ ثابت نشان می‌دهد.")}</p>'
        '</main>')
    # the same page in the other language when that chapter has its read-along there too, else its chapter
    other = sync_path(ch, "en" if fa else "fa").exists()
    page(f"guide/listen/{ch.slug}.html", other_rel=None if other else f"guide/{ch.href}", root=root, title=L(f"Read along: {title}", f"خواندن همراه با صدا: {title}"),
         desc=L("The chapter's text, highlighted as the narration reads it.", "متنِ فصل، همراه با روایت، خط‌به‌خط."),
         body=page_body, current="audio", bar="clear")


# ----------------------------------------------------------------------------- main

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def page(rel, other_rel=None, **kw):
    """Write one page of the language being built, with a link to the same page in the other language
    (or to other_rel there, for a page that exists in one language only)."""
    path = OUT() / rel
    other = (ROOT / "fa" / (other_rel or rel)) if LANG == "en" else (ROOT / (other_rel or rel))
    alt = os.path.relpath(other, path.parent).replace(os.sep, "/")
    if alt.endswith("index.html"):
        alt = alt[:-len("index.html")] or "./"
    write(path, shell(alt=alt, **kw))


def load_chapters(tracks):
    chapters = {}
    for p in sorted(GUIDE.glob("[01][0-9]-*.md")):
        if LANG == "fa":
            fa = GUIDE / "fa" / p.name
            ch = Chapter(fa) if fa.exists() else Chapter(p, fallback=True)
        else:
            ch = Chapter(p)
        chapters[ch.num] = ch
    read_blurbs(chapters)
    for t in tracks:
        n = int(t["file"][:2])
        if n in chapters:
            chapters[n].track = t
    return chapters


def build_language(art, md, C, tracks):
    reset_learning()
    chapters = load_chapters(tracks)
    MENU_CHAPTERS.clear()
    MENU_CHAPTERS.update(chapters)
    if LANG == "en":
        EN_CHAPTERS.clear()
        EN_CHAPTERS.update(chapters)
    total = sum(t["duration"] for t in tracks)
    half = 0.25 <= (total / 3600) % 1 < 0.75
    total_label = (f"{int(total // 3600)}½ hours" if half else f"{round(total / 3600)} hours") if LANG == "en" else \
        (f"{num(int(total // 3600))}٫۵ ساعت" if half else f"{num(round(total / 3600))} ساعت")

    print(f"[{LANG}] guide")
    if LANG == "en":
        load_deeper(md)  # both languages' pages: the Persian build uses what the English build loaded
    later = []
    prepare_learning(md, C, chapters)
    for ch in chapters.values():
        build_chapter(ch, chapters, md, art, later, C)
    guide_index = build_guide_index(art, chapters, md, total_label)
    home_page = build_home(art, chapters, md, total_label, len(C.N))
    svgs = render_mermaid(md, prune=False)
    r1, r0, r2 = up(1), up(0), up(2)
    for path, body, root, ch, desc, chsw in later:
        body = place_diagrams(body, md, svgs)
        page(f"guide/{ch.href}", root=root, title=f"{ch.label}: {ch.title}" if ch.num <= 16 else ch.title, desc=desc, body=body,
             current="guide", hero_img=(art.src(ch.art, root), art.srcset(ch.art, root)), bar="clear", reader=True, focus=True,
             chapter_nav=chsw)
    build_deeper(chapters, md, art)
    build_reading_catalogue(ROOT, chapters, md, clean_chapter_markdown, DEEP, LANG, FA_HEADS, DEEP_FA)
    path_script = lambda root: (f'<script src="{av(root, "reading-path-i18n.js")}" defer></script>'
                                f'<script src="{av(root, "reading-path.js")}" defer></script>')
    page("reading-path/index.html", root=r1, title=L("Find your reading path", "مسیر مطالعهٔ خود را پیدا کنید"),
         desc=L("An adaptive reading guide for your questions, education, prior knowledge and available time.",
                "راهنمای مطالعه بر پایهٔ پرسش‌ها، تحصیلات، دانسته‌ها و زمان شما."),
         body=reading_path_body(LANG), current="guide",
         extra_head=f'<link rel="stylesheet" href="{av(r1, "reading-path.css")}">'
                    f'<script src="{av(r1, "reading-path-core.js")}" defer></script>',
         extra_scripts=path_script(r1))
    page("guide/index.html", root=r1, title=L("The guide", "راهنما"),
         desc=L("Contents of Mastering Epistemology: sixteen chapters on knowledge, evidence, and critical thinking.",
                "فهرستِ «تسلط بر معرفت‌شناسی»: شانزده فصل دربارهٔ معرفت، شواهد و تفکر نقادانه."),
         body=place_diagrams(guide_index, md, svgs), current="guide", hero_img=(art.src("guide", r1), art.srcset("guide", r1)), bar="clear", extra_scripts=path_script(r1))
    page("index.html", root=r0, title=site_name(),
         desc=L("A free, complete guide to epistemology and critical thinking: illustrated chapters, a bilingual concept map, and a narrated audio edition.",
                "راهنمایی رایگان و کامل دربارهٔ معرفت‌شناسی و تفکر نقادانه: فصل‌های مصوّر، نقشهٔ دوزبانهٔ مفاهیم و نسخهٔ صوتی."),
         body=home_page, hero_img=(art.src("home", r0), art.srcset("home", r0)), bar="clear",
         extra_scripts=path_script(r0))

    print(f"[{LANG}] concepts")
    pages = []
    (build_concepts if LANG == "en" else build_concepts_fa)(C, chapters, md, art, pages)
    for path, root, title, desc, body, current, key in pages:
        page(str(path.relative_to(OUT())), root=root, title=title, desc=desc, body=body, current=current,
             hero_img=(art.src(key, root), art.srcset(key, root)), bar="clear", reader=True, bilingual=(LANG == "en"))

    print(f"[{LANG}] concept map")
    build_map(C, chapters, md, art)

    print(f"[{LANG}] audio, credits, study pages")
    feed = build_feed(chapters, tracks, md)
    page("guide/audio/index.html", root=r2, title=L("Listen", "شنیدن"), desc=L("The narrated audio edition of Mastering Epistemology.", "نسخهٔ صوتیِ «تسلط بر معرفت‌شناسی»."),
         body=build_audio_page(art, chapters, tracks, feed), current="audio", hero_img=(art.src("audio", r2), art.srcset("audio", r2)), bar="clear")
    page("guide/download.html", root=r1, title=L("Download", "دریافت"),
         desc=L("Download the audiobook, the EPUB and the podcast feed, and save the guide for offline reading.",
                "دریافتِ کتاب صوتی، EPUB و خوراکِ پادکست، و ذخیرهٔ راهنما برای خواندنِ بی‌اینترنت."),
         body=build_download_page(art, chapters, tracks, feed), current="download", hero_img=(art.src("audio", r1), art.srcset("audio", r1)), bar="clear")
    page("guide/audio/about.html", root=r2, title=L("How the audio was made", "صوت چگونه ساخته شد"),
         desc=L("How the narrated audio edition was produced.", "نسخهٔ صوتی چگونه ساخته شد."), body=build_audio_about(art, md), current="audio", bar="clear")
    page("notes/index.html", root=r1, title=L("Notebook", "دفترچه"), desc=L("Your highlights and notes.", "نشانه‌گذاری‌ها و یادداشت‌های شما."),
         body=build_notebook(art), current="account", bar="clear")
    page("credits.html", root=r0, title=L("Credits", "منابع"), desc=L("Credits for the artwork, audio and fonts on this site.", "منابعِ آثار هنری، صدا و قلم‌های این سایت."),
         body=build_credits(art), bar="clear")
    page("privacy.html", root=r0, title=L("Privacy policy", "سیاستِ حریم خصوصی"),
         desc=L(f"How {SITE} handles your data: no tracking, and Google sign-in that keeps your study data in your own Google Drive.",
                f"شیوهٔ رفتارِ {SITE_FA} با داده‌های شما: بدونِ ردیابی، و ورود با گوگل که داده‌های مطالعه را در گوگل‌درایوِ خودتان نگه می‌دارد."),
         body=build_privacy(art), bar="clear")
    page("terms.html", root=r0, title=L("Terms of service", "شرایطِ استفاده"),
         desc=L(f"The terms for using {SITE}.", f"شرایطِ استفاده از {SITE_FA}."), body=build_terms(art), bar="clear")
    page("review/index.html", root=r1, title=L("Review questions", "مرور پرسش‌ها"),
         desc=L("Spaced review of the guide's self-check questions.", "مرورِ فاصله‌دارِ پرسش‌های خودآزماییِ راهنما."), body=build_review(art), current="account", bar="clear")
    page("account/index.html", root=r1, title=L("My study", "مطالعهٔ من"),
         desc=L("Sign in, sync your notes and progress, and set up the AI study companion.", "ورود، همگام‌سازیِ یادداشت‌ها و پیشرفت، و راه‌اندازیِ همراهِ هوشمندِ مطالعه."),
         body=build_account(art), current="account", bar="clear")
    write_learning_data(C)
    build_epub(chapters, art)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for ch in chapters.values():
        sync = chapter_sync(ch)
        if sync:
            build_readalong(ch, sync, art, sync_stamp(ch) or stamp)
    return chapters, pages


def main():
    global LANG, FA_AUDIO, FA_TRACKS
    art = Art()
    print("artwork")
    art.derive()
    art.derive_dots()
    audiobook_cover()
    (ASSETS / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    md = Markdown()
    tracks = load_js_json(GUIDE / "audio" / "tracks.js", "window.TRACKS =")
    fa_js = GUIDE / "fa" / "audio" / "tracks.js"
    fa_tracks = load_js_json(fa_js, "window.TRACKS =") if fa_js.exists() else []
    for t in fa_tracks:
        t["fa"] = True
    FA_TRACKS = {int(t["file"][:2]): t for t in fa_tracks}
    FA_AUDIO = bool(FA_TRACKS)
    C = Concepts()
    LANG = "en"
    chapters, pages = build_language(art, md, C, tracks)
    write(ROOT / "404.html", shell(root="", title="Page not found", desc="Page not found.", body=build_404(art), bar="clear")
          .replace("<meta charset=\"utf-8\">", "<meta charset=\"utf-8\">\n" + BASE_404, 1))
    LANG = "fa"
    fa_chapters, _ = build_language(art, md, C, [FA_TRACKS.get(int(t["file"][:2]), t) for t in tracks])
    LANG = "en"
    render_mermaid(md, prune=True)
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    print("offline")
    write(ROOT / "manifest.webmanifest", json.dumps(MANIFEST, indent=2) + "\n")
    write(ROOT / "offline.json", json.dumps(build_offline_list(), indent=0) + "\n")
    done = sum(1 for c in fa_chapters.values() if not c.fallback)
    print(f"done: {len(chapters)} chapters ({done} translated into Persian), {len(pages)} concept pages")




if __name__ == "__main__":
    main()
