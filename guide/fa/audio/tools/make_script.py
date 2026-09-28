#!/usr/bin/env python3
"""Turn a Persian guide chapter into a Persian narration script.

This is the Persian counterpart of guide/audio/tools/make_script.py and writes
scripts in the same cue format, so the two editions can be read side by side.
A script is a plain-text file, one cue per line, that says what is read and
how: which voice, where the pauses and chimes go, where a question is followed
by thinking time. `narrate.py` turns scripts into audio.

    python3 make_script.py              # every chapter, into ../scripts/
    python3 make_script.py 05           # one chapter, printed to stdout
    python3 make_script.py --report     # every chapter, plus a list of what was dropped

Script cues (the same as the English edition's)
    @title T         metadata: the track title
    @opening T       chapter title, read slowly after the opening chime
    @section T       level-2 heading: chime, pause, heading, pause (and a chapter marker)
    @subsection T    level-3 heading: pause, heading, shorter pause
    @quote T         a quotation, in the quotation voice
    @attr T          who said it, read by the narrator
    @cue T           a signpost before a boxed lesson or tip (soft bell first)
    @label T         a short spoken label, such as «جواب.» in a quoted thread
    @aside T         set-off text such as an example argument, read a little slower
    @item T          a list item or table row (shorter pause after)
    @voice1..3 T     speakers in a dialogue, each in their own voice
    @question T      a review question
    @think N         N seconds of silence to think
    @answer T        the answer to a review question
    @pause N         N seconds of silence
    @chime           the section chime
    T                anything else is read by the narrator as a paragraph

Rules the Persian scripts follow
  - The chapter's own Persian terms are kept exactly as written. Nothing is
    paraphrased; only what cannot be read aloud (links, citations, formulas,
    digits) is turned into words.
  - An English or Latin term that the chapter gives in brackets after a
    Persian term is read once, at its first appearance in the chapter, with
    «به انگلیسی» or «به لاتین» before it. Later repeats are left out.
  - Latin-script names that only repeat a Persian name are left out.
"""

import re
import sys
from pathlib import Path

from num2words import num2words

from script_extras import INTROS, OUTROS, REPLACE, TABLES, WELCOME

FA = Path(__file__).resolve().parents[2]  # guide/fa
SCRIPTS = FA / "audio" / "scripts"

dropped = []  # (chapter, text) pairs, for --report

ZWNJ = "‌"
FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


# ---------------------------------------------------------------------------
# Numbers


def words(n):
    return num2words(int(n), lang="fa")


ORDINALS = {1: "اول", 2: "دوم", 3: "سوم"}


def ordinal(n):
    n = int(n)
    return ORDINALS.get(n) or num2words(n, lang="fa", to="ordinal")


def decimal(whole, frac):
    """0.35 -> سی و پنج صدم; 1.5 -> یک و پنج دهم; the fraction keeps its digits."""
    places = {1: "دهم", 2: "صدم", 3: "هزارم", 4: "ده‌هزارم", 5: "صدهزارم"}
    frac_n = int(frac) if frac else 0
    head = "" if int(whole or 0) == 0 else words(whole)
    if not frac_n:
        return head or "صفر"
    tail = f"{words(frac_n)} {places.get(len(frac), 'جزء')}"
    return f"{head} و {tail}" if head else tail


NUM = r"(\d+(?:[.٫]\d+)?)"


def cardinal(s):
    s = s.replace(",", "").replace("٬", "")
    if re.search(r"[.٫]", s):
        whole, frac = re.split(r"[.٫]", s, 1)
        return decimal(whole, frac)
    return words(s)


SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def say_numbers(t):
    t = t.translate(FA_DIGITS)
    t = re.sub(r"(\d+(?:[.٫]\d+)?)\s?(?:\^\s?(\d+)|([⁰¹²³⁴⁵⁶⁷⁸⁹]+))",
               lambda m: f"{m.group(1)} به توانِ {m.group(2) or m.group(3).translate(SUPERSCRIPT)}", t)
    t = re.sub(r"(?<=\d)[,٬](?=\d{3}\b)", "", t)  # thousands separators
    t = re.sub(r"(\d)\s?[–-]\s?(\d)", r"\1 تا \2", t)  # ranges
    t = re.sub(r"(\d{1,2}):(\d{2})\b", lambda m: words(m.group(1)) + (
        "" if m.group(2) == "00" else " و " + words(m.group(2)) + " دقیقه"), t)  # 9:15
    t = re.sub(NUM + r"\s?:\s?" + NUM, lambda m: cardinal(m.group(1)) + " به " + cardinal(m.group(2)), t)  # 15:85
    t = re.sub(NUM + r"\s?[٪%]", lambda m: cardinal(m.group(1)) + " درصد", t)
    t = re.sub(r"\b(1\d{3}|20\d{2})\s?/\s?(1\d{3}|20\d{2})\b", r"\1 و \2", t)  # two years, 1843 / 1859
    t = re.sub(r"(\d(?:[.٫]\d+)?)\s?/\s?(\d+[.٫]\d+)|(\d+[.٫]\d+)\s?/\s?(\d)|(\d)\s/\s(\d)",
               lambda m: re.sub(r"\s?/\s?", " تقسیم بر ", m.group(0)), t)
    t = re.sub(r"(?<![\d.])(\d+)/(\d+)(?![\d.])",
               lambda m: f"{words(m.group(1))} {'دوم' if m.group(2) == '2' else ordinal(m.group(2)).replace('اول', 'یکم')}"
               if int(m.group(2)) <= 10 else f"{words(m.group(1))} از {words(m.group(2))}", t)
    t = re.sub(r"\bفصل\s+(\d+)", lambda m: "فصلِ " + words(m.group(1)), t)
    t = re.sub(NUM, lambda m: cardinal(m.group(1)), t)
    return t


# ---------------------------------------------------------------------------
# Letters, symbols and formulas

# How Persian speakers name the Latin letters when they read a formula aloud
LETTERS = {"A": "اِی", "B": "بی", "C": "سی", "D": "دی", "E": "ای", "F": "اِف", "G": "جی",
           "H": "اِچ", "I": "آی", "J": "جِی", "K": "کِی", "L": "اِل", "M": "اِم", "N": "اِن",
           "O": "اُو", "P": "پی", "Q": "کیو", "R": "آر", "S": "اِس", "T": "تی", "U": "یو",
           "V": "وی", "W": "دابلیو", "X": "اِکس", "Y": "وای", "Z": "زِد"}


def letter_names(s):
    return "‌".join(LETTERS[c.upper()] for c in s)


def say_probability(t):
    t = re.sub(r"\bnot-(\w+)", r"نه \1", t)
    t = re.sub(r"\bnot\s", "نه ", t)

    def prob(m):
        which, body = m.group(1), m.group(2)
        body = re.sub(r"\s*\|\s*", " به شرطِ ", body)
        body = re.sub(r"\bor\b", "یا", body)
        body = re.sub(r"\band\b", "و", body)
        kind = {"_new": "تازهٔ ", "_old": "قبلیِ "}.get(which or "", "")
        return f"احتمالِ {kind}{body}"
    t = re.sub(r"(P(?:_\w+)?\([^()]*\))\s*/\s*(?=P(?:_\w+)?\()", r"\1 تقسیم بر ", t)
    for _ in range(2):
        t = re.sub(r"\bP(_new|_old)?\(([^()]{1,40})\)", prob, t)
    return t


LOGIC = [
    (r"∀(\w)\s?", r"برای هر \1، "), (r"∃(\w)\s?", r"\1‌ای هست که "),
    (r"□\s?", "ضرورتاً "), (r"◇\s?", "ممکن است "), (r"¬\s?", "نه "),
    (r"\s?∧\s?", " و "), (r"\s?∨\s?", " یا "), (r"\s?↔\s?", " اگر و فقط اگر "),
    (r"\s?≡\s?", " هم‌ارز است با "), (r"\s?⊢\s?", " نتیجه می‌دهد "),
    (r"\s?≈\s?", " تقریباً "), (r"\s?≠\s?", " مساوی نیست با "),
    (r"\s?≤\s?", " کوچک‌تر یا مساویِ "), (r"\s?≥\s?", " بزرگ‌تر یا مساویِ "),
    (r"\s?×\s?", " ضرب در "), (r"\s?÷\s?", " تقسیم بر "), (r"√", "رادیکالِ "),
    (r"∞", "بی‌نهایت"), (r"∴", "پس"), (r"\s>\s", " بزرگ‌تر از "), (r"\s<\s", " کوچک‌تر از "),
]

SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def say_symbols(t):
    t = say_probability(t)
    t = re.sub(r"»\s*=\s*", "» یعنی ", t)
    t = re.sub(r"\s?←\s?", " ", t)
    t = t.replace("H₂O", "اِچ‌تواُو").replace("CO₂", "سی‌اُتو")
    for pat, rep in LOGIC:
        t = re.sub(pat, rep, t)
    t = re.sub(r"((?:نه )?\b[A-Z]\b)\s?→\s?((?:نه )?\b[A-Z]\b)", r"اگر \1 آن‌گاه \2", t)
    t = re.sub(r"\s?→\s?", "، آن‌گاه ", t)
    t = re.sub(r"(\w)\s?=\s?(\w)", r"\1 مساوی \2", t)
    t = re.sub(r"\s=\s", " مساوی ", t)
    t = re.sub(r"\s\+\s", " به‌علاوهٔ ", t)
    t = re.sub(r"\s?−\s?", " منهای ", t)
    t = t.translate(SUB)
    t = t.replace("&", " و ").replace("§", "بخشِ ").replace("~", "حدودِ ")
    return t


def say_latin_letters(t):
    """Single letters and short capitals used as names in the text: P, Q, IBE, RCT."""
    t = re.sub(r"(?<![A-Za-z'’-])(?<![A-Za-z] )([A-Za-z])(?![A-Za-z'’-])(?! [A-Za-z])(\u200c?)(?=([\u0621-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06CC])?)",
               lambda m: LETTERS[m.group(1).upper()] + ("\u200c" if m.group(3) else ""), t)
    t = re.sub(r"(?<![A-Za-z'’-])([A-Z]{2,5})s?(?![A-Za-z'’-])",
               lambda m: m.group(0) if m.group(1) in SPOKEN_ACRONYMS else letter_names(m.group(1)), t)
    return t


# Capitals that are said as a word, not letter by letter (narrate.py's lexicon says how)
SPOKEN_ACRONYMS = {"FLICC", "SIFT", "CRAAP", "CUDOS", "OPERA", "PLOS", "ONE", "SIDS", "NASA", "IARPA",
                   "HARKing", "AAA", "ARS", "ABC"}


# ---------------------------------------------------------------------------
# Terms from other languages

# Latin (and one or two Greek) expressions: introduced as «به لاتین»
LATIN = {"a priori", "a posteriori", "modus ponens", "modus tollens", "reductio ad absurdum", "ad hominem",
         "tu quoque", "ad populum", "ad ignorantiam", "ad verecundiam", "ad misericordiam", "ad hoc",
         "post hoc ergo propter hoc", "cum hoc ergo propter hoc", "non sequitur", "petitio principii",
         "ceteris paribus", "de re", "de dicto", "prima facie", "sine qua non", "ex ante", "ex post",
         "sensus divinitatis", "genius malignus", "cogito", "si fallor", "sapere aude", "esse est percipi",
         "ex falso quodlibet", "dicto simpliciter", "adaequatio rei et intellectus", "elenchus",
         "argumentum ad verecundiam", "argumentum ad populum", "argumentum ad novitatem",
         "argumentum ad nauseam", "argumentum ad ignorantiam", "argumentum ad consequentiam",
         "argumentum ad antiquitatem", "reductio ad hitlerum",
         "nihil est in intellectu quod non sit prius in sensu"}
LANGUAGE_WORDS = ("انگلیسی", "لاتین", "یونانی", "آلمانی", "فرانسوی")


class Chapter:
    def __init__(self, number):
        self.chapter = f"{number:02d}"
        self.seen = set()  # foreign terms already introduced

    def foreign(self, term, before):
        """How a bracketed foreign term is read: the first time with its language, then not at all."""
        key = term.lower().strip("*_ ")
        if key in self.seen:
            return None
        self.seen.add(key)
        term = term.strip("*_ ")
        if any(w in before[-40:] for w in LANGUAGE_WORDS):
            return term  # the sentence already says which language it is
        return ("به لاتین " if key in LATIN else "به انگلیسی ") + term


def latin_run(s):
    """The leading Latin-script run of a bracket, if the bracket starts with one."""
    whole = re.sub(r"[*_]", "", s).strip()
    if re.fullmatch(r"[A-Za-zÀ-ÿĀ-žēīōū'’ .,;:!?-]+", whole):
        return whole
    m = re.match(r"^\*{0,2}([A-Za-z][A-Za-z'’ .-]*[A-Za-z.])\*{0,2}(?=$|[،,;؛]\s*)", s.strip())
    return m.group(1) if m else None


def is_name(s):
    words_ = s.split()
    return len(words_) >= 2 and all(w[:1].isupper() for w in words_ if w not in ("de", "von", "van", "of"))


# ---------------------------------------------------------------------------
# Inline markdown

LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
PERSIAN_YEAR = r"(?:[۱1][۰-۹0-9]{3}|[۲2][۰0][۰-۹0-9]{2})"
CROSSREF = r"(?:همچنین\s+)?نگاه\s+کنید\s+به"


def strip_crossrefs(t):
    """Drop sentences and brackets whose only job is to send the reader elsewhere."""
    t = re.sub(r"\s*\(" + CROSSREF + r"[^()]*(?:\([^()]*\)[^()]*)*\)", "", t)
    t = re.sub(r"\s*\(\[[^\]]*\]\([^)]*\)\)", "", t)  # ([فصل ۱۵](...))
    parts = re.split(r"(?<=[.!؟?])\s+", t)
    keep = []
    for p in parts:
        bare = p.strip("*_ ")
        if re.match(r"^\(?" + CROSSREF, bare) or re.match(r"^\(?بیشتر\s+در\s+\[", bare):
            unlinked = LINK.sub("", p)
            closing = unlinked.count(")") - unlinked.count("(")
            if closing > 0 and keep:
                keep[-1] += ")" * closing
            continue
        # «... را در [فصل ۶] ببینید.» style pointers
        if re.fullmatch(r"[^.]{0,40}\[[^\]]*\]\([^)]*\)[^.]{0,20}(?:ببینید|می‌آید)\.?", bare) and len(bare) < 90:
            continue
        keep.append(p)
    t = " ".join(keep)
    t = re.sub(r"[،,]?\s*" + CROSSREF + r"\s+(?:\[[^\]]*\]\([^)]*\)(?:\s*[،,]\s*|\s+و\s+)?)+(?=[.؛;)])", "", t)
    return t


def parenthetical(inner, before, ch):
    """What a bracket becomes when read aloud: nothing, an aside, or a sentence."""
    c = inner.strip()
    plain = re.sub(r"[*_]", "", c)
    if not plain:
        return ""
    # A foreign term, maybe followed by a Persian gloss: (credence، یا احتمالِ ذهنی)
    lat = latin_run(c)
    if lat and not re.fullmatch(r"[A-Z]\d*|[A-Z]{1,3}|[a-z]", lat) and not re.search(r"\d", lat):
        rest = c[len(c) - len(c.lstrip()):]
        rest = re.sub(r"^\*{0,2}" + re.escape(lat) + r"\*{0,2}", "", re.sub(r"[*_]", "", c).strip()).lstrip("،,؛; ")
        if is_name(lat) and not rest:
            dropped.append((ch.chapter, c))
            return ""
        spoken = ch.foreign(lat, before)
        parts = [p for p in (spoken, rest) if p]
        return "، ".join(parts)
    # "(عنوان، ۱۹۵۶: آنچه نویسنده گفت)" keeps what was said
    m = re.match(r"^[^:]{0,90}" + PERSIAN_YEAR + r"[^:]{0,8}:\s*(.+)$", plain)
    if m:
        dropped.append((ch.chapter, c.split(":")[0]))
        return m.group(1)
    if re.match(CROSSREF, plain):
        dropped.append((ch.chapter, c))
        return None
    # A full sentence
    if re.search(r"[.!؟?][»\"]?$", plain) and len(plain.split()) >= 5:
        return plain
    # Citations: a year with a title, or a year with little else
    if re.search(PERSIAN_YEAR, plain):
        rest = re.sub(PERSIAN_YEAR + r"|[۰-۹0-9]+|حدودِ|پیش از میلاد|پ\.\s?م\.|میلادی|قرنِ|ویراستِ\s+\S+|"
                      r"کتابِ|فصلِ|بخشِ|بندِ|نوشته‌شده|منتشرشده|در|و|[،,؛;:.–()\-]", " ", plain)
        if "*" in c or "«" in c or len(rest.split()) <= 4:
            dropped.append((ch.chapter, c))
            return None
    if re.search(r"(?:فصلِ|بخشِ|بندِ)\s*[۰-۹0-9]", plain) and ("*" in c or "«" in c):
            dropped.append((ch.chapter, c))
            return None
    # Section and page references: (B16), (I.46), (97e–98a), (۱۷۳۹–۱۷۴۰، کتابِ ۳، بخشِ ۱)
    if re.fullmatch(r"[A-Z]\d+|[IVX]+\.[\dixv]+[a-z]?|\d+[a-e]\d*(?:\s?[–-]\s?\d*[a-e]\d*)?", plain) or \
            re.fullmatch(r"[\d۰-۹\s–\-،,]+(?:(?:کتابِ|فصلِ|بخشِ|بندِ)\s*[\d۰-۹]+[،,\s]*)*", plain):
        dropped.append((ch.chapter, c))
        return None
    return plain


LABELS = {"الف": "الف", "ب": "ب", "پ": "پ", "ت": "ت", "ج": "ج", "د": "د", "ه": "ه",
          "و": "واو", "ز": "ز", "ح": "ح", "ط": "ط", "ی": "ی"}


def ordinal_marks(t):
    """(الف) ... (ب) ... inside a paragraph become «الف: ... ب: ...»; (۱) ... (۲) ... become «یک: ...»."""
    # a mark that opens an item («... . (ب) علی می‌داند ...») becomes «ب:»; one that refers back stays a name
    t = re.sub(r"(^|[.!؟?:؛;«]\s*)\((الف|ب|پ|ت|ج|د|ه|و|ز|ح|ط|ی)\)(?=\s)",
               lambda m: f"{m.group(1)}{LABELS[m.group(2)]}:", t)
    t = re.sub(r"(?<=\s)\((الف|ب|پ|ت|ج|د|ه|و|ز|ح|ط|ی)\)(?=[\s،,.؛])", lambda m: LABELS[m.group(1)], t)
    t = re.sub(r"(^|[\s:؛;])\(([۱-۹1-9])\)\s", lambda m: f"{m.group(1)}{words(m.group(2).translate(FA_DIGITS))}: ", t)
    return t


def flatten_parens(t, ch):
    """Replace (...) groups, innermost first, following `parenthetical`."""
    t = ordinal_marks(t)
    while True:
        m = re.search(r"\(([^()]*)\)", t)
        if not m:
            break
        before, after = t[: m.start()], t[m.end():]
        if re.search(r"\b(?:P|[a-z]|احتمالِ)$", before):  # a formula such as P(x) left over
            t = before + "⦅" + m.group(1) + "⦆" + after
            continue
        inner = parenthetical(m.group(1), before, ch)
        if inner is None or inner == "":
            t = before.rstrip() + after
            continue
        if re.search(r"[.!؟?][»\"]?$", inner) and (re.search(r"[.!؟?:][»\"]?$", before.rstrip()) or not before.strip()):
            t = before.rstrip() + " " + inner + " " + after.lstrip()  # a sentence on its own
        else:
            rest = after.lstrip()
            inner = inner.rstrip(".")
            if rest[:1] in (".", "!", "؟", "?", "؛", ";", ":", ""):
                t = before.rstrip() + "، " + inner + rest
            else:
                t = before.rstrip() + "، " + inner + ("" if rest[:1] in "،,)" else "، ") + rest
    return t.replace("⦅", "(").replace("⦆", ")")


def tidy(t):
    t = re.sub(r"\s+", " ", t).strip()
    rules = [
        (r"\s+([،,.؛;:!؟?])", r"\1"), (r"[،,]\s*([.؛;:!؟?])", r"\1"), (r"([.؛;:!؟?])[،,]", r"\1"),
        (r"[،,]\s*[،,]", "،"), (r"—\s*[،,]", "—"), (r"—\s*([.؛;:!؟?])", r"\1"), (r"([،,؛;:])\s*—", r"\1"),
        (r"—\s*—", "—"), (r"…\.", "…"), (r"\s*—\s*", " — "), (r"([.!؟?])\s*\.", r"\1"), (r"^[،,؛;:—\s]+", ""),
        (r"[،,؛;—\s]+$", ""), (r":$", "."), (r"([،؛:])(?=[^\s\d»)])", r"\1 "), (r",", "،"), (r";", "؛"),
        (r"«\s+", "«"), (r"\s+»", "»"), (r"«»", ""),
    ]
    while True:
        before = t
        for pat, rep in rules:
            t = re.sub(pat, rep, t)
        if t == before:
            return t.strip()


def speak(t, ch, cell=False):
    """Markdown inline text to plain spoken Persian."""
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = strip_crossrefs(t)
    t = LINK.sub(r"\1", t)
    t = re.sub(r"پ\.\s?م\.", "پیش از میلاد", t)
    t = re.sub(r"(?<![\u0600-\u06FF.])م\.(?=[\s:،؛)|]|$)", "میلادی", t)  # «حدودِ ۲۰۰ م.»
    t = t.replace("`", "")
    t = say_probability(t)
    t = re.sub(r"\*\*\((الف|ب|پ|ج|د|ه|و|ز|ح|ط|ی)\)\*\*\s*", lambda m: LABELS[m.group(1)] + ": ", t)
    t = re.sub(r"\*\*\(([A-Z])\)\*\*\s*", lambda m: LETTERS[m.group(1)] + ": ", t)
    t = re.sub(r"^\*\(([^()]{1,25})\)\*\s+", r"\1: ", t)  # «۴. *(ناگفته)* ...» in a premise list
    t = re.sub(r"\*\(([^()]*)\)\*", r"(\1)", t)
    t = flatten_parens(t, ch)  # before italics go: a title in *italics* marks a citation
    t = re.sub(r"\*\*|__", "", t)
    t = re.sub(r"(?<![\w*])\*(?![\s*])([^*\n]+?)(?<![\s*])\*(?!\*)", r"\1", t)
    t = t.replace("’", "'").replace("‘", "'").replace("“", "«").replace("”", "»")
    t = re.sub(r"\"([^\"]+)\"", r"«\1»", t)
    t = re.sub(r"[،,]?\s*\b[IVX]+\.[\dixv]+[a-z]?(?:[.–-][\dixv]+[a-z]?)*\b", "", t)  # II.19, I.46
    t = re.sub(r"[،,]?\s*\b\d+[a-e]\d*(?:\s?[–-]\s?\d*[a-e]\d*)?(?![\w])", "", t)  # 97e–98a, 1011b25
    t = re.sub(r"\be\.g\.,?", "مثلاً", t)
    t = re.sub(r"\bvs\.?\s", "در برابرِ ", t)
    t = say_symbols(t)
    t = re.sub(r"([A-Za-z])(?=[0-9۰-۹])", r"\1 ", t)  # DH0 -> DH 0
    t = say_numbers(t)
    t = say_latin_letters(t)
    t = re.sub(r"(\w)\s*–\s*(\w)", r"\1 \2", t)
    t = t.replace("–", " — ").replace("ـ", " ")  # «دوئم‌ـ‌کواین» is read as two names
    t = re.sub(r"(?<=\S)\s?/\s?(?=\S)", " یا ", t)
    t = t.replace("...", "…").replace("[", "").replace("]", "")
    t = re.sub(ZWNJ + r"+\s", " ", t)
    return tidy(t)


# ---------------------------------------------------------------------------
# Blocks


def parse_table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    return cells[0], cells[1:]


def fill(template, header, row):
    def sub(m):
        idx = m.group(1)
        return header[int(idx[1:])] if idx.startswith("h") else row[int(idx)]
    return re.sub(r"\{(h?\d+)\}", sub, template)


def end(s):
    s = s.rstrip()
    return s if re.search(r"[.!؟?:»]$", s) else s + "."


def table_lines(header, rows, ch):
    key = re.sub(r"[`*]", "", header[0]) if header[0] else "|" + header[1]
    spec = TABLES.get(ch.chapter, {}).get(key)
    if spec is not None and not isinstance(spec, str):  # a list of prepared lines
        return [f"@item {speak(line, ch, cell=True)}" if not line.startswith("@") else line for line in spec]
    out = []
    for row in rows:
        row = [speak(c, ch, cell=True) for c in row]
        head = [speak(h, ch, cell=True) for h in header]
        if spec:
            line = fill(spec, head, row)
        elif not head[0]:
            line = end(row[0]) + " " + " ".join(
                (f"{h} {c}" if h.endswith("؟") else f"{h}: {c}") + ("" if c.endswith((".", "؟", "!")) else ".")
                for h, c in zip(head[1:], row[1:]))
        elif len(head) == 2:
            line = f"{row[0]}: {row[1]}"
        else:
            parts = [end(row[0])]
            for h, c in zip(head[1:], row[1:]):
                if h.endswith("؟"):
                    parts.append(f"{h} {end(c)}")
                elif h.endswith(("…", "...")):
                    parts.append(f"{h.rstrip('.…')} {end(c)}")
                else:
                    parts.append(f"{h}: {end(c)}")
            line = " ".join(parts)
        out.append("@item " + tidy(end(line)))
    return out


SPEAKERS = {"الف": 1, "ب": 2, "گویندهٔ الف": 1, "گویندهٔ ب": 2}
THREAD = {"پست": 1, "جواب": 2, "جواب به جواب": 1}


def speaker_line(l):
    m = (re.match(r"^\*\*([^*.]{1,20}?):\*\*\s+(.*)$", l) or re.match(r"^\*\*([^*.]{1,20}?)\*\*:\s+(.*)$", l))
    return (m.group(1), m.group(2)) if m else None


def unquote(s):
    s = s.strip()
    if s.startswith("«") and s.endswith("»") and s.count("«") == 1:
        return s[1:-1]
    return s


def speaker_cues(l, ch):
    """One labelled line: a voice for speakers, label and voice for a thread, else an aside."""
    label, said = speaker_line(l)
    if label in SPEAKERS:
        return [f"@voice{SPEAKERS[label]} {unquote(speak(said, ch))}"]
    if label in THREAD:
        return [f"@label {label}.", f"@voice{THREAD[label]} {unquote(speak(said, ch))}"]
    return [f"@aside {end(speak(label, ch))} {speak(said, ch)}"]


def clean_attr(attr):
    attr = re.sub(r"\s*\(([^()]*)\)", lambda m: "" if re.search(r"[۰-۹0-9]", m.group(1)) else m.group(0), attr)
    attr = re.sub(r"[،,]\s*(?:کتابِ|فصلِ|بخشِ|بندِ|در\s)[^،,]*", "", attr)
    attr = re.sub(r"[،,]\s*(?:حدودِ\s*)?[۰-۹0-9]{3,4}\s*$", "", attr)
    attr = re.sub(r"[،,]\s*[IVXLC]+\.\d+.*$|[،,]\s*\d+[a-z]?\d*$|[،,]\s*[۰-۹]+$", "", attr)
    return attr.strip("، ")


def blockquote_lines(block, ch, epigraph=False):
    """A run of '>' lines to script cues."""
    lines = [re.sub(r"^>\s?", "", l) for l in block]
    text_lines = [l for l in lines if l.strip()]
    out = []
    # Epigraph or attributed quotation: quote lines followed by «— نویسنده، اثر»
    if text_lines and text_lines[-1].startswith("—") and len(text_lines) >= 2 and not text_lines[-1].startswith("——"):
        quote = " ".join(text_lines[:-1])
        attr = clean_attr(text_lines[-1].lstrip("— ").strip())
        out.append("@quote " + unquote(speak(quote, ch)))
        out.append("@attr " + end(speak(attr, ch)))
        return out
    # Dialogue: every line has a speaker label
    labelled = [speaker_line(l) for l in text_lines]
    if len(text_lines) >= 2 and all(labelled):
        for l in text_lines:
            out.extend(speaker_cues(l, ch))
        return out
    # Callout: bold label then text
    m = re.match(r"^\*\*([^*]{2,70}?)\*\*[.:]?\s+(.*)$", text_lines[0]) if text_lines else None
    if m and not m.group(1).startswith("«") and len(text_lines) == 1 and len(m.group(2)) > 50:
        out.append("@cue " + end(speak(m.group(1).rstrip(".: "), ch)))
        out.append(speak(m.group(2), ch))
        return out
    if m and not m.group(1).startswith("«") and len(text_lines) > 1 and text_lines[1].startswith("- "):
        out.append("@cue " + end(speak(m.group(1).rstrip(".: "), ch)) + " " + speak(m.group(2), ch))
        for l in text_lines[1:]:
            out.append("@item " + end(speak(l[2:], ch)))
        return out
    # Argument layout: numbered premises, a rule, a conclusion
    if any(re.fullmatch(r"—{2,}|-{3,}", l.strip()) for l in text_lines):
        for l in text_lines:
            if re.fullmatch(r"—{2,}|-{3,}", l.strip()):
                out.append("@pause 0.4")
                continue
            mm = re.match(r"^([0-9۰-۹]+)\.\s+(.*)$", l)
            if mm:
                out.append(f"@aside مقدمهٔ {words(mm.group(1).translate(FA_DIGITS))}: {speak(mm.group(2), ch)}")
                continue
            mm = re.match(r"^(?:C|ن)\.\s+(.*)$", l)
            if mm:
                out.append(f"@aside نتیجه: {speak(mm.group(1), ch)}")
                continue
            out.append("@aside " + speak(l, ch))
        return out
    # A quotation standing alone
    whole = " ".join(text_lines)
    if re.match(r'^\*{0,2}«', whole) and re.search(r'»\*{0,2}\.?$', whole) and whole.count("«") <= 1:
        out.append("@quote " + unquote(speak(whole, ch)))
        return out
    # Anything else: set-off text, each line its own cue
    for l in text_lines:
        mm = re.match(r"^([0-9۰-۹]+)\.\s+(.*)$", l)
        if mm:
            out.append(f"@aside {words(mm.group(1).translate(FA_DIGITS))}: {speak(mm.group(2), ch)}")
        elif l.startswith("- "):
            out.append("@aside " + end(speak(l[2:], ch)))
        elif speaker_line(l) and (speaker_line(l)[0] in SPEAKERS or speaker_line(l)[0] in THREAD):
            out.extend(speaker_cues(l, ch))
        else:
            m = re.match(r"^\*\*([^*]{2,70}?)\*\*[.:]?\s+(.*)$", l)
            if m and len(m.group(2)) > 50 and not m.group(1).startswith("«"):
                out.append("@cue " + end(speak(m.group(1).rstrip(".: "), ch)))
                out.append(speak(m.group(2), ch))
            else:
                out.append("@aside " + end(speak(l, ch)))
    return out


def list_item(text, n, ch):
    body = speak(text, ch)
    if n is None:
        return "@item " + end(body)
    return f"@item {words(n)}. {end(body)}"


# ---------------------------------------------------------------------------
# Chapter


ANSWER_LEADS = ["پاسخ.", "و اما پاسخ.", "پاسخِ من این است.", "ببینیم پاسخ چیست.", "پاسخ این است."]
REVIEW_INTRO = ("حالا نوبتِ شماست. چند پرسش می‌آید تا فهمِ خودتان را بسنجید. بعد از هر پرسش چند ثانیه "
                "سکوت هست تا فکر کنید. اگر وقتِ بیشتری لازم دارید، پخش را نگه دارید و پیش از شنیدنِ پاسخ، "
                "پاسخِ خودتان را بلند بگویید یا بنویسید.")
PRACTICE_INTRO = ("حالا تمرین کنیم. بعد از هر نمونه چند ثانیه سکوت هست تا خودتان مغالطه را پیدا کنید. "
                  "اگر وقتِ بیشتری لازم دارید، پخش را نگه دارید.")


def extra(text, ch):
    """Hand-written lines: cues stay as they are, words get the same normalization."""
    out = []
    for line in text.strip().split("\n"):
        m = re.match(r"^(@\w+)(?:\s+(.*))?$", line)
        if m and m.group(2) and not re.fullmatch(r"[\d.]+", m.group(2)):
            out.append(f"{m.group(1)} {speak(m.group(2), ch)}")
        else:
            out.append(line if m else speak(line, ch))
    return out


def chapter_script(path):
    src = path.read_text(encoding="utf-8")
    number = int(path.name[:2])
    ch = Chapter(number)
    for old, new in REPLACE.get(ch.chapter, []):
        if old not in src:
            raise SystemExit(f"{path.name}: replacement source not found: {old[:60]!r}")
        src = src.replace(old, new)
    lines = src.split("\n")

    title_line = lines[0].lstrip("# ").strip()
    m = re.match(r"فصل\s+[۰-۹0-9]+\.\s+(.*)", title_line)
    title = m.group(1)
    out = [f"@title فصلِ {words(number)}: {title}"]
    if number == 1:
        out.extend(extra(WELCOME, ch))
    out += ["@chime", f"@opening فصلِ {words(number)}. {end(speak(title, ch))}", "@pause 1.2"]

    section = None
    i = 0
    intro_done = False
    in_review = False
    question_no = 0
    in_code = False
    para = []

    def flush():
        if para:
            text = re.sub(r"^\*\*([0-9۰-۹]+)\.\s", lambda m: f"**{words(m.group(1).translate(FA_DIGITS))}. ",
                          " ".join(para))
            out.append(speak(text, ch))
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if i == 0 or (s.startswith("[") and "](README.md)" in s) or "](audio/" in s:
            i += 1
            continue
        if s.startswith("```"):
            flush()
            in_code = not in_code
            i += 1
            continue
        if in_code:
            i += 1
            continue
        if s.startswith("## "):
            flush()
            section = s[3:].strip()
            if not intro_done:
                out.append("@pause 0.6")
                out.extend(extra(INTROS[ch.chapter], ch))
                intro_done = True
            if section == "برای مطالعهٔ بیشتر":
                break
            if section == "فهمِ خود را بسنجید":
                in_review = True
                out.append("@section " + section)
                out.append(REVIEW_INTRO)
            else:
                in_review = section.startswith("تمرین")
                out.append("@section " + speak(section, ch))
                if in_review:
                    out.append(PRACTICE_INTRO)
            i += 1
            continue
        if s.startswith("### ") or s.startswith("#### "):
            flush()
            out.append("@subsection " + speak(s.lstrip("# ").strip(), ch))
            i += 1
            continue
        if not s or s == "---":
            flush()
            i += 1
            continue
        if re.fullmatch(r"-{4,}|—{2,}", s):  # the rule above a conclusion in standard form
            flush()
            out.append("@pause 0.4")
            i += 1
            continue
        mc = re.match(r"^ن\.\s+(.*)$", s)
        if mc:
            flush()
            out.append("@item نتیجه: " + end(speak(mc.group(1), ch)))
            i += 1
            continue
        if in_review:
            flush()
            mq = re.match(r"^\*\*([0-9۰-۹]+)\.\*\*\s*(.*)$", s)
            if mq:
                question_no += 1
                out.append("@pause 0.8")
                out.append(f"@question پرسشِ {ordinal(question_no)}. {speak(mq.group(2), ch)}")
                i += 1
                continue
            if s.startswith("<details>"):
                j = i + 1
                body = []
                while not lines[j].strip().startswith("</details>"):
                    if not lines[j].strip().startswith("<summary>"):
                        body.append(lines[j])
                    j += 1
                chunks = "\n".join(body).strip().split("\n\n")
                out.append("@think 5")
                first = True
                for chunk in chunks:
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    if chunk.startswith("|"):
                        header, rows = parse_table(chunk.split("\n"))
                        out.extend(table_lines(header, rows, ch))
                        continue
                    if re.match(r"^([0-9۰-۹]+\.|-)\s", chunk):
                        for item in re.split(r"\n(?=[0-9۰-۹]+\.\s|-\s)", chunk):
                            mm = re.match(r"^([0-9۰-۹]+)\.\s+(.*)$", item, re.S)
                            if mm:
                                out.append(list_item(mm.group(2).replace("\n", " "),
                                                     int(mm.group(1).translate(FA_DIGITS)), ch))
                            else:
                                out.append(list_item(item[2:].replace("\n", " "), None, ch))
                        continue
                    if chunk.startswith(">"):
                        out.extend(blockquote_lines(chunk.split("\n"), ch))
                        continue
                    text = speak(chunk.replace("\n", " "), ch)
                    out.append(f"@answer {ANSWER_LEADS[question_no % len(ANSWER_LEADS)]} {text}" if first else text)
                    first = False
                i = j + 1
                continue
        if not in_review and (s.startswith("<details>") or s.startswith("</details>")):
            flush()  # a hidden answer in the text: give the listener time first
            m = re.search(r"<summary>(.*?)</summary>", s)
            if s.startswith("<details>"):
                out.append("@think 5")
            if m:
                out.append(f"@label {end(speak(m.group(1), ch))}")
            i += 1
            continue
        if not in_review and re.fullmatch(r"<summary>(.*?)</summary>", s):
            flush()
            out.append(f"@label {end(speak(re.sub(r'</?summary>', '', s), ch))}")
            i += 1
            continue
        if s.startswith("|"):
            flush()
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            header, rows = parse_table(lines[i:j])
            out.extend(table_lines(header, rows, ch))
            i = j
            continue
        if s.startswith(">"):
            flush()
            j = i
            while j < len(lines) and lines[j].startswith(">"):
                j += 1
            block = lines[i:j]
            is_epigraph = section is None and any(l.startswith("> —") for l in block)
            cues = blockquote_lines(block, ch, is_epigraph)
            if is_epigraph:
                out.extend(cues)
                out.append("@pause 0.8")
            else:
                out.append("@pause 0.3")
                out.extend(cues)
                out.append("@pause 0.3")
            i = j
            continue
        ml = re.match(r"^(\s*)([0-9۰-۹]+)\.\s+(.*)$", line)
        mb = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if ml or mb:
            flush()
            item = (ml.group(3) if ml else mb.group(2))
            j = i + 1
            while j < len(lines) and lines[j].startswith("   ") and not re.match(r"^\s*([0-9۰-۹]+\.|[-*])\s", lines[j]):
                item += " " + lines[j].strip()
                j += 1
            out.append(list_item(item, int(ml.group(2).translate(FA_DIGITS)) if ml else None, ch))
            i = j
            continue
        para.append(s)
        i += 1
    flush()

    out.append(f"@section پایانِ فصلِ {words(number)}")
    out.extend(extra(OUTROS[ch.chapter], ch))
    return "\n".join(l for l in out if l.strip() and l.strip() != "@item .") + "\n"


def chapters():
    return sorted(p for p in FA.glob("[01][0-9]-*.md") if int(p.name[:2]) <= 16)


def main(argv):
    report = "--report" in argv
    wanted = [a for a in argv if not a.startswith("--")]
    for path in chapters():
        if wanted and path.name[:2] not in wanted:
            continue
        script = chapter_script(path)
        if wanted and not report:
            sys.stdout.write(script)
        else:
            SCRIPTS.mkdir(parents=True, exist_ok=True)
            (SCRIPTS / (path.stem + ".txt")).write_text(script, encoding="utf-8")
    if report:
        for ch, text in dropped:
            print(f"{ch} dropped ({text})")


if __name__ == "__main__":
    main(sys.argv[1:])
