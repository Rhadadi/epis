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
    fa/index.html                       the Persian starting page
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
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
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
SITE_FA = "تسلط بر معرفت‌شناسی"
EPUB_NAME = "mastering-epistemology.epub"
EPUB_NAME_FA = "mastering-epistemology-fa.epub"
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
              "شانزده فصل، هر کدام با آزمونکی شفاهی در پایان. روایت با صدایی ساختگی است.")
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
    """The concept map (shared by both languages), opened in the language being built."""
    return f"{root}map/" + ("?lang=fa" if LANG == "fa" else "") + (f"#{frag}" if frag else "")


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

def shell(*, root, title, desc, body, current="", hero_img=None, extra_head="", bar="solid", reader=False, focus=False,
          alt=None, bilingual=False):
    h = home(root)
    nav = [("guide", f"{h}guide/", "book", L("Guide", "راهنما")), ("concepts", f"{h}concepts/", "grid", L("Concepts", "مفاهیم")),
           ("map", map_url(root), "map", L("Map", "نقشه")), ("audio", f"{h}guide/audio/", "phones", L("Listen", "شنیدن")),
           ("account", f"{h}account/", "user", L("My study", "مطالعهٔ من"))]
    here = ' aria-current="page"'
    links = "".join(f'<a href="{href}"{here if key == current else ""}>{icon(ic)}<span>{label}</span></a>'
                    for key, href, ic, label in nav)
    preload = (f'<link rel="preload" as="image" href="{hero_img[0]}" imagesrcset="{hero_img[1]}" imagesizes="100vw">'
               if hero_img else "")
    full_title = title if title == site_name() else f"{title} · {site_name()}"
    reader_btn = (f'<button class="tbtn rbtn" id="reader" type="button" aria-label="{L("Reading settings", "تنظیمات خواندن")}" '
                  f'title="{L("Reading settings (A)", "تنظیمات خواندن (A)")}" aria-expanded="false" aria-controls="rpanel">Aa</button>')
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
<link rel="stylesheet" href="{root}assets/fonts/fonts.css">
<link rel="stylesheet" href="{root}assets/site.css">
{preload}{extra_head}
<script>{BOOT}</script>
</head>
<body>
<a class="skip" href="#main">{L("Skip to content", "رفتن به متن")}</a>
<header class="bar {bar}">
  <a class="brand" href="{h}" aria-label="{site_name()}, {L("home", "صفحهٔ نخست")}">{LOGO}<span><b>{site_name()}</b><small>{L("Guide · Map · Audio", "راهنما · نقشه · صوت")}</small></span></a>
  <nav class="site-nav" aria-label="{L("Site", "سایت")}">{links}</nav>
  <button class="tbtn" id="search" type="button" aria-label="{L("Search the guide", "جست‌وجو در راهنما")}" title="{L("Search (/)", "جست‌وجو (/)")}">{icon("search")}</button>{ask_btn}{focus_btn}{reader_btn}{lang_btn}<button class="tbtn" id="theme" type="button" aria-label="{L("Theme", "پوسته")}"></button>
  <button class="tbtn" id="menu" type="button" aria-label="{L("Menu", "فهرست")}" aria-expanded="false" aria-controls="mnav">{icon("menu")}</button>
</header>
<nav class="mnav" id="mnav" aria-label="{L("Menu", "فهرست")}" hidden>{links}<span class="sep"></span>
  <a href="{h}notes/">{icon("pen")}<span>{L("Notebook", "دفترچه")}</span></a><a href="{h}review/">{icon("review")}<span>{L("Review questions", "مرور پرسش‌ها")}</span></a>
  {f'<a href="{alt}" data-set-site-lang="{L("fa", "en")}" lang="{L("fa", "en")}">{icon("globe")}<span>{L("فارسی", "English")}</span></a>' if alt else ""}</nav>
{body}
{footer(root)}
<script src="{root}assets/site.js" defer></script>
<script src="{root}assets/notes.js" defer></script>
<script src="{root}assets/learn.js" defer></script>
<script src="{root}assets/ai-config.js" defer></script>
<script src="{root}assets/account.js" defer></script>
<script src="{root}assets/ai.js" defer></script>
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
    image = art.img(key, root, eager=True, alt=image_alt) if art.has(key) else ""
    return (f'<header class="hero {cls}" style="--art:{art.color(key)};--focus:{art.focus(key)}">{image}'
            f'<div class="hero-in">{"".join(parts)}{plate}</div></header>')


def label(art, key):
    i = art.meta(key)
    if not i.get("note"):
        return ""
    sep = L(", ", "، ")
    place = f"{sep}{esc(i['place'])}" if i.get("place") else ""
    return (f'<div class="art-label"><span class="kicker">{L("On the cover", "روی جلد")}</span>'
            f'<p><cite>{art.caption(key)}{place}.</cite> {esc(i["note"])}</p></div>')


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
        facts.append(f"{icon('phones')} {minutes_label(ch.track['duration'])} {L('audio', ch_audio(ch, 'صوت', 'صوت انگلیسی'))}")
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
        chips = "".join(f'<button class="chip" type="button" data-at="{s["s"]}">{esc(s["t"])} <small>{num(mmss(s["s"]))}</small></button>'
                        for s in sections)
        readalong_attrs = (f'data-readalong="listen/{ch.slug}.html" data-epub="epub/{ch.slug}/files.json" '
                           if chapter_sync(ch) else "")
        listen_card = (f'<section class="listen" data-audio="{audio_dir(root, ch.track)}{ch.track["file"]}" data-size="{track_bytes(ch.track)}" {readalong_attrs}data-thumb="{art.src(ch.art, root, 640)}" '
                       f'data-title="{attr(ch.label + ": " + ch.title)}" data-sections="{attr(json.dumps(sections, ensure_ascii=False))}" '
                       f'aria-label="{L("Listen to this chapter", "شنیدن این فصل")}">'
                       f'<button class="play" type="button" aria-label="{L("Play the narrated chapter", "پخش روایت صوتی فصل")}">{icon("play", "icon i-play")}'
                       f'<svg class="icon i-pause" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" stroke="none"/></svg></button>'
                       f'<span class="kicker">{L("Listen", "شنیدن")} · {minutes_label(ch.track["duration"])} · {L("narrated", ch_audio(ch, "روایت‌شده", "روایت به انگلیسی"))}</span>'
                       f'<h2>{L("Hear this chapter read aloud", "این فصل را بشنوید")} <span class="resume" style="font-weight:400;color:var(--dim)"></span></h2>'
                       f'<div class="row">{chips}</div></section>')
        actions += f'<button class="btn" type="button" data-listen>{icon("phones")} {L("Listen", "شنیدن")}</button>'
    dek = cite = None
    if epigraphs:
        dek, cite = md.inline(epigraphs[0][0]), md.inline(epigraphs[0][1])
        if ch.fallback:
            dek, cite = f'<span dir="ltr" lang="en">{dek}</span>', f'<span dir="ltr" lang="en">{cite}</span>'
    head = hero(art, ch.art, root, kicker=kicker, title=title_html(ch), dek=dek, cite=cite, facts=facts, actions=actions)

    listen_link = (f'<button type="button" data-listen>{icon("phones")} {L("Listen", "شنیدن")}</button>' if ch.track else "")
    focus_head = (f'<div class="focus-head"><span class="kicker">{kicker}</span><div class="ftitle" role="heading" aria-level="1">{title_html(ch)}</div>'
                  f'<div class="fmeta"><span>{num(ch.minutes)} {L("min read", "دقیقه مطالعه")}</span>{listen_link}'
                  f'<button type="button" data-focus-toggle>{L("Leave focus mode", "خروج از حالت تمرکز")}</button></div></div>')
    prev_ch, next_ch = chapters.get(ch.num - 1), chapters.get(ch.num + 1)
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
            f'<article data-slug="{ch.slug}" data-read-min="{ch.minutes}">{focus_head}{notice}{listen_card}<details class="mini-toc"><summary>{in_ch}</summary><ol{prose_attrs}>{toc}</ol></details>'
            f'<div class="prose"{prose_attrs}>{more_quotes}{body}</div>{deeper_box(ch, C, root) if ch.num <= 16 else ""}</article></main>{pager}')
    desc = ch.blurb.replace("*", "") or f"{ch.label}: {ch.title}"
    svgs_later.append((OUT() / "guide" / ch.href, page, root, ch, desc))


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
        sec = best_section(n["t"], chn, idx) if cid != "root" else None
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
            f'<h2>{L("Where to start", "از کجا شروع کنیم")}</h2></div></div><div class="prose" style="max-width:52rem">{paths}</div></div></section>'
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
                actions=(f'<a class="btn primary" href="{h}guide/01-what-is-epistemology.html">{L("Start reading", "شروع خواندن")} {icon("arrow")}</a>'
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
            f'<section class="section"><div class="wrap"><div id="resume"></div><div class="section-head"><div><span class="kicker">{L("Three ways in", "سه راهِ ورود")}</span>'
            f'<h2>{L("Read it, map it, or hear it", "بخوانید، روی نقشه ببینید، یا بشنوید")}</h2></div><p>{L("The same ideas, three ways. Start wherever suits you; everything is cross-linked.", "همان ایده‌ها، از سه راه. از هر جا که مناسب شماست آغاز کنید؛ همه‌چیز به هم پیوند خورده است.")}</p></div>{doors}'
            f'<div style="margin-top:28px">{stats}</div></div></section>'
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
            + L('The narration is generated with a synthetic voice, the open Kokoro-82M text-to-speech model, from scripts adapted for listening. '
                '<a href="about.html">How the audio was made</a>. Keyboard: <kbd>k</kbd> or space to play and pause, <kbd>j</kbd> and <kbd>l</kbd> to skip.',
                fa_audio('روایت با صدایی ساختگی، با مدلِ متن‌به‌گفتارِ فارسیِ «گویا بزرگ»، از متن‌هایی ساخته شده که برای شنیدن بازنویسی شده‌اند. ',
                         'روایت با صدایی ساختگی، با مدلِ متن‌به‌گفتارِ متن‌باز Kokoro-82M، از متن‌هایی ساخته شده که برای شنیدن بازنویسی شده‌اند. '
                         'این مدل صدای فارسی ندارد، به همین دلیل روایت به زبان انگلیسی است. ',
                         'روایت با صدایی ساختگی، با مدلِ متن‌به‌گفتارِ فارسیِ «گویا بزرگ»، از متن‌هایی ساخته شده که برای شنیدن بازنویسی شده‌اند. '
                         'روایتِ فارسی فصل‌به‌فصل آماده می‌شود؛ تا آن زمان فصل‌های دیگر با روایتِ انگلیسیِ مدلِ Kokoro-82M پخش می‌شوند. ')
                + '<a href="about.html">صوت چگونه ساخته شد</a>. '
                'صفحه‌کلید: <kbd>k</kbd> یا فاصله برای پخش و توقف، <kbd>j</kbd> و <kbd>l</kbd> برای جابه‌جایی.')
            + '</p></main>'
            f'<script>window.TRACKS={json.dumps(data, ensure_ascii=False)};window.TRACK_ART={json.dumps(thumbs)};</script>')
    return body


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
             ("IBM Plex Mono", "ibm-plex-mono"), ("Vazirmatn", "vazirmatn"), ("Atkinson Hyperlegible", "atkinson-hyperlegible")]
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
            + L(f'The audio edition is narrated by a synthetic voice: the <a href="https://huggingface.co/hexgrad/Kokoro-82M">Kokoro-82M</a> text-to-speech model '
                f'(Apache License 2.0), with pronunciation by <a href="https://github.com/hexgrad/misaki">misaki</a>. See <a href="{audio}">how the audio was made</a>.',
                fa_audio(FA_VOICES_CREDIT + 'نسخهٔ صوتیِ انگلیسی', 'نسخهٔ صوتی (به انگلیسی)') +
                f' با صدایی ساختگی روایت شده است: مدلِ متن‌به‌گفتارِ <a href="https://huggingface.co/hexgrad/Kokoro-82M">Kokoro-82M</a> '
                f'(مجوز آپاچی ۲٫۰)، با تلفظِ <a href="https://github.com/hexgrad/misaki">misaki</a>. <a href="{audio}">صوت چگونه ساخته شد</a> را ببینید.')
            + f'</p><h2>{L("Type", "حروف")}</h2><p>{fonts}{L(", all under the SIL Open Font License (follow a name for its licence).", "؛ همه با مجوزِ SIL Open Font License (برای دیدنِ مجوز، روی نام کلیک کنید).")}</p></div></main>')
    return body


FA_VOICES_CREDIT = (
    'نسخهٔ صوتیِ فارسی با صدایی ساختگی روایت شده است: مدلِ متن‌به‌گفتارِ '
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
        branch = C.branch(cid)
        sec = best_section(C.title(cid), BRANCH_CHAPTER.get(branch, 1), idx)
        num_ = sec[0] if sec else BRANCH_CHAPTER.get(branch, 1)
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
    branch = next((b for b, n in BRANCH_CHAPTER.items() if n == ch.num), None)
    if not ids and not branch:
        return ""
    lang = "fa" if LANG == "fa" else "en"
    chips = "".join(f'<a href="../concepts/{cid}.html" data-term="{attr(next((k for k, v in LEARN["terms"].items() if v.get("c") == cid), ""))}">'
                    f'{esc(C.title(cid, lang))}</a>' for cid in ids)
    links = [f'<a href="{map_url(root, branch)}">{icon("map")} {L("Explore this part of the concept map", "این بخش از نقشهٔ مفاهیم را ببینید")}</a>'] if branch else []
    if any(q["ch"] == ch.num for q in LEARN["questions"]):
        links.append(f'<a href="../review/#{ch.slug}">{icon("clock")} {L("Practise this chapter&#39;s questions", "تمرینِ پرسش‌های این فصل")}</a>')
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
    pages = ["", "index.html", "guide/", "guide/index.html", "concepts/", "credits.html", "guide/audio/", "guide/audio/index.html",
             "guide/audio/about.html", "notes/", "review/", "account/"]
    paths = list(pages) + ["fa/" + p for p in pages]
    paths += ["map/", "map/index.html", "guide/audio/tracks.js"] + (["guide/fa/audio/tracks.js"] if FA_AUDIO else [])
    paths += [
              "assets/site.css", "assets/site.js", "assets/notes.js", "assets/learn.js", "assets/ai-config.js", "assets/account.js", "assets/ai.js",
              "assets/data/terms.json", "assets/data/search.json", "assets/data/questions.json",
              "assets/data/terms-fa.json", "assets/data/search-fa.json", "assets/data/questions-fa.json",
              "assets/favicon.svg", "assets/data/concepts.js", "assets/fonts/fonts.css", "manifest.webmanifest", "assets/icon-192.png"]
    for base in ("", "fa/"):
        paths += sorted(f"{base}guide/{p.name}" for p in (ROOT / base / "guide").glob("[01][0-9]-*.html"))
        paths += sorted(f"{base}concepts/{p.name}" for p in (ROOT / base / "concepts").glob("*.html"))
    paths += sorted(f"fa/guide/listen/{p.name}" for p in (ROOT / "fa" / "guide" / "listen").glob("*.html"))
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


# ----------------------------------------------------------------------------- read-along (Persian narration)

def sync_stamp(ch):
    """When a chapter's sync file last changed in git, as the EPUB's modification date (stable across builds)."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", f"guide/fa/audio/sync/{ch.slug}.json"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not out:
        return None
    return datetime.fromisoformat(out).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def chapter_sync(ch):
    """The Persian narration's line timings for a chapter (guide/fa/audio/sync/), when it has them."""
    if not fa_voice(ch):
        return None
    p = GUIDE / "fa" / "audio" / "sync" / f"{ch.slug}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def readalong_lines(sync, times=False):
    """The narration's lines as XHTML, one element per spoken line, with ids l0001… (and, for the web
    page, their times). The same markup goes into the EPUB, where the Media Overlay points at the ids.
    Dialogue lines carry their speaker's label from the chapter (الف, ب), which is not spoken; lines read
    by the second narrator are marked, so a reader can see the voices take turns."""
    out = []
    tag = {"opening": ("h1", ""), "section": ("h2", ""), "subsection": ("h3", ""), "quote": ("p", "quote"),
           "attr": ("p", "attr"), "cue": ("p", "label"), "label": ("p", "label"), "question": ("p", "question"),
           "answer": ("p", "answer"), "item": ("p", "item"), "aside": ("p", "aside")}
    who = {"voice1": "الف", "voice2": "ب", "voice3": "ج"}
    for i, line in enumerate(sync["lines"], 1):
        kind = line["kind"]
        el, cls = tag.get(kind, ("p", "dialogue" if kind in who else ""))
        classes = " ".join(c for c in ("line", cls, "v2" if line.get("voice") == "second" else "") if c)
        at = f' data-b="{line["begin"]}" data-e="{line["end"]}"' if times else ""
        label = f'<span class="who">{who[kind]}:</span> ' if kind in who else ""
        out.append(f'<{el} id="l{i:04d}" class="{classes}"{at}>{label}{html.escape(line["text"], quote=False)}</{el}>')
    return "".join(out)


def narration_credit(sync):
    """Who narrates a chapter, for its read-along page and EPUB: (Persian credit, narrators, rights)."""
    n = sync.get("narration") or {}
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


READALONG_CSS = """@font-face{font-family:"Vazirmatn";font-weight:100 900;src:url(fonts/vazirmatn.woff2) format("woff2")}
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
.cover{text-align:center;margin:0;padding:0}
.cover img{max-width:100%;max-height:100vh}
pre.license{white-space:pre-wrap;text-align:left;font-size:.8em;font-family:serif}
"""


def build_readalong(ch, sync, art, stamp):
    """For a narrated Persian chapter: a read-along web page, and the parts of a chapter EPUB 3 with
    Media Overlays, which the page's "EPUB" button packs together with the MP3 in the reader's browser
    (so the site keeps one copy of the audio). The EPUB stands on its own as a published ebook: cover,
    title page, the chapter with its synchronized narration, a colophon with credits and licences, a table
    of contents and landmarks, and full publication and accessibility metadata."""
    import uuid
    title = f"{ch.label}: {ch.title}"
    audio = sync["file"]
    body = readalong_lines(sync)
    parts = OUT() / "guide" / "epub" / ch.slug
    x = lambda v: html.escape(str(v), quote=True)
    credit, narrators, narration_rights = narration_credit(sync)
    blurb = html.unescape(strip_tags(Markdown().inline(ch.blurb))) if ch.blurb else ""
    heads = [(i, l["text"]) for i, l in enumerate(sync["lines"], 1) if l["kind"] == "section"]
    uid = uuid.uuid5(uuid.NAMESPACE_URL, f"{LIVE}fa/guide/{ch.href}#readalong")
    doc = lambda name, t, inner, epub_type="": (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="fa" xml:lang="fa" dir="rtl">'
        f'<head><meta charset="utf-8"/><title>{x(t)}</title><link rel="stylesheet" href="style.css"/></head>'
        f'<body{f" epub:type={chr(34)}{epub_type}{chr(34)}" if epub_type else ""}>{inner}</body></html>')
    cover = doc("cover", "جلد", f'<section class="cover" epub:type="cover"><img src="cover.jpg" alt="{x(art.alt("audio"))}"/></section>')
    titlepage = doc("title", SITE_FA, '<section class="title-page" epub:type="titlepage">'
                    f'<p class="book">{x(SITE_FA)}</p><p class="sub">راهنمای کاملِ معرفت، شواهد و تفکرِ نقادانه</p>'
                    f'<p class="chapter">{x(title)}</p><p class="kind">کتابِ صوتی همراه با متن</p></section>')
    chapter = doc("chapter", title, f'<section epub:type="chapter" role="doc-chapter">{body}</section>', "bodymatter")
    how = ("این فایل متن و روایتِ فصل را با هم دارد. در برنامه‌هایی که «خواندنِ همراه با صدا»ی EPUB 3 (Media Overlays) را "
           "پشتیبانی می‌کنند، مانندِ Apple Books و Thorium Reader، دکمهٔ پخش را بزنید: روایت شروع می‌شود و جمله‌ای که خوانده می‌شود "
           "رنگی می‌شود. در برنامه‌های دیگر، متن مثلِ هر کتابِ الکترونیکی خوانده می‌شود.")
    colophon = doc("colophon", "دربارهٔ این کتاب", '<section class="colophon" epub:type="colophon">'
                   '<h1>دربارهٔ این کتاب</h1>'
                   f'<p>{x(title)}، از «{x(SITE_FA)}»{("؛ " + x(blurb)) if blurb else ""}</p>'
                   f'<h2>چگونه بشنوید و بخوانید</h2><p>{x(how)}</p>'
                   '<h2>متن</h2><p>متنِ این کتاب همان است که روایت می‌کند: متنِ فصل، که برای شنیدن تنظیم شده است. عددها و نمادها به کلمه '
                   'درآمده‌اند، جدول‌ها جمله‌به‌جمله خوانده می‌شوند، نمودارها کنار گذاشته شده‌اند، و فصل با آزمونکی شفاهی تمام می‌شود. '
                   'در گفت‌وگوها نامِ گوینده («الف»، «ب») فقط نوشته شده و خوانده نمی‌شود.</p>'
                   f'<h2>روایت</h2><p>{x(credit)}</p>'
                   '<h2>تصویرِ جلد و قلم</h2><ul>'
                   f'<li>تصویرِ جلد: {art.caption("audio")}؛ مالکیتِ عمومی، از ویکی‌انبار.</li>'
                   '<li>قلم: Vazirmatn، با <a href="license.xhtml">مجوزِ SIL Open Font License 1.1</a>.</li></ul>'
                   f'<p>شناسه: urn:uuid:{uid}</p></section>')
    ofl = (ASSETS / "fonts" / "licenses" / "vazirmatn-OFL.txt").read_text(encoding="utf-8")
    license_doc = doc("license", "مجوزِ قلم", f'<section epub:type="appendix"><h1>مجوزِ قلمِ Vazirmatn</h1><pre class="license" lang="en" xml:lang="en" dir="ltr">{x(ofl)}</pre></section>')
    smil = ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<smil xmlns="http://www.w3.org/ns/SMIL" xmlns:epub="http://www.idpf.org/2007/ops" version="3.0">'
            '<body><seq id="chapter-seq" epub:textref="chapter.xhtml" epub:type="chapter">'
            + "".join(f'<par id="p{i:04d}"><text src="chapter.xhtml#l{i:04d}"/>'
                      f'<audio src="audio/{x(audio)}" clipBegin="{l["begin"]:.3f}s" clipEnd="{l["end"]:.3f}s"/></par>'
                      for i, l in enumerate(sync["lines"], 1))
            + "</seq></body></smil>")
    duration = clock_value(sync["duration"])
    access = ("متنِ کامل همراه با روایتِ هم‌زمان (EPUB 3 Media Overlays): می‌توان فقط خواند، فقط شنید، یا هر دو را با هم؛ "
              "فهرستِ مطالب و عنوان‌های بخش‌ها برای جابه‌جایی آمده‌اند. تنها تصویر، جلد است و متنِ جایگزین دارد.")
    meta = [f'<dc:identifier id="uid">urn:uuid:{uid}</dc:identifier>',
            f'<dc:title id="t1">{x(title)}</dc:title>', '<meta refines="#t1" property="title-type">main</meta>',
            f'<dc:title id="t2">{x(SITE_FA)}</dc:title>', '<meta refines="#t2" property="title-type">collection</meta>',
            '<dc:language>fa</dc:language>', f'<dc:creator>{x(SITE_FA)}</dc:creator>', f'<dc:publisher>{x(SITE_FA)}</dc:publisher>',
            f'<dc:description>{x(blurb or title)}</dc:description>',
            '<dc:subject>معرفت‌شناسی</dc:subject>', '<dc:subject>فلسفه</dc:subject>', '<dc:subject>تفکرِ نقادانه</dc:subject>',
            f'<dc:rights>{x("متن: «" + SITE_FA + "». " + narration_rights + " تصویرِ جلد: مالکیتِ عمومی. قلم: Vazirmatn (SIL OFL 1.1).")}</dc:rights>',
            f'<meta property="dcterms:modified">{stamp}</meta>',
            f'<meta property="belongs-to-collection" id="series">{x(SITE_FA)}</meta>',
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
             '<item id="font" href="fonts/vazirmatn.woff2" media-type="font/woff2"/>',
             '<item id="font-latin" href="fonts/vazirmatn-latin.woff2" media-type="font/woff2"/>',
             '<item id="cover" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>']
    spine = ('<itemref idref="cover-page"/><itemref idref="title-page"/><itemref idref="chapter"/>'
             '<itemref idref="colophon"/><itemref idref="license" linear="no"/>')
    opf = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="fa" dir="rtl">'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{"".join(meta)}</metadata>'
           f'<manifest>{"".join(items)}</manifest><spine page-progression-direction="rtl">{spine}</spine></package>')
    nav = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
           '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="fa" xml:lang="fa" dir="rtl">'
           '<head><meta charset="utf-8"/><title>فهرست</title><link rel="stylesheet" href="style.css"/></head><body>'
           '<nav epub:type="toc" id="toc" role="doc-toc"><h1>فهرست</h1><ol>'
           f'<li><a href="title.xhtml">{x(SITE_FA)}</a></li>'
           f'<li><a href="chapter.xhtml">{x(title)}</a>'
           + (f'<ol>{"".join(f"<li><a href={chr(34)}chapter.xhtml#l{i:04d}{chr(34)}>{x(t)}</a></li>" for i, t in heads)}</ol>' if heads else "")
           + '</li><li><a href="colophon.xhtml">دربارهٔ این کتاب</a></li></ol></nav>'
           '<nav epub:type="landmarks" id="landmarks" hidden="hidden"><h2>راهنما</h2><ol>'
           '<li><a epub:type="cover" href="cover.xhtml">جلد</a></li>'
           '<li><a epub:type="titlepage" href="title.xhtml">صفحهٔ عنوان</a></li>'
           '<li><a epub:type="bodymatter" href="chapter.xhtml">آغازِ متن</a></li>'
           '<li><a epub:type="colophon" href="colophon.xhtml">دربارهٔ این کتاب</a></li></ol></nav></body></html>')
    container = ('<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    texts = (("container.xml", container), ("package.opf", opf), ("nav.xhtml", nav), ("cover.xhtml", cover),
             ("title.xhtml", titlepage), ("chapter.xhtml", chapter), ("colophon.xhtml", colophon), ("license.xhtml", license_doc),
             ("chapter.smil", smil), ("style.css", READALONG_CSS))
    for name, text in texts:
        write(parts / name, text)
    up4 = "../../../../"  # from fa/guide/epub/<chapter>/ to the site root
    files = [["META-INF/container.xml", "container.xml"]] + [[f"OEBPS/{name}", name] for name, _ in texts[1:]]
    files += [["OEBPS/fonts/vazirmatn.woff2", up4 + "assets/fonts/vazirmatn-arabic-wght-normal.woff2"],
              ["OEBPS/fonts/vazirmatn-latin.woff2", up4 + "assets/fonts/vazirmatn-latin-wght-normal.woff2"],
              ["OEBPS/cover.jpg", up4 + "assets/art/audiobook-cover.jpg"],
              [f"OEBPS/audio/{audio}", up4 + f"guide/fa/audio/{audio}"]]
    write(parts / "files.json", json.dumps({"name": f"{ch.slug}-readalong-fa.epub", "files": files}, indent=0) + "\n")

    root = up(2)
    size = megabytes(track_bytes(ch.track))
    head = hero(art, ch.art, root, kicker=f'{L("Read along", "خواندن همراه با صدا")} · {ch.label}', title=html.escape(ch.title), cls="band")
    page_body = head + (
        f'<main id="main" class="wrap readalong" style="padding-top:26px;padding-bottom:90px">'
        f'<p class="ra-note">{L("The text follows the narration: the line being read is highlighted. Tap a line to listen from there.", "متن همراهِ روایت پیش می‌رود و خطی که خوانده می‌شود رنگی است. روی هر خط بزنید تا از همان‌جا بشنوید.")}'
        f' {html.escape(credit)}{" خط‌هایی که صدای دوم می‌خواند، در کنارشان خطی رنگی دارند." if sync.get("narration") else ""}</p>'
        f'<div class="ra-bar" role="region" aria-label="{L("Player", "پخش‌کننده")}">'
        f'<audio controls preload="metadata" src="{root}guide/fa/audio/{audio}"></audio>'
        f'<div class="ra-tools"><label>{L("Speed", "سرعت")} <select class="ra-rate">'
        + "".join(f"<option{' selected' if v == '1' else ''}>{v}</option>" for v in ("0.8", "0.9", "1", "1.1", "1.25", "1.5", "1.75"))
        + '</select></label>'
        f'<button type="button" class="btn" data-epub="../epub/{ch.slug}/files.json">{icon("download")} EPUB ({size})</button>'
        f'<a class="btn" href="../{ch.href}">{icon("book")} {L("Chapter text", "متنِ فصل")}</a></div>'
        f'<p class="note" data-epub-note hidden></p></div>'
        f'<article class="ra-text" lang="fa" dir="rtl">{readalong_lines(sync, times=True)}</article>'
        f'<p class="ra-foot">{L("The EPUB holds this text and the narration together, with the same highlighting, for offline reading in apps that support EPUB 3 read-aloud (Media Overlays), such as Apple Books or Thorium Reader.", "فایلِ EPUB همین متن و روایت را با همین رنگی‌شدنِ خط‌ها در خود دارد، برای خواندن و شنیدنِ بی‌اینترنت در برنامه‌هایی که «خواندنِ همراه با صدا»ی EPUB 3 (Media Overlays) را پشتیبانی می‌کنند، مانند Apple Books یا Thorium Reader.")}</p>'
        '</main>')
    page(f"guide/listen/{ch.slug}.html", other_rel=f"guide/{ch.href}", root=root, title=L(f"Read along: {title}", f"خواندن همراه با صدا: {title}"),
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
    if LANG == "en":
        EN_CHAPTERS.clear()
        EN_CHAPTERS.update(chapters)
    total = sum(t["duration"] for t in tracks)
    half = 0.25 <= (total / 3600) % 1 < 0.75
    total_label = (f"{int(total // 3600)}½ hours" if half else f"{round(total / 3600)} hours") if LANG == "en" else \
        (f"{num(int(total // 3600))}٫۵ ساعت" if half else f"{num(round(total / 3600))} ساعت")

    print(f"[{LANG}] guide")
    later = []
    prepare_learning(md, C, chapters)
    for ch in chapters.values():
        build_chapter(ch, chapters, md, art, later, C)
    guide_index = build_guide_index(art, chapters, md, total_label)
    home_page = build_home(art, chapters, md, total_label, len(C.N))
    svgs = render_mermaid(md, prune=False)
    r1, r0, r2 = up(1), up(0), up(2)
    for path, body, root, ch, desc in later:
        body = place_diagrams(body, md, svgs)
        page(f"guide/{ch.href}", root=root, title=f"{ch.label}: {ch.title}" if ch.num <= 16 else ch.title, desc=desc, body=body,
             current="guide", hero_img=(art.src(ch.art, root), art.srcset(ch.art, root)), bar="clear", reader=True, focus=True)
    page("guide/index.html", root=r1, title=L("The guide", "راهنما"),
         desc=L("Contents of Mastering Epistemology: sixteen chapters on knowledge, evidence, and critical thinking.",
                "فهرستِ «تسلط بر معرفت‌شناسی»: شانزده فصل دربارهٔ معرفت، شواهد و تفکر نقادانه."),
         body=place_diagrams(guide_index, md, svgs), current="guide", hero_img=(art.src("guide", r1), art.srcset("guide", r1)), bar="clear")
    page("index.html", root=r0, title=site_name(),
         desc=L("A free, complete guide to epistemology and critical thinking: illustrated chapters, a bilingual concept map, and a narrated audio edition.",
                "راهنمایی رایگان و کامل دربارهٔ معرفت‌شناسی و تفکر نقادانه: فصل‌های مصوّر، نقشهٔ دوزبانهٔ مفاهیم و نسخهٔ صوتی."),
         body=home_page, hero_img=(art.src("home", r0), art.srcset("home", r0)), bar="clear")

    print(f"[{LANG}] concepts")
    pages = []
    (build_concepts if LANG == "en" else build_concepts_fa)(C, chapters, md, art, pages)
    for path, root, title, desc, body, current, key in pages:
        page(str(path.relative_to(OUT())), root=root, title=title, desc=desc, body=body, current=current,
             hero_img=(art.src(key, root), art.srcset(key, root)), bar="clear", reader=True, bilingual=(LANG == "en"))

    print(f"[{LANG}] audio, credits, study pages")
    page("guide/audio/index.html", root=r2, title=L("Listen", "شنیدن"), desc=L("The narrated audio edition of Mastering Epistemology.", "نسخهٔ صوتیِ «تسلط بر معرفت‌شناسی»."),
         body=build_audio_page(art, chapters, tracks, build_feed(chapters, tracks, md)), current="audio", hero_img=(art.src("audio", r2), art.srcset("audio", r2)), bar="clear")
    page("guide/audio/about.html", root=r2, title=L("How the audio was made", "صوت چگونه ساخته شد"),
         desc=L("How the narrated audio edition was produced.", "نسخهٔ صوتی چگونه ساخته شد."), body=build_audio_about(art, md), current="audio", bar="clear")
    page("notes/index.html", root=r1, title=L("Notebook", "دفترچه"), desc=L("Your highlights and notes.", "نشانه‌گذاری‌ها و یادداشت‌های شما."),
         body=build_notebook(art), current="account", bar="clear")
    page("credits.html", root=r0, title=L("Credits", "منابع"), desc=L("Credits for the artwork, audio and fonts on this site.", "منابعِ آثار هنری، صدا و قلم‌های این سایت."),
         body=build_credits(art), bar="clear")
    page("review/index.html", root=r1, title=L("Review questions", "مرور پرسش‌ها"),
         desc=L("Spaced review of the guide's self-check questions.", "مرورِ فاصله‌دارِ پرسش‌های خودآزماییِ راهنما."), body=build_review(art), current="account", bar="clear")
    page("account/index.html", root=r1, title=L("My study", "مطالعهٔ من"),
         desc=L("Sign in, sync your notes and progress, and set up the AI study companion.", "ورود، همگام‌سازیِ یادداشت‌ها و پیشرفت، و راه‌اندازیِ همراهِ هوشمندِ مطالعه."),
         body=build_account(art), current="account", bar="clear")
    write_learning_data(C)
    build_epub(chapters, art)
    if LANG == "fa":
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
