# Scholarly companions

A second layer beside the guide's chapters, for readers who want the scholarly discussion behind
them. Each companion follows one chapter section by section: the chapter stays the concise, narrated
version, and the companion carries the extended discussion, the scholarly disagreements, the
qualifications the chapter leaves out, numbered notes and sources.

The narrated chapters are frozen. Nothing here changes `guide/NN-*.md`, their Persian translations
or any audio: the links from a chapter to its companion are added by `tools/site/build.py` when it
writes the chapter page, never to the Markdown. `tools/site/frozen.py` checks this (see below).

## Files

| Path | What it is |
|---|---|
| `src/NN-*.md` | A companion, one per chapter, named like the chapter |
| `data/sources.json` | The shared bibliography: every work any companion cites, with verified details |
| `data/NN-*.json` | Provenance for one companion: for each section, the research questions asked and, for each source cited, what it was used for and the evidence behind it |
| `data/corpus.json` | The research corpus: every text the companions were researched from, with its link, licence and retrieval date |
| `NN-*.html`, `index.html` | Generated pages (do not edit) |

## Writing a companion

Front matter, then one `##` section for each substantive section of the chapter, with **the same
heading text as the chapter**, so the section ids match and the chapter's links land on them:

```markdown
---
chapter: 01-what-is-epistemology
status: draft
updated: 2026-10-01
---

## Three kinds of knowing

### Knowledge-how
Ryle argued that knowing how is not a matter of knowing facts [@ryle1949, ch. 2].
```

- **Citations** are `[@key]`, `[@key, locator]` or several separated by `;`. Each becomes a numbered
  note; the notes and the full references of the works cited follow each section, and a
  bibliography ends the page.
- **Keys** refer to `data/sources.json`. Every source needs a DOI, an ISBN or a stable link, and a
  `verified` note saying how its details were checked (a Crossref record, the full text, a library
  catalogue). Authors are written `"Family, Given"`.
- **`status: draft`** keeps a companion off the live site: its page is not built and the chapter
  shows no links to it. Preview a draft with `EPIS_SCHOLARLY_DRAFTS=1 python3 tools/site/build.py`.
  **`status: published`** builds it, and the build fails if any cited source lacks evidence in the
  provenance record, or if a section is not one of the chapter's.

## Provenance (`data/NN-*.json`)

```json
{
  "chapter": "01-what-is-epistemology",
  "sections": {
    "three-kinds-of-knowing": {
      "questions": ["What is Ryle's argument against intellectualism about knowing how?"],
      "sources": [
        {"key": "pavese2022", "used_for": ["Ryle's regress argument"],
         "evidence": [{"locator": "§ 1", "basis": "full text", "corpus_chunk": 684,
                       "excerpt": "it would be a logical impossibility for anyone ever to break into the circle"}],
         "annotation": "One line for the reader on why this source matters."},
        {"key": "ryle1949", "used_for": ["the regress argument, pp. 19–20"],
         "evidence": [{"locator": "pp. 19–20", "basis": "secondary",
                       "note": "Quoted in the SEP entry “Knowledge How” (pavese2022); the book itself was not read"}],
         "annotation": "Ryle's classic statement of anti-intellectualism."}
      ]
    }
  }
}
```

An `excerpt` is the source's own words, copied from the passage that supports the claim; `corpus_chunk`
numbers that passage in the research corpus snapshot (`corpus` at the top of the file), while the
locator and excerpt identify it in the source itself. A top-level `not_verified_here` list records
claims in the chapter that the research did not check.

`basis` says how the claim was checked: `full text` (the work itself was read), `secondary` (through
a named secondary source, which is then cited too), or `catalogue` (the bibliographic record only, for
a work cited as a pointer rather than for a specific claim).

## Checks

```sh
python3 tools/site/frozen.py        # the narrated text and audio are unchanged
python3 tools/site/build.py         # builds the site; fails on problems in a published companion
python3 tools/site/check_links.py   # every link and anchor on the site resolves
```
