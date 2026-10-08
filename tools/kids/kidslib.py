"""Shared parsing for the children's section (kids/): units, stories, level pages, game data, reading level.

build.py, tools/kids/check.py, narrate.py and render_video.py all read the sources through this module, so they
cannot disagree about what a story line or a word is.

Layout (one folder per unit, both languages side by side, because they ship together):

    kids/units.json                  every unit of the curriculum, in order, with its status
    kids/src/<unit>/unit.json        language-neutral: story id, shots (pictures), games, quizzes, words, adult links
    kids/src/<unit>/story.<lang>.md  the story, one line per paragraph; "@role: text" is spoken by that voice,
                                     "@shot s01" starts a new picture
    kids/src/<unit>/<level>.<lang>.md  explorers / investigators lesson pages (::: blocks, see STYLE.md)
    kids/src/<unit>/grownups.<lang>.md
    kids/games/<id>.json             bilingual game and quiz data: English at the top level, Persian under "fa"
    kids/words.json, kids/stories.json, kids/books.json, kids/cast.json
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIDS = ROOT / "kids"
SRC = KIDS / "src"
LANGS = ("en", "fa")
LEVELS = ("explorers", "investigators")
# the blocks of a lesson page, in the order they must appear (further: Investigators only)
BLOCK_ORDER = ["opener", "think", "bigidea", "words", "tryit", "check", "talk", "further"]
REQUIRED = {"explorers": ["think", "bigidea", "words", "tryit", "check", "talk"],
            "investigators": ["think", "bigidea", "words", "tryit", "check", "talk", "further"]}
BLOCK = re.compile(r"(?ms)^::: *([a-z]+)(?: +([^\n]*?))? *\n(.*?)^::: *$\n?")
FRONT = re.compile(r"(?s)^---\n(.*?)\n---\n")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def front_matter(text):
    """Flat "key: value" front matter and the text after it."""
    m = FRONT.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def units():
    """The curriculum: every unit in order, from kids/units.json."""
    return read_json(KIDS / "units.json")


def unit_dir(uid):
    return SRC / uid


def unit_meta(uid):
    return read_json(unit_dir(uid) / "unit.json")


def lesson_blocks(text):
    """The ::: blocks of a lesson page, in order: [(kind, arg, inner)], plus the prose between them."""
    return [(m.group(1), (m.group(2) or "").strip(), m.group(3)) for m in BLOCK.finditer(text)]


# ----------------------------------------------------------------------------- stories

ROLE = re.compile(r"^@([a-z][a-z0-9-]*):\s*(.+)$", re.S)
SHOT = re.compile(r"^@shot\s+([a-z0-9-]+)\s*$")


def story(uid, lang):
    """A unit's story: {"title", "lines": [{"id","role","text","shot"}], "shots": [ids in order]}.
    Paragraphs separated by blank lines are lines; "@shot sNN" on its own changes the picture."""
    meta, body = front_matter((unit_dir(uid) / f"story.{lang}.md").read_text(encoding="utf-8"))
    lines, shots, shot = [], [], None
    for para in re.split(r"\n\s*\n", body.strip()):
        para = " ".join(para.split())
        if not para:
            continue
        m = SHOT.match(para)
        if m:
            shot = m.group(1)
            shots.append(shot)
            continue
        m = ROLE.match(para)
        role, text = (m.group(1), m.group(2).strip()) if m else ("narrator", para)
        lines.append({"id": f"l{len(lines) + 1:03d}", "role": role, "text": text, "shot": shot})
    return {"title": meta.get("title", ""), "lines": lines, "shots": shots}


def words_of(text):
    """The words of a line as shown on the page (whitespace-separated; a ZWNJ stays inside a Persian word)."""
    return text.split()


# ----------------------------------------------------------------------------- reading level

VOWELS = "aeiouy"


def syllables(word):
    """A rough English syllable count, good enough for a reading-level estimate."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def plain(text):
    """Markdown to plain prose for measuring: no links, emphasis marks, list bullets or block markers."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", text, flags=re.M)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"[*_`>|]", "", text)
    return text


def sentences(text, fa=False):
    ends = r"[.!?؟]+" if fa else r"[.!?]+"
    parts = re.split(ends + r"[\"'”»)]*\s+|\n\s*\n", plain(text).strip())
    return [p for p in (s.strip() for s in parts) if len(p.split()) >= 2]


def flesch_kincaid(text):
    """Flesch–Kincaid grade level of English prose."""
    sents = sentences(text)
    words = [w for s in sents for w in re.findall(r"[A-Za-z’']+", s)]
    if not sents or not words:
        return 0.0
    syl = sum(syllables(w) for w in words)
    return 0.39 * len(words) / len(sents) + 11.8 * syl / len(words) - 15.59


def persian_level(text):
    """Average sentence length (words) and average word length (letters) of Persian prose."""
    sents = sentences(text, fa=True)
    words = [w for s in sents for w in s.split()]
    if not sents or not words:
        return 0.0, 0.0
    letters = sum(len(re.sub(r"[^؀-ۿ]", "", w)) for w in words)
    return len(words) / len(sents), letters / len(words)


def avg_sentence(text, fa=False):
    sents = sentences(text, fa)
    return sum(len(s.split()) for s in sents) / len(sents) if sents else 0.0


# ----------------------------------------------------------------------------- bilingual data

def pick(obj, lang):
    """The language-specific view of a bilingual record: English at the top level, Persian under "fa"
    (only the keys that differ are under "fa"; everything else, such as answers, is shared)."""
    if isinstance(obj, list):
        return [pick(x, lang) for x in obj]
    if not isinstance(obj, dict):
        return obj
    fa = obj.get("fa") if lang == "fa" and isinstance(obj.get("fa"), dict) else {}
    return {k: (fa[k] if k in fa else pick(v, lang)) for k, v in obj.items() if k != "fa"}


def missing_fa(obj, path=""):
    """Paths of English strings with no Persian counterpart in a bilingual record (TEXT_KEYS only)."""
    TEXT_KEYS = {"title", "label", "text", "prompt", "q", "why", "explain", "hint", "intro", "done", "alt", "name"}
    out = []
    if isinstance(obj, list):
        for i, x in enumerate(obj):
            out += missing_fa(x, f"{path}[{i}]")
    elif isinstance(obj, dict):
        fa = obj.get("fa") if isinstance(obj.get("fa"), dict) else {}
        for k, v in obj.items():
            if k == "fa":
                continue
            if k in TEXT_KEYS and isinstance(v, str) and v.strip() and k not in fa:
                out.append(f"{path}.{k}")
            elif k == "choices" and isinstance(v, list) and all(isinstance(c, str) for c in v):
                if not (isinstance(fa.get("choices"), list) and len(fa["choices"]) == len(v)):
                    out.append(f"{path}.choices")
            elif isinstance(v, (dict, list)):
                out += missing_fa(v, f"{path}.{k}")
    return out


def game_path(gid):
    """A game's data: the kids' own (kids/games/) or one shared with Baloney Detector (play/data/)."""
    own = KIDS / "games" / f"{gid}.json"
    return own if own.exists() else ROOT / "play" / "data" / f"{gid}.json"


def game(gid):
    return read_json(game_path(gid))


def plain(t):
    """Scene text as it is spoken: without the **bold** and *italic* marks."""
    return re.sub(r"\*+", "", str(t)).strip()


def deck_script(uid, level, lang):
    """Everything a unit's scene deck says aloud, in scene order, as narration lines: {id, role, text, shot}.
    The story keeps its own line ids and shots (so it is the same as story.<lang>.md); every other scene is read by the
    narrator under its scene id: its text, list, new words (word, then meaning) and question. Games and links stay silent."""
    raw = read_json(deck_path_of(uid, level))["scenes"]
    words = {w["id"]: pick(w, lang) for w in read_json(KIDS / "words.json")}
    out, order = [], []
    for sc in raw:
        if "levels" in sc and level not in sc["levels"]:
            continue
        sc = pick(sc, lang)
        if sc.get("story"):
            st = story(uid, lang)
            for ln in st["lines"]:
                out.append({"id": ln["id"], "role": ln["role"], "text": ln["text"], "shot": ln["shot"]})
            order += st["shots"]
            continue
        lines = []
        t = sc.get("text")
        lines += [plain(x) for x in ([t] if isinstance(t, str) else t or [])]
        lines += [plain(x) for x in sc.get("list", [])]
        for wid in [w.strip() for w in re.split(r"[,\s]+", sc.get("words", "")) if w.strip()]:
            if wid in words:
                lines.append(f"{plain(words[wid]['word'])}. {plain(words[wid]['def'])}")
        if sc.get("ask") and sc["ask"].get("q"):
            lines.append(plain(sc["ask"]["q"]))
        if lines:
            order.append(sc["id"])
            out += [{"id": f"{sc['id']}-{i + 1}", "role": "narrator", "text": x, "shot": sc["id"]} for i, x in enumerate(lines)]
    return out, order


def deck_path_of(uid, level):
    return unit_dir(uid) / f"deck.{level}.json"
