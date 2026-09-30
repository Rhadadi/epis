#!/usr/bin/env python3
"""Check a chapter's speech text (narration/NN-*.txt, narration edition v2) against its narration script
(scripts/NN-*.txt), which it rewrites for the ear:

  - the same section titles, in the same order (they are the audio's section markers);
  - every quotation and its source, every line of dialogue, every quiz question and answer: the same
    words (punctuation and sentence breaks may differ);
  - every term the chapter sets in bold, and every Latin-script term, kept;
  - words of the script that no longer appear, listed for review (a rewrite adds and moves words; it
    should not lose the chapter's content);
  - the length, compared.

    python3 check_narration.py 08 [09 ...]      exit status 1 if a check fails
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIO = HERE.parent
sys.path.insert(0, str(HERE))
from eleven_narrate import parse  # noqa: E402

FUNCTION = set("""و در به از که این آن را با برای هم یا تا اما ولی یک است هست بود شد شود کرد کند می‌کند نیست نه هر چه چون اگر پس
بلکه همان همین ما شما او آن‌ها این‌ها خود دیگر نیز باید چطور چرا کی کجا آیا دارد دارند داریم دارید شده شده‌اند است، یعنی""".split())


def words(t):
    t = re.sub(r"[ً-ٰٟ]", "", t).replace("‌", " ")
    return re.findall(r"[\w'’-]+", t)


def bare(t):
    return " ".join(words(t))


def check(n):
    src = next((AUDIO / "scripts").glob(f"{n}-*.txt"))
    new = AUDIO / "narration" / src.name
    if not new.exists():
        print(f"{n}: no speech text yet ({new.relative_to(AUDIO)})")
        return False
    a, b = parse(src.read_text(encoding="utf-8")), parse(new.read_text(encoding="utf-8"))
    ok = True

    def fail(msg):
        nonlocal ok
        ok = False
        print(f"  FAIL {msg}")

    secs = lambda cues: [t for k, t in cues if k in ("section", "opening", "title")]
    if secs(a) != secs(b):
        fail(f"section titles differ:\n    {secs(a)}\n    {secs(b)}")
    for kinds, what in ((("quote", "attr"), "quotations and sources"), (("voice1", "voice2", "voice3"), "dialogue"),
                        (("question",), "quiz questions"), (("answer",), "quiz answers")):
        x = [bare(t) for k, t in a if k in kinds]
        y = [bare(t) for k, t in b if k in kinds]
        if len(x) != len(y):
            fail(f"{what}: {len(x)} in the script, {len(y)} in the speech text")
            continue
        for p, q in zip(x, y):
            if p != q and kinds != ("answer",):
                fail(f"{what} changed:\n    {p[:120]}\n    {q[:120]}")
    body_a = " ".join(t for k, t in a if t and k not in ("pause", "think"))
    body_b = " ".join(t for k, t in b if t and k not in ("pause", "think"))
    # bold terms of the chapter that the script says, and Latin-script terms: all kept
    md = next((AUDIO.parent).glob(f"{n}-*.md")).read_text(encoding="utf-8")
    bold = {re.sub(r"[*_]", "", m).strip() for m in re.findall(r"\*\*([^*\n]{2,60})\*\*", md)}
    spoken_a, spoken_b = bare(body_a), bare(body_b)
    for term in sorted(bold):
        t = bare(term)
        if t and t in spoken_a and t not in spoken_b:
            fail(f"term dropped: {term}")
    for lat in sorted(set(re.findall(r"[A-Za-zÀ-ÿĀ-žēīōū][A-Za-zÀ-ÿĀ-žēīōū'’ .,-]*[A-Za-zÀ-ÿĀ-žēīōū]", body_a))):
        if bare(lat) not in spoken_b:
            fail(f"Latin-script term dropped: {lat}")
    # words that are gone (content words only; counted, so a word said three times and now once shows)
    from collections import Counter
    ca, cb = Counter(w for w in words(body_a) if w not in FUNCTION), Counter(w for w in words(body_b) if w not in FUNCTION)
    gone = sorted((w for w in ca if w not in cb), key=lambda w: -ca[w])
    ratio = len(body_b) / max(1, len(body_a))
    print(f"{n}: {len(body_a):,} -> {len(body_b):,} characters ({ratio:.2f}); lines {len(a)} -> {len(b)}; "
          f"words no longer said: {len(gone)}" + (f" — {'، '.join(gone[:60])}" if gone else ""))
    if not 0.9 <= ratio <= 1.2:
        fail(f"length changed by {ratio:.2f}")
    return ok


if __name__ == "__main__":
    results = [check(n) for n in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
