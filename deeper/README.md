# Deeper study

A second layer beside the guide's chapters, for readers who arrive because a section didn't click or left
them wanting more. Each substantive section of a chapter can have one Deeper study page. The chapter stays the
concise, narrated version; the page explains the idea again, tells the full story behind it, fills in what the
chapter leaves out, and gives the sources.

The narrated chapters are frozen. Nothing here changes `guide/NN-*.md`, their Persian translations or any audio:
the link from a chapter section to its page is added by `tools/site/build.py` when it writes the chapter page,
never to the Markdown. `tools/site/frozen.py` checks this.

## Files

| Path | What it is |
|---|---|
| `src/<chapter>/<section>.md` | One page: `<chapter>` is the chapter's file name (`01-what-is-epistemology`), `<section>` the id of one of its `##` sections (`three-great-distinctions`) |
| `data/sources.json` | The shared bibliography: every work any page cites, with checked details |
| `data/<chapter>/<section>.json` | Provenance for one page: the research questions and, for every source cited, what it was used for and the evidence behind it |
| `data/corpus.json` | The research corpus: every text the pages were researched from, with its link and licence |
| `<chapter>/<section>.html`, `<chapter>/index.html`, `index.html` | Generated pages (do not edit) |

## Tiers

- **Tier A, full study.** All four layers. The sections chosen for full study are listed below.
- **Tier B, short study.** Re-learn, Beyond the chapter and Sources, without The full story.
- Sections with no page (checklists, timelines, summary tables) show no link in the chapter.

Tier A: chapter 1, Three kinds of knowing · Belief, credence, and acceptance · Three great distinctions · Epistemic
reasons versus practical reasons. Chapter 2, Ancient Greece · Epistemology in the Islamic world · The early modern
revolution. Chapter 3, Deduction, induction, and abduction · Validity and soundness. Chapter 4, Sense and reference
· Vagueness and the sorites paradox. Chapter 5, The Gettier problem · Responses to Gettier · Epistemic luck · The
value of knowledge. Chapter 6, Agrippa's trilemma · Foundationalism · Coherentism · Internalism and externalism.
Chapter 7, Perception · Reason and the a priori · Testimony · Knowledge by presence. Chapter 8, Pyrrhonian
skepticism · The closure argument · Responses to skepticism. Chapter 9, Hume's problem of induction · Responses to
Hume · Goodman's new riddle of induction · Bayes' theorem. Chapter 10, Kuhn and paradigms · Underdetermination ·
Causation and causal inference. Chapter 11, Theories of truth · Relativism. Chapter 12, Experts and novices · Peer
disagreement · Epistemic injustice. Chapter 13, The ethics of belief: Clifford and James · Virtue epistemology ·
Faith, reason, and religious epistemology. Chapter 14, Dual-process theories · Motivated reasoning.

A topic that appears in several chapters (the problem of the criterion, Clifford and James, the a priori) gets its
full story on one page; the others give their own short version and link to it with `deeper:<chapter>/<section>`.

## Writing a page

```markdown
---
tier: A
status: draft
updated: 2026-10-02
---

> **In short.** The point of the chapter section in four to six plain sentences, from a new angle.

## Re-learn
### Step by step
### Common confusions

## The full story
### How the idea developed
### ... (original texts, the arguments, the positions, where the debate stands, evidence and cases)

## Beyond the chapter
### What the chapter leaves out
### What the chapter simplifies
### Connections

## Sources
### Where to go next
```

The `##` headings are the layers and must be exactly these, in this order (Tier B leaves out The full story). The
build numbers the layers and ends Sources with the works cited. Within a layer, the `###` sections are free.

- **Layer 1, Re-learn**, is for the reader who didn't get it: plain language, new examples, one concept at a time.
  Its citations appear as one line of sources at its end, not as note numbers.
- **Layer 2, The full story**, is the substance: where the idea came from and why, the original texts, the
  arguments step by step with the objections to each premise, the positions and who holds them, where the debate
  stands now, and the evidence where there is any. Aim for 2,500–5,000 words.
- **Layer 3, Beyond the chapter**: what the chapter leaves out or simplifies, links to the other chapters and to
  other traditions (Islamic, Indian, Chinese) where they genuinely bear on the topic.
- **Layer 4, Sources**: a reading path from a free first reading to the classics and the current literature.

### Blocks

A block is ordinary Markdown between `::: kind Title` and `:::`, shown as a box:

| Kind | Use |
|---|---|
| `original` | A passage from an original text, quoted in a blockquote and followed by a commentary. Public-domain texts can be quoted at length; anything in copyright only briefly. |
| `argument` | An argument as a numbered list of premises and conclusion (shown as P1, P2, ...). Objections refer to premises by number. |
| `timeline` | A bulleted list of dated events. |
| `positions` | A table of positions: the view, who holds it, its core claim, the main objection. On phones each row is shown as a card, so keep the first column short: it becomes the card's title. |
| `box` | Anything else that should stand apart. |

A block's sources go in a citation that opens the paragraph right after it (`[@key, § 1]. The usual replies ...`,
or the citation alone on a line). The build moves that citation onto the block's title, so the note number sits on
the title rather than at the start of the next paragraph.

Mermaid diagrams (```` ```mermaid ````) work as in the chapters.

### Citations and links

- **Citations** are `[@key]`, `[@key, locator]` or several separated by `;`. **Keys** refer to `data/sources.json`.
  Every source needs a DOI, an ISBN or a stable link, and a `verified` note saying how its details were checked (a
  Crossref record, the full text, a library catalogue). Authors are written `"Family, Given"`.
- Explanations and invented examples need no citation; every claim about what a philosopher held, what a study
  found or what the literature says does.
- `[text](07-sources-of-knowledge.md#testimony)` links to a chapter section; `[text](deeper:07-sources-of-knowledge/testimony)`
  to another Deeper study page.
- **`status: draft`** keeps a page off the live site: it is not built and the chapter shows no link to it. Preview
  drafts with `EPIS_DEEPER_DRAFTS=1 python3 tools/site/build.py`. **`status: published`** builds it, and the build
  fails if any cited source lacks evidence in the provenance record, a layer is missing, or the page is not a
  section of its chapter.

## Provenance (`data/<chapter>/<section>.json`)

```json
{
  "chapter": "01-what-is-epistemology",
  "section": "three-kinds-of-knowing",
  "questions": ["What is Ryle's regress argument against intellectualism?"],
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
```

An `excerpt` is the source's own words, copied from the passage that supports the claim, and checked word for word
against the research corpus when the file is written; `corpus_chunk` numbers that passage in the corpus snapshot,
while the locator and excerpt identify it in the source itself. `basis` says how a claim was checked: `full text`
(the work itself was read), `secondary` (through a named secondary source, which is then cited too), or `catalogue`
(the bibliographic record only, for a work cited as a pointer rather than for a specific claim).

## Checks

```sh
python3 tools/site/frozen.py        # the narrated text and audio are unchanged
python3 tools/site/build.py         # builds the site; fails on problems in a published page
python3 tools/site/check_links.py   # every link and anchor on the site resolves
```
