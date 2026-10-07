"""Regression checks for the evidence/coverage gates of Persian translations."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("check_fa", Path(__file__).with_name("check_fa.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SOURCE = """---
tier: B
status: published
---
> **In short.** Evidence can support a belief without making it certain.

## Re-learn
### One example
A train timetable gives you a reason to expect a departure. It can be revised. [@source, § 1]

## Beyond the chapter
### A connection
[Read about testimony](07-sources-of-knowledge.md#testimony).

## Sources
### Read next
Start with the cited source. [@source, § 1]
"""
TRANSLATION = """---
tier: B
status: published
source_sha256: HASH
---
> **چکیده.** شواهد می‌توانند از باوری پشتیبانی کنند، بی‌آنکه آن را یقینی سازند.

## بازآموزی
### یک مثال
جدول زمان حرکت قطار دلیلی برای انتظار حرکت در ساعت معین به شما می‌دهد. بااین‌حال، این جدول ممکن است
تغییر کند و دانستن آن به معنای آگاهی یقینی از آنچه رخ خواهد داد نیست. [@source, § 1]

## فراتر از فصل
### یک پیوند
[دربارهٔ گواهی بخوانید](07-sources-of-knowledge.md#testimony).

## منابع
### مسیر مطالعه
برای آغاز مطالعه، منبع یادشده را بخوانید و به تفاوت پشتیبانیِ شواهد و یقین توجه کنید. [@source, § 1]
""".replace("HASH", hashlib.sha256(SOURCE.encode()).hexdigest())
PROVENANCE = {"sources": [{"key": "source", "evidence": [{"excerpt": "checked source words"}],
                           "annotation": "An introduction."}]}
ANNOTATIONS = {"annotations": {"source": "درآمدی برای شناخت این بحث."}}


class TranslationEvidenceTests(unittest.TestCase):
    def problems(self, translation=TRANSLATION, source=SOURCE, provenance=PROVENANCE):
        return module.validate_page(source, translation, provenance, ANNOTATIONS)

    def test_complete_persian_translation_reuses_original_evidence(self):
        self.assertEqual(self.problems(), [])

    def test_missing_citation_occurrence_cannot_hide_behind_same_source_set(self):
        edited = TRANSLATION.replace("[@source, § 1]", "", 1)
        self.assertTrue(any("missing/changed citations" in p for p in self.problems(edited)))

    def test_new_source_and_changed_location_are_rejected(self):
        for edited in [TRANSLATION.replace("@source", "@invented", 1),
                       TRANSLATION.replace("§ 1", "§ 2", 1)]:
            self.assertTrue(any("new/changed citations" in p for p in self.problems(edited)))

    def test_source_edit_requires_review_of_translation(self):
        self.assertTrue(any("English edition changed" in p for p in self.problems(source=SOURCE + "\nA new claim.\n")))

    def test_missing_argument_or_section_is_not_accepted_as_translation(self):
        edited = TRANSLATION.replace("### یک مثال\n", "")
        self.assertTrue(any("H3 section count differs" in p for p in self.problems(edited)))

    def test_citation_without_checked_evidence_is_rejected(self):
        self.assertTrue(any("no shared checked source evidence" in p for p in self.problems(provenance={})))

    def test_changed_canonical_link_is_rejected(self):
        edited = TRANSLATION.replace("#testimony", "#invented")
        self.assertTrue(any("canonical reading links differ" in p for p in self.problems(edited)))


if __name__ == "__main__":
    unittest.main()
