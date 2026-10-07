#!/usr/bin/env python3
"""Validate Persian Deeper translations against their checked English editions.

Translations reuse English evidence; they must not introduce new citations or
pretend that Persian quotation wording occurs in the English research corpus.
This verifies edition identity, complete structure, source/link preservation and
the shared provenance. Semantic fidelity still requires editorial review.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
EN = ROOT / "deeper/src"
FA = ROOT / "deeper/src-fa"
CITATIONS = re.compile(r"\[@[^\[\]]+\]")
LINKS = re.compile(r"\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")
LAYERS = {
    "Re-learn": "بازآموزی",
    "The full story": "شرح تفصیلی",
    "Beyond the chapter": "فراتر از فصل",
    "Sources": "منابع",
}


def split_page(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}, text
    meta = {}
    for line in match[1].splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, text[match.end():]


def counters_differ(left, right):
    a, b = Counter(left), Counter(right)
    return a - b, b - a


def validate_page(source, translation, provenance=None, annotations=None, require_hash=True):
    """Return material structural/evidence problems for one translation."""
    errors = []
    en_meta, en = split_page(source)
    fa_meta, fa = split_page(translation)
    if fa_meta.get("tier") != en_meta.get("tier"):
        errors.append("study tier differs from the English edition")
    if fa_meta.get("status") not in {"draft", "published"}:
        errors.append("status must be draft or published")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if require_hash and fa_meta.get("source_sha256") != digest:
        errors.append("source_sha256 is missing or the English edition changed")
    if not re.match(r"\s*> \*\*چکیده\.\*\*", fa):
        errors.append("missing Persian > **چکیده.** introduction")
    expected_layers = [LAYERS.get(h, h) for h in re.findall(r"^## (.+)$", en, re.M)]
    actual_layers = re.findall(r"^## (.+)$", fa, re.M)
    if actual_layers != expected_layers:
        errors.append("translated layers are missing, renamed or out of order")
    for level in [3, 4]:
        marker = "#" * level
        if len(re.findall(rf"^{marker} ", en, re.M)) != len(re.findall(rf"^{marker} ", fa, re.M)):
            errors.append(f"H{level} section count differs: a section may have been omitted")
    missing, extra = counters_differ(CITATIONS.findall(en), CITATIONS.findall(fa))
    if missing:
        errors.append("missing/changed citations: " + "; ".join(missing))
    if extra:
        errors.append("new/changed citations: " + "; ".join(extra))
    missing, extra = counters_differ(LINKS.findall(en), LINKS.findall(fa))
    if missing or extra:
        errors.append("source URLs or canonical reading links differ from the English edition")
    block_pattern = r"^::: *([a-z]+)(?: |$)"
    if Counter(re.findall(block_pattern, en, re.M)) != Counter(re.findall(block_pattern, fa, re.M)):
        errors.append("an original, argument, timeline, position or example block is missing")
    if len(re.findall(r"^:::\s*$", en, re.M)) != len(re.findall(r"^:::\s*$", fa, re.M)):
        errors.append("block closing count differs")
    for pattern, label in [(r"^> ", "blockquote"), (r"^\|", "table row"), (r"^\s*(?:- |\d+\. )", "list item")]:
        if len(re.findall(pattern, en, re.M)) != len(re.findall(pattern, fa, re.M)):
            errors.append(f"{label} count differs: content may have been omitted")
    # Guard against replacing a full study with a short synopsis. This is a
    # coverage alarm, never a substitute for reading the translated prose.
    if len(fa.split()) < len(en.split()) * 0.65:
        errors.append("translation is substantially shorter than its English edition")
    body_without_citations = CITATIONS.sub("", fa)
    persian_letters = len(re.findall(r"[آ-ی]", body_without_citations))
    latin_letters = len(re.findall(r"[A-Za-z]", body_without_citations))
    if persian_letters < latin_letters * 1.5:
        errors.append("substantial English prose may have been left untranslated")
    if re.search(r"[يك]", fa):
        errors.append("Arabic yeh/kaf found; use Persian ی/ک")
    if provenance is not None:
        evidence = {s["key"]: s for s in provenance.get("sources", [])}
        cited = set(re.findall(r"@([\w:.-]+)", " ".join(CITATIONS.findall(fa))))
        for key in sorted(cited):
            if key not in evidence or not evidence[key].get("evidence"):
                errors.append(f"@{key} has no shared checked source evidence")
        expected_annotations = {s["key"] for s in provenance.get("sources", []) if s.get("annotation")}
        supplied = (annotations or {}).get("annotations", {})
        if set(supplied) != expected_annotations:
            errors.append("Persian source annotations do not match the English annotation keys")
        if any(not isinstance(v, str) or not re.search(r"[آ-ی]", v) for v in supplied.values()):
            errors.append("a source annotation is empty or not translated into Persian")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapters", nargs="*", help="chapter prefixes, e.g. 01 09")
    parser.add_argument("--drafts", action="store_true", help="check existing drafts too")
    parser.add_argument("--allow-unrecorded", action="store_true", help="editorial work in progress: hash may be absent")
    parser.add_argument("--complete", action="store_true", help="require a published translation of every published English page")
    args = parser.parse_args(argv)
    checked, existing, issues = 0, 0, []
    for src in sorted(EN.glob("*/*.md")):
        if args.chapters and not any(src.parent.name.startswith(p + "-") for p in args.chapters):
            continue
        relative = src.relative_to(EN)
        source = src.read_text(encoding="utf-8")
        en_meta, _ = split_page(source)
        if en_meta.get("status") != "published":
            continue
        dest = FA / relative
        if not dest.exists():
            if args.complete:
                issues.append(f"{relative}: no Persian translation")
            continue
        text = dest.read_text(encoding="utf-8")
        meta, _ = split_page(text)
        if meta.get("status") != "published" and not args.drafts:
            if args.complete:
                issues.append(f"{relative}: Persian translation is not published")
            continue
        if not meta.get("translation_of"):
            # Previously published translations use the site's original body
            # fingerprint and heading conventions. Preserve that edition check;
            # the strict builder still checks their citations, links and layers.
            expected = hashlib.sha1(split_page(source)[1].encode("utf-8")).hexdigest()[:10]
            if meta.get("of") != expected:
                issues.append(f"{relative}: existing translation's English edition changed")
            existing += 1
            continue
        expected_id = str(relative.with_suffix(""))
        if meta.get("translation_of") != expected_id:
            issues.append(f"{relative}: incorrect translation_of")
        evidence_path = ROOT / "deeper/data" / relative.with_suffix(".json")
        annotation_path = ROOT / "deeper/data-fa" / relative.with_suffix(".json")
        evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
        annotation = json.loads(annotation_path.read_text()) if annotation_path.exists() else {}
        issues.extend(f"{relative}: {e}" for e in validate_page(
            source, text, evidence, annotation, require_hash=not args.allow_unrecorded))
        checked += 1
    for issue in issues:
        print(issue)
    print(f"Persian Deeper: {checked} full checks, {existing} existing edition checks, {len(issues)} problems")
    return int(bool(issues))


if __name__ == "__main__":
    sys.exit(main())
