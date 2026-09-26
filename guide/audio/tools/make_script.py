#!/usr/bin/env python3
"""Turn a guide chapter into a narration script.

A narration script is a plain-text file, one cue per line, that says what the
narrator reads and how: which voice, where the pauses and chimes go, where a
question is followed by thinking time. Scripts are meant to be read and edited
by people; `narrate.py` turns them into audio.

    python3 make_script.py              # every chapter, into ../scripts/
    python3 make_script.py 05           # one chapter, printed to stdout
    python3 make_script.py --report     # every chapter, plus a list of what was dropped

Script cues
    @title T         metadata: the track title
    @opening T       chapter title, read slowly after the opening chime
    @section T       level-2 heading: chime, pause, heading, pause (and a chapter marker)
    @subsection T    level-3 heading: pause, heading, shorter pause
    @quote T         a quotation, in the quotation voice
    @attr T          who said it, read by the narrator
    @cue T           a signpost before a boxed lesson or tip (soft bell first)
    @label T         a short spoken label, such as "Reply." in a quoted thread
    @aside T         set-off text such as an example argument, read a little slower
    @item T          a list item or table row (shorter pause after)
    @voice1..3 T     speakers in a dialogue, each in their own voice
    @question T      a review question
    @think N         N seconds of silence to think
    @answer T        the answer to a review question
    @pause N         N seconds of silence
    @chime           the section chime
    T                anything else is read by the narrator as a paragraph
"""

import re
import sys
from pathlib import Path

from num2words import num2words

from script_extras import INTROS, OUTROS, REPLACE, TABLES, WELCOME

GUIDE = Path(__file__).resolve().parents[2]
SCRIPTS = GUIDE / "audio" / "scripts"

dropped = []  # (chapter, text) pairs, for --report


# ---------------------------------------------------------------------------
# Numbers


def words(n, **kw):
    """num2words without the British "and" and without commas, which would pause."""
    return num2words(n, **kw).replace(" and ", " ").replace(",", "")


def year(n):
    return words(int(n), to="year")


def cardinal(s):
    s = s.replace(",", "")
    if "." in s:
        whole, frac = s.split(".", 1)
        head = "" if whole in ("", "0") else words(int(whole)) + " "
        return head + "point " + " ".join(words(int(d)) for d in frac)
    return words(int(s))


def fraction(a, b):
    a, b = int(a), int(b)
    if b == 2:
        return "one half" if a == 1 else f"{words(a)} halves"
    if b == 4 and a in (1, 3):
        return "one quarter" if a == 1 else "three quarters"
    if b <= 10 and a < b:
        ordn = words(b, to="ordinal")
        return f"{words(a)} {ordn}" + ("s" if a > 1 else "")
    return f"{words(a)} out of {words(b)}"


NUM = r"((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)"
DIGITS = r"(?:\d{1,3}(?:,\d{3})+|\d+)"


def money(amount, unit, cents_word):
    whole, _, frac = amount.replace(",", "").partition(".")
    whole = int(whole or 0)
    cents = int((frac + "00")[:2]) if frac else 0
    if whole == 0 and cents:
        return f"{words(cents)} {cents_word}"
    out = f"{words(whole)} {unit}" + ("" if whole == 1 else "s")
    return out + (f" and {words(cents)} {cents_word}" if cents else "")

UNITS = {"kg": "kilograms", "km": "kilometers", "cm": "centimeters", "mm": "millimeters",
         "mph": "miles per hour", "ms": "milliseconds", "°C": "degrees Celsius",
         "°F": "degrees Fahrenheit"}


def say_numbers(t):
    t = re.sub(r"(\d)\s?[–-]\s?(\d)", r"\1 to \2", t)  # ranges
    t = re.sub(r"±\s?", "plus or minus ", t)
    t = re.sub(r"[$]" + NUM + r"\s(million|billion|trillion)",
               lambda m: f"{cardinal(m.group(1))} {m.group(2)} dollars", t)
    t = re.sub(r"£" + NUM + r"\s(million|billion|trillion)",
               lambda m: f"{cardinal(m.group(1))} {m.group(2)} pounds", t)
    t = re.sub(r"[$]" + NUM, lambda m: money(m.group(1), "dollar", "cents"), t)
    t = re.sub(r"£" + NUM, lambda m: money(m.group(1), "pound", "pence"), t)
    t = re.sub(r"#(?=\d)", "number ", t)
    t = t.replace("50/50", "fifty-fifty").replace("9/11", "nine eleven")
    t = re.sub(r"\b([A-Z]{1,3})(\d)\b", lambda m: " ".join(m.group(1)) + " " + m.group(2), t)
    t = re.sub(r"\b(\d+)([A-Z])\b", r"\1 \2", t)
    t = re.sub(r"(?<![\w.])" + NUM + r"\s?/\s?" + NUM + r"(?![\w.])",
               lambda m: (f"{cardinal(m.group(1))} divided by {cardinal(m.group(2))}"
                          if "." in m.group(1) + m.group(2) else m.group(0)), t)
    t = re.sub(NUM + r"\s?%", lambda m: cardinal(m.group(1)) + " percent", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s?(°C|°F|kg|km|cm|mm|mph|ms)\b",
               lambda m: cardinal(m.group(1)) + " " + UNITS[m.group(2)], t)
    t = re.sub(r"(\d+)\s?°", lambda m: cardinal(m.group(1)) + " degrees", t)
    t = re.sub(r"(?<=\bat )(\d{1,2}):(\d{2})\b",
               lambda m: words(int(m.group(1))) + " " + ("o'clock" if m.group(2) == "00" else
               ("oh " + words(int(m.group(2))) if m.group(2)[0] == "0" else words(int(m.group(2))))), t)
    t = re.sub(r"\b(1\d|20)(\d0)s\s?[–-]\s?(\d0)s\b", lambda m: m.group(1) + m.group(2) + "s to "
               + m.group(3) + "s", t)
    t = re.sub(r"\b(1\d|20)(\d0)s\b", lambda m: (year(m.group(1) + m.group(2)) + "s").replace("ys", "ies"), t)
    t = re.sub(r"\b([1-9]0)s\b", lambda m: (words(int(m.group(1))) + "s").replace("ys", "ies"), t)
    t = re.sub(r"\b(\d+)(?:st|nd|rd|th)\s?[–-]\s?(\d+)(st|nd|rd|th)\b",
               lambda m: m.group(1) + m.group(3) + " to " + m.group(2) + m.group(3), t)
    t = re.sub(r"(?<![\w.:])" + NUM + r"\s?:\s?" + NUM + r"(?![\w.:])",
               lambda m: f"{cardinal(m.group(1))} to {cardinal(m.group(2))}", t)  # odds, ratios
    t = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: words(int(m.group(1)), to="ordinal"), t)
    t = re.sub(r"(?<![\d.])(\d+)/(\d+)(?![\d.])", lambda m: fraction(m.group(1), m.group(2)), t)
    t = re.sub(r"\b(\d{3,4})\s(BCE|CE|BC|AD)\b", lambda m: year(m.group(1)) + " " + m.group(2), t)
    t = re.sub(r"(?<![\d,.])\b(1[0-9]\d\d|20\d\d)\b(?![,.]\d)", lambda m: year(m.group(1)), t)
    t = re.sub(r"(?<![\w.])" + NUM + r"(?![\w])", lambda m: cardinal(m.group(1)), t)
    t = t.replace("ninety-nine to one hundred percent", "ninety-nine to a hundred percent")
    return t


# ---------------------------------------------------------------------------
# Symbols, formulas and abbreviations


def say_probability(t):
    t = re.sub(r"(P(?:_\w+)?\([^()]*\))\s*/\s*(?=P(?:_\w+)?\()", r"\1 divided by ", t)

    def prob(m):
        which, body = m.group(1), m.group(2)
        body = re.sub(r"\s*\|\s*", " given ", body)
        kind = {"_new": "new ", "_old": "old "}.get(which or "", "")
        return f"the {kind}probability of {body}"
    for _ in range(2):
        t = re.sub(r"\bP(_new|_old)?\(([^()]{1,40})\)", prob, t)
    t = re.sub(r"\bnot-([A-Z])\b", r"not \1", t)
    return t


LOGIC = [
    (r"∀(\w)\s?", r"for every \1, "), (r"∃(\w)\s?", r"there is some \1 such that "),
    (r"□\s?", "necessarily "), (r"◇\s?", "possibly "), (r"¬\s?", "not "),
    (r"\s?∧\s?", " and "), (r"\s?∨\s?", " or "), (r"\s?↔\s?", " if and only if "),
    (r"\s?≡\s?", " is equivalent to "), (r"\s?⊢\s?", " entails "), (r"\s?⇄\s?", " and "),
    (r"\s?≈\s?", " approximately "), (r"\s?≠\s?", " does not equal "),
    (r"\s?≤\s?", " is at most "), (r"\s?≥\s?", " is at least "),
    (r"\s?×\s?", " times "), (r"\s?÷\s?", " divided by "), (r"√", "the square root of "),
    (r"∞", "infinity"), (r"∴", "therefore"), (r"\s>\s", " is greater than "), (r"\s<\s", " is less than "),
]

GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "Γ": "gamma", "δ": "delta", "Δ": "delta",
         "θ": "theta", "λ": "lambda", "μ": "mu", "π": "pi", "σ": "sigma", "Σ": "sigma",
         "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega", "Ω": "omega"}

SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
SUP = {"²": " squared", "³": " cubed"}

ABBREVIATIONS = [
    (r"\be\.g\.,?", "for example,"), (r"\bi\.e\.,?", "that is,"), (r"\bcf\.", "compare"),
    (r"\betc\.(?=\s+[a-z])", "and so on"), (r"\betc\.", "and so on."),
    (r"\bet al\.", "and colleagues"), (r"\bvs\.", "versus"), (r"\bviz\.", "namely"),
    (r"\bc\.\s(?=\S*\d)", "around "), (r"\bca\.\s(?=\S*\d)", "around "),
    (r"\bSt\.\s", "Saint "), (r"\bDr\.\s", "Doctor "), (r"\bMr\.\s", "Mister "),
    (r"\bMrs\.\s", "Missus "), (r"\bMs\.\s", "Miz "), (r"\bJr\.", "Junior"),
    (r"\bapprox\.", "approximately"), (r"\biff\b", "if and only if"),
    (r"\bU\.S\.(?=[\s,])", "U.S."), (r"\bBIVs\b", "brains in vats"),
    (r"\bBIV\b", "brain in a vat"), (r"\bvs\b", "versus"),
]

# Words after an initial that start a sentence rather than continue a name
SENTENCE_STARTERS = set("""Therefore So Then Thus Hence The If Not It This That And But Or
Assume Derive All Some No Every I We You He She They A An In On At To Q P R S X Y Z B C See
Now Here There What When Why How Which Who Is Are Was Were Do Does Did Both Either Neither""".split())


def say_symbols(t):
    t = say_probability(t)
    t = re.sub(r"\s?←\s?", " ", t)
    for pat, rep in LOGIC:
        t = re.sub(pat, rep, t)
    t = re.sub(r"((?:not )?\b[A-Z][A-Z]{0,2}\b)\s?→\s?((?:not )?\b[A-Z][A-Z]{0,2}\b)", r"if \1, then \2", t)
    t = re.sub(r"\s?→\s?", ", then ", t)
    t = re.sub(r"(\w)=(\w)", r"\1 equals \2", t)
    t = re.sub(r"\s=\s", " equals ", t)
    t = re.sub(r"(\d|\b[a-zA-Z]\b)\s?\+\s?(?=\d|\b[a-zA-Z]\b)", r"\1 plus ", t)
    t = re.sub(r"\s\+\s", " plus ", t)
    t = re.sub(r"\s?−\s?", " minus ", t)
    for g, name in GREEK.items():
        t = t.replace(g, f" {name} ")
    t = re.sub(r"([A-Za-z])([₀-₉]+)(?=(\w?))", lambda m: m.group(1) + " " + " ".join(m.group(2).translate(SUB))
               + (" " if m.group(3) else ""), t)
    t = re.sub(r"([₀-₉]+)", lambda m: " " + " ".join(m.group(1).translate(SUB)) + " ", t)
    t = re.sub(r"(\d(?:\.\d+)?)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: m.group(1) + " to the power of " +
               m.group(2).translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")), t)
    for s, rep in SUP.items():
        t = t.replace(s, rep)
    t = re.sub(r"\"\s?/\s?\"", '" versus "', t)
    t = re.sub(r"\b([A-Z])%", r"\1 percent", t)
    t = re.sub(r"10([⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: "ten to the power of " +
               m.group(1).translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")), t)
    t = t.replace("&", " and ").replace("§", "section ").replace("~", "about ")
    t = re.sub(r"[؀-ۿ֐-׿一-鿿]+", "", t)  # other scripts
    return t


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman(r):
    total = 0
    for a, b in zip(r, r[1:] + " "):
        v = ROMAN[a]
        total += -v if b != " " and ROMAN[b] > v else v
    return total


def say_roman(t):
    return re.sub(r"\b(Books?|Parts?|Chapters?|Sections?|Lectures?|Volumes?|Meditations?|Essays?)\s+([IVXLC]+)\b"
                  r"(?:\s?[–-]\s?([IVXLC]+)\b)?",
                  lambda m: m.group(1) + " " + words(roman(m.group(2))) +
                  (" to " + words(roman(m.group(3))) if m.group(3) else ""), t)


def say_abbreviations(t):
    t = say_roman(t)
    for pat, rep in ABBREVIATIONS:
        t = re.sub(pat, rep, t)

    def initials(m):
        nxt = m.group(2)
        return m.group(0) if nxt in SENTENCE_STARTERS else m.group(1).replace(".", "") + nxt
    t = re.sub(r"\b((?:[A-Z]\.\s){2,3})([A-Z][a-z]+)", initials, t)
    t = re.sub(r"\b([A-Z]\.\s)([A-Z][a-z]+)(?=\s[A-Z][a-z])", initials, t)  # L. Jonathan Cohen
    return t


# ---------------------------------------------------------------------------
# Inline markdown


LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
YEARISH = re.compile(r"\b(1[0-9]\d\d|20\d\d)\b|\b\d{3,4}\s?(BCE|CE)\b|\b\d{1,4}[ab]\d")
CITATION_MARK = re.compile(r"\*|\"|“|\bch\.|§|\bp\.\s?\d|\bpp\.|\beds?\.|\bvol\.|\btrans\.")


def strip_crossrefs(t):
    """Drop sentences and clauses whose only job is to send the reader elsewhere."""
    t = re.sub(r"\s*→\s*(?:\[[^\]]*\]\([^)]*\)(?:,\s*|\s+and\s+)?)+", "", t)
    t = re.sub(r"\s*\((?:[Ss]ee|[Cc]ompare|[Cc]f\.)\s[^()]*\]\([^)]*\)[^()]*\)", "", t)
    parts, last = [], 0
    for m in re.finditer(r"[.!?][*_\"”')]*\s+(?=[A-Z(\[*\"“])", t):
        parts.append(t[last:m.end()].strip())
        last = m.end()
    parts.append(t[last:])
    keep = []
    for p in parts:
        bare = p.strip("*_ ")
        if (re.match(r"\(?(See|For more|More on this|Compare|Cf\.)\b", bare) and "](" in bare) or \
                re.fullmatch(r"(?:\[[^\]]*\]\([^)]*\)[,.;]?\s*(?:and\s+)?)+", bare):
            closing = LINK.sub("", p).count(")") - LINK.sub("", p).count("(")
            if closing > 0 and keep:
                keep[-1] += ")" * closing
            continue
        keep.append(p)
    return " ".join(keep)


CITATION_WORDS = set("""and or in of the a an by on for to with from eds ed colleagues published written
lectures book trans chapter section part orig et al see also first english translated reprinted
edition vol pp ch ca century cf as at""".split())


def parenthetical(inner, chapter):
    """Decide what a parenthesis becomes when read aloud: nothing, an aside, or a sentence."""
    c = inner.strip()
    plain = re.sub(r"[*_]", "", c)
    if not plain:
        return ""
    # "(Title, 1956: what the author said)" keeps what was said
    m = re.match(r"^[^:]{0,90}\b\d{4}:\s*(.+)$", plain)
    if m and YEARISH.search(plain.split(":")[0]):
        dropped.append((chapter, c.split(":")[0]))
        return m.group(1)
    # Real content, not a citation: a full sentence, or plenty of ordinary words
    core = re.sub(r"\*[^*]*\*|\"[^\"]*\"|“[^”]*”", " ", c)
    ordinary = [w for w in re.findall(r"\b[a-z][a-z'-]+\b", core) if w not in CITATION_WORDS]
    sentence = re.search(r"[.!?][\"']?$", plain) and len(plain.split()) >= 6
    if sentence or len(ordinary) >= 5:
        return re.sub(r",?\s*(§+\s?[\d–-]+|ch\.\s?\d+|p\.\s?\d+)\s*(?=[.]?$)", "", plain)
    if re.match(r"(?i)(see|compare|cf\.)\s", plain) or re.search(r"\bch\.|§|\bpp?\.\s?\d", plain):
        dropped.append((chapter, c))
        return None
    if YEARISH.search(plain):
        nonyear = re.sub(r"\b\d[\d–-]*\b|\b(BCE|CE|c|ca|lectures|book|published|orig|written|first|and)\b\.?|[,;.()–-]", " ", plain)
        if CITATION_MARK.search(c) or len(nonyear.split()) <= 4:
            dropped.append((chapter, c))
            return None
    ref = r"[\w./–-]*\d[\w./–-]*|[IVXLC]+\.[\w.]+"
    if re.fullmatch(rf"(c\.\s*)?\d{{1,4}}\s?(BCE|CE)?(\s?[–-]\s?(c\.\s*)?\d{{1,4}}\s?(BCE|CE)?)?", plain) or \
            re.fullmatch(rf"([A-Z][a-z]+,?\s)?({ref})((,|;|\sand)\s({ref}))*", plain):
        dropped.append((chapter, c))
        return None
    if not re.search(r"[A-Za-z0-9]", plain):  # only other scripts
        dropped.append((chapter, c))
        return None
    return plain


def flatten_parens(t, chapter):
    """Replace (...) groups, innermost first, following `parenthetical`."""
    verbs = r"(?:is|are|was|were|has|have|had|can|could|might|may|must|would|should|will|does|do|did|involves|seems|fails|holds)\b"
    t = re.sub(r"(^|[.!?:;]\s+|[“\"])\(([a-hA-H])\)\s(?=" + verbs + ")", lambda m: f"{m.group(1)}{m.group(2).upper()} ", t)
    t = re.sub(r"(^|[.!?:;]\s+|[“\"])\(([a-hA-H])\)\s", lambda m: f"{m.group(1)}{m.group(2).upper()}: ", t)
    t = re.sub(r"(?<=\s)\(([a-hA-H])\)(?=[\s,.])", lambda m: m.group(1).upper(), t)
    t = re.sub(r"(^|[\s:;“\"])\((i{1,3}|iv|v|vi)\)\s", lambda m: m.group(1) + {
        "i": "one", "ii": "two", "iii": "three", "iv": "four", "v": "five", "vi": "six"}[m.group(2)] + ": ", t)
    # formulas keep their parentheses: P(x) was handled earlier; f(x) style is rare
    while True:
        m = re.search(r"\(([^()]*)\)", t)
        if not m:
            break
        inner = parenthetical(m.group(1), chapter)
        before, after = t[: m.start()], t[m.end():]
        if inner is None or inner == "":
            t = before.rstrip() + after
            continue
        if re.search(r"[.!?][\"']?$", inner) and (before.rstrip().endswith((".", "!", "?", ":")) or not before.strip()):
            t = before.rstrip() + " " + inner + " " + after.lstrip()  # a sentence on its own
        elif re.search(r"[.!?]$", inner):
            t = before.rstrip() + " — " + inner.rstrip(".") + " — " + after.lstrip()
        elif len(inner.split()) <= 8 and "," not in inner and ";" not in inner:
            rest = after.lstrip()
            if rest[:1] in (".", "!", "?", ";", ":", ""):
                t = before.rstrip() + " — " + inner + rest
            else:
                t = before.rstrip() + ", " + inner + "," + ("" if rest[:1] in ",)" else " ") + rest
        else:
            t = before.rstrip() + " — " + inner + " — " + after.lstrip()
    return t


def tidy(t):
    t = re.sub(r"\s+", " ", t).strip()
    rules = [
        (r"\s+([,.;:!?])", r"\1"), (r",\s*([.;:!?])", r"\1"), (r"([.;:!?]),", r"\1"),
        (r",\s*,", ","), (r"—\s*,", "—"), (r"—\s*([.;:!?])", r"\1"), (r"([,;:])\s*—", r"\1"),
        (r"—\s*—", "—"), (r"…\.", "…"), (r"\s*—\s*", " — "), (r"([.!?])\s*\.", r"\1"), (r"^[,;:—\s]+", ""),
        (r"[,;—\s]+$", ""), (r":$", "."), (r"\s+,", ","), (r"([,;:])(?=[A-Za-z])", r"\1 "),
    ]
    while True:
        before = t
        for pat, rep in rules:
            t = re.sub(pat, rep, t)
        if t == before:
            return t.strip()


def speak(t, chapter, cell=False):
    """Markdown inline text to plain spoken English."""
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    if not cell:
        t = strip_crossrefs(t)
    t = LINK.sub(r"\1", t)
    t = t.replace("`", "")
    t = re.sub(r"\*\*|__", "", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])", r"\1", t)
    t = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", t)
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = say_probability(t)
    t = re.sub(r",?\s*\b[IVX]+\.[\dixv]+[a-z]?(?:[.–-][\dixv]+[a-z]?)*\b", "", t)  # II.19, IV.xv–xvi
    t = re.sub(r",?\s*\b\d+[a-e](?:\d+)?(?:\s?[–-]\s?\d*[a-e]\d*)?(?![\w])", "", t)  # 97e–98a, 1011b25
    t = re.sub(r",?\s*\bB\d+\b|,?\s*\bA\d+/B\d+\b|,?\s*\b\d+\.\d+\.\d+\b", "", t)  # B18, A51/B75, 1.4.1
    t = flatten_parens(t, chapter)
    t = say_abbreviations(t)
    t = say_symbols(t)
    t = t.replace("N/A", "not applicable")
    t = say_numbers(t)
    t = re.sub(r"(\w)\s*–\s*(\w)", r"\1-\2", t)  # en dash joining words: Duhem–Quine
    t = t.replace("–", " — ")
    t = re.sub(r"(?<=[A-Za-z])\s?/\s?(?=[A-Za-z])", " or ", t)
    t = t.replace("...", "…").replace("[", "").replace("]", "")
    return tidy(t)


# ---------------------------------------------------------------------------
# Blocks


def parse_table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    return cells[0], cells[1:]


def lower_first(s):
    return s if re.match(r"[A-Z]{2,}|I\b", s) else s[:1].lower() + s[1:]


def fill(template, header, row):
    def sub(m):
        idx, mod = m.group(1), m.group(2)
        v = header[int(idx[1:])] if idx.startswith("h") else row[int(idx)]
        return lower_first(v) if mod == "l" else v
    return re.sub(r"\{(h?\d+)(?::(l))?\}", sub, template)


def end(s):
    s = s.rstrip()
    return s if re.search(r"[.!?:\"]$", s) else s + "."


def table_lines(header, rows, chapter):
    key = header[0] if header[0] else "|" + header[1]
    spec = TABLES.get(chapter, {}).get(key)
    if spec is not None and not isinstance(spec, str):  # a list of prepared lines
        return [f"@item {line}" if not line.startswith("@") else line for line in spec]
    out = []
    for row in rows:
        row = [speak(c, chapter, cell=True) for c in row]
        head = [speak(h, chapter, cell=True) for h in header]
        if spec:
            line = fill(spec, head, row)
        elif not head[0]:
            line = end(row[0]) + " " + " ".join(
                (f"{h} {c}" if h.endswith("?") else f"{h}: {c}") + ("" if c.endswith((".", "?", "!")) else ".")
                for h, c in zip(head[1:], row[1:]))
        elif len(head) == 2:
            line = f"{row[0]}: {row[1]}"
        else:
            parts = [end(row[0])]
            for h, c in zip(head[1:], row[1:]):
                if h.endswith("?"):
                    parts.append(f"{h} {end(c)}")
                elif h.endswith(("…", "...")):
                    parts.append(f"{h.rstrip('.…')} {end(lower_first(c))}")
                else:
                    parts.append(f"{h}: {end(c)}")
            line = " ".join(parts)
        out.append("@item " + tidy(end(line)))
    return out


CALLOUTS = {
    "Critical-thinking lesson": "Here's the critical-thinking lesson.",
    "Critical-thinking lessons from Kuhn": "Here are the critical-thinking lessons from Kuhn.",
    "Practical tip": "A practical tip.",
    "Practical upshot": "The practical upshot.",
    "Practical point": "A practical point.",
    "Connection": "A connection worth making.",
    "Lessons": "The lessons.",
    "Lesson": "The lesson.",
    "Defense": "Your defense.",
}


def callout(label):
    key = label.rstrip(".:").strip()
    return CALLOUTS.get(key) or end(speak(key, "callout"))


SPEAKERS = {"A": 1, "B": 2, "Speaker A": 1, "Speaker B": 2}
THREAD = {"Post": 1, "Reply": 2, "Reply to reply": 1}


def speaker_line(l):
    m = (re.match(r"^\*\*([^*.]{1,20}?):\*\*\s+(.*)$", l) or re.match(r"^\*\*([^*.]{1,20}?)\*\*:\s+(.*)$", l)
         or re.match(r"^([AB]):\s+(.*)$", l))
    return (m.group(1), m.group(2)) if m else None


def speaker_cues(l, chapter):
    """One labelled line: a voice for speakers, label and voice for a thread, else an aside."""
    label, said = speaker_line(l)
    if label in SPEAKERS:
        return [f"@voice{SPEAKERS[label]} {speak(said, chapter)}"]
    if label in THREAD:
        return [f"@label {label}.", f"@voice{THREAD[label]} {speak(said, chapter)}"]
    return [f"@aside {end(speak(label, chapter))} {speak(said, chapter)}"]


def blockquote_lines(block, chapter, epigraph=False):
    """A run of '>' lines to script cues."""
    lines = [re.sub(r"^>\s?", "", l) for l in block]
    text_lines = [l for l in lines if l.strip()]
    out = []
    # Epigraph or attributed quotation: quote lines followed by "— Author, Work"
    if text_lines and text_lines[-1].startswith("—") and len(text_lines) >= 2:
        quote = " ".join(text_lines[:-1])
        attr = text_lines[-1].lstrip("— ").strip()
        attr = re.sub(r"\s*\(([^()]*)\)\s*$", "", attr)  # trailing (1784)
        attr = re.sub(r",\s*(?:c\.\s*)?\d{3,4}(?:\s?(?:BCE|CE))?\s*$", "", attr)
        attr = re.sub(r"\s+[IVXLC]+\.\d+.*$|\s+\d+[a-z]?\d*$", "", attr)  # book/section numbers
        out.append("@quote " + speak(quote, chapter))
        out.append("@attr " + end(speak(attr, chapter)))
        return out
    # Dialogue: every line has a speaker label
    labelled = [speaker_line(l) for l in text_lines]
    if len(text_lines) >= 2 and all(labelled) and sum(
            1 for lab in labelled if lab[0] in SPEAKERS or lab[0] in THREAD) >= 2:
        for l in text_lines:
            out.extend(speaker_cues(l, chapter))
        return out
    if len(text_lines) >= 2 and all(labelled):  # a labelled layout, such as Toulmin's parts
        for l in text_lines:
            out.extend(speaker_cues(l, chapter))
        return out
    # Callout: bold label then text
    m = re.match(r"^\*\*([^*]{2,70}?)\*\*[.:]?\s+(.*)$", text_lines[0]) if text_lines else None
    if m and not m.group(1).startswith('"') and len(text_lines) == 1 and len(m.group(2)) > 60:
        out.append("@cue " + callout(m.group(1)))
        out.append(speak(m.group(2), chapter))
        return out
    if m and not m.group(1).startswith('"') and len(text_lines) > 1 and text_lines[1].startswith("- "):
        out.append("@cue " + callout(m.group(1)) + " " + speak(m.group(2), chapter))
        for l in text_lines[1:]:
            out.append("@item " + end(speak(l[2:], chapter)))
        return out
    # Argument layout: numbered premises, a rule, a conclusion
    if any(re.fullmatch(r"—{2,}|-{3,}", l.strip()) for l in text_lines):
        for l in text_lines:
            if re.fullmatch(r"—{2,}|-{3,}", l.strip()):
                out.append("@pause 0.4")
                continue
            mm = re.match(r"^(\d+)\.\s+(.*)$", l)
            if mm:
                out.append(f"@aside Premise {words(int(mm.group(1)))}: {speak(mm.group(2), chapter)}")
                continue
            mm = re.match(r"^C\.\s+(.*)$", l)
            if mm:
                out.append(f"@aside Conclusion: {speak(mm.group(1), chapter)}")
                continue
            out.append("@aside " + speak(l, chapter))
        return out
    # A quotation standing alone
    whole = " ".join(text_lines)
    if re.match(r'^\*{0,2}["“]', whole) and re.search(r'["”]\*{0,2}\.?$', whole) and whole.count('"') + whole.count("“") <= 2:
        out.append("@quote " + speak(whole, chapter))
        return out
    # Anything else: set-off text, each line its own cue
    for l in text_lines:
        mm = re.match(r"^(\d+)\.\s+(.*)$", l)
        if mm:
            out.append(f"@aside {words(int(mm.group(1))).capitalize()}: {speak(mm.group(2), chapter)}")
        elif l.startswith("- "):
            out.append("@aside " + end(speak(l[2:], chapter)))
        elif speaker_line(l) and (speaker_line(l)[0] in SPEAKERS or speaker_line(l)[0] in THREAD):
            out.extend(speaker_cues(l, chapter))
        else:
            m = re.match(r"^\*\*([^*]{2,70}?)\*\*[.:]?\s+(.*)$", l)
            if m and len(m.group(2)) > 60 and not m.group(1).startswith('"'):
                out.append("@cue " + callout(m.group(1)))
                out.append(speak(m.group(2), chapter))
            else:
                out.append("@aside " + end(speak(l, chapter)))
    return out


def number_word(n):
    return words(n).capitalize()


def list_item(text, n, chapter):
    body = speak(text, chapter)
    if n is None:
        return "@item " + end(body)
    return f"@item {number_word(n)}. {end(body)}"


# ---------------------------------------------------------------------------
# Chapter


ANSWER_LEADS = ["Here's the answer.", "Answer.", "Here's what to notice.", "The answer.", "Here's my answer."]


def extra(text, chapter):
    """Hand-written lines: cues stay as they are, words get the same normalization."""
    out = []
    for line in text.strip().split("\n"):
        m = re.match(r"^(@\w+)(?:\s+(.*))?$", line)
        if m and m.group(2) and not re.fullmatch(r"[\d.]+", m.group(2)):
            out.append(f"{m.group(1)} {speak(m.group(2), chapter)}")
        else:
            out.append(line if m else speak(line, chapter))
    return out


def chapter_script(path):
    chapter = path.name[:2]
    src = path.read_text(encoding="utf-8")
    for old, new in REPLACE.get(chapter, []):
        if old not in src:
            raise SystemExit(f"{path.name}: replacement source not found: {old[:60]!r}")
        src = src.replace(old, new)
    lines = src.split("\n")

    title_line = lines[0].lstrip("# ").strip()
    m = re.match(r"Chapter (\d+)\.\s+(.*)", title_line)
    num, title = int(m.group(1)), m.group(2)
    out = [f"@title Chapter {num} — {title}"]
    if num == 1:
        out.extend(extra(WELCOME, chapter))
    out += ["@chime", f"@opening Chapter {words(num)}. {end(title)}", "@pause 1.2"]

    section = None
    i = 0
    intro_done = False
    in_review = False
    question_no = 0
    in_code = False
    para = []

    def flush():
        if para:
            text = re.sub(r"^\*\*(\d+)\.\s", lambda m: f"**{number_word(int(m.group(1)))}. ", " ".join(para))
            out.append(speak(text, chapter))
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if i == 0 or (s.startswith("[") and "](" in s and ("Contents](README.md)" in s)) or "](audio/" in s:
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
            if section == "In this chapter":
                if not intro_done:
                    out.append("@pause 0.6")
                    out.extend(extra(INTROS[chapter], chapter))
                    intro_done = True
            elif section == "Further reading":
                pass
            elif section == "Check your understanding":
                in_review = True
                out.append("@section Quick review")
                out.append("Now it's your turn. Here are some questions to check your understanding. "
                           "After each one I'll leave a few seconds of quiet so you can think. If you "
                           "want longer, pause the recording and try answering out loud, or in writing, "
                           "before you hear mine.")
            else:
                in_review = section.startswith("Practice")
                out.append("@section " + speak(section, chapter))
            i += 1
            continue
        if section in ("In this chapter", "Further reading"):
            i += 1
            continue
        if s.startswith("### ") or s.startswith("#### "):
            flush()
            out.append("@subsection " + speak(s.lstrip("# ").strip(), chapter))
            i += 1
            continue
        if not s or s == "---":
            flush()
            i += 1
            continue
        if in_review:
            flush()
            mq = re.match(r"^\*\*(\d+)\.\*\*\s*(.*)$", s)
            if mq:
                question_no += 1
                out.append("@pause 0.8")
                out.append(f"@question Question {words(question_no)}. {speak(mq.group(2), chapter)}")
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
                        out.extend(table_lines(header, rows, chapter))
                        continue
                    if re.match(r"^(\d+\.|-)\s", chunk):
                        for k, item in enumerate(re.split(r"\n(?=\d+\.\s|-\s)", chunk)):
                            mm = re.match(r"^(\d+)\.\s+(.*)$", item, re.S)
                            if mm:
                                out.append(list_item(mm.group(2).replace("\n", " "), int(mm.group(1)), chapter))
                            else:
                                out.append(list_item(item[2:].replace("\n", " "), None, chapter))
                        continue
                    if chunk.startswith(">"):
                        out.extend(blockquote_lines(chunk.split("\n"), chapter))
                        continue
                    text = speak(chunk.replace("\n", " "), chapter)
                    out.append(f"@answer {ANSWER_LEADS[question_no % len(ANSWER_LEADS)]} {text}" if first else text)
                    first = False
                i = j + 1
                continue
        if s.startswith("|"):
            flush()
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            header, rows = parse_table(lines[i:j])
            out.extend(table_lines(header, rows, chapter))
            i = j
            continue
        if s.startswith(">"):
            flush()
            j = i
            while j < len(lines) and lines[j].startswith(">"):
                j += 1
            block = lines[i:j]
            is_epigraph = section is None and any(l.startswith("> —") for l in block)
            cues = blockquote_lines(block, chapter, is_epigraph)
            if is_epigraph:
                out.extend(cues)
                out.append("@pause 0.8")
            else:
                out.append("@pause 0.3")
                out.extend(cues)
                out.append("@pause 0.3")
            i = j
            continue
        ml = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        mb = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if ml or mb:
            flush()
            item = (ml.group(3) if ml else mb.group(2))
            j = i + 1
            while j < len(lines) and lines[j].startswith("   ") and not re.match(r"^\s*(\d+\.|[-*])\s", lines[j]):
                item += " " + lines[j].strip()
                j += 1
            out.append(list_item(item, int(ml.group(2)) if ml else None, chapter))
            i = j
            continue
        para.append(s)
        i += 1
    flush()

    out.append("@section End of chapter " + words(num))
    out.extend(extra(OUTROS[chapter], chapter))
    return "\n".join(l for l in out if l.strip() and l.strip() != "@item .") + "\n"


def chapters():
    return sorted(p for p in GUIDE.glob("[01][0-9]-*.md") if int(p.name[:2]) <= 16)


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
