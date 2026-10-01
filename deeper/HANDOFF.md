# Handoff: finishing the Deeper study pages

This file is for whoever continues the work, human or agent (Codex, Claude Code, ...). It says where things
stand, the rules, how to set up the research corpus, and the exact loop for each chapter. Read
[`deeper/README.md`](README.md) first: it defines the page format, the tiers, blocks, citations and provenance.
This file adds the workflow and tools.

- Repository: <https://github.com/rhadadi/epis>, branch `claude/epistemology-learning-guide-s6zuob`
- Live site: <https://epis.duckdns.org/> (GitHub Pages, served from the committed HTML)
- Deeper study index: <https://epis.duckdns.org/deeper/>
- Research engine: <https://github.com/Rhadadi/search-bot>, branch `epis-evidence` (a fork of
  <https://github.com/raaaas/search-bot>)

## 1. Where things stand

| Chapter | Pages | Status |
|---|---|---|
| 01 What is epistemology | 10 | published |
| 02 History of epistemology | 9 | published |
| 03 Logic and arguments | 15 | published |
| 04 Language, concepts and definitions | 17 | published |
| 05–16 | 0 of about 150 | to do (list in section 8) |

After that: the final polish pass (section 9). The Persian Deeper study comes later, after the English is done.

## 2. Rules that are not negotiable

1. **Never edit the narrated chapters.** `guide/NN-*.md`, `guide/fa/*`, the audio and the files listed in
   `tools/site/frozen.sha256` are frozen. `python3 tools/site/frozen.py` must say `OK`.
2. **No invented citations.** Every claim about what a philosopher held, what a study found or what the
   literature says carries a citation, and every cited source has evidence in the page's provenance file: an
   excerpt copied word for word from the corpus. `prov2.py` refuses anything it cannot find. Every
   quotation on a page must be found in a source cited in the same paragraph, or be allowed with `ok-quote:`
   (for invented examples, titles and the like).
3. **Only open texts.** Use open-access, free-to-read and public-domain sources. Never use shadow libraries
   (Library Genesis, Sci-Hub, Anna's Archive and the like). If a host refuses with 403, do not route around it;
   leave the work out or cite it from a secondary source (`ref:secondary`).
4. **Secrets never go in the repository.** No API keys (OpenAlex, OpenAI, ElevenLabs, Azure), DuckDNS tokens or
   OAuth client secrets in any file, commit, log or page. Pass them as environment variables or through the
   agent's secret store. If one is ever committed, rotate it at once; deleting the commit is not enough.
5. **Git.** Work on `claude/epistemology-learning-guide-s6zuob`. Commit per chapter. Push with
   `git push -u origin claude/epistemology-learning-guide-s6zuob`. Fetch and merge; never rebase, amend or
   force-push. No pull request unless the owner asks for one.
6. **Publish a chapter as a whole.** Pages link to each other with `deeper:<chapter>/<section>`; a link to a
   draft breaks the strict build, so set a chapter's pages to `status: published` together.
7. **Do not spend money silently.** The site's narration used paid TTS (ElevenLabs); the Deeper study needs
   none. Do not call paid APIs.

## 3. Setting up

### 3.1 The epis repository (all you need to build the site)

```sh
git clone https://github.com/rhadadi/epis && cd epis
git checkout claude/epistemology-learning-guide-s6zuob
python3 -m venv .venv && . .venv/bin/activate
pip install markdown-it-py mdit-py-plugins pillow
tools/deeper/check.sh          # builds strictly, runs frozen.py and check_links.py
```

`check.sh` should end with `no broken links or anchors` and a clean `git status` (apart from your work).

### 3.2 The research corpus (needed to write new pages)

The pages are researched from one corpus of 270 open texts: 210 Stanford Encyclopedia of Philosophy entries,
17 IEP entries, 20 Project Gutenberg books, 8 Internet Archive scans and 15 open-access articles. It is listed
in `deeper/data/corpus.json`. The texts themselves are **not** in this repository, because SEP, IEP and
several articles may be read freely but not redistributed. A new machine fetches them again:

```sh
# next to the epis checkout
git clone -b epis-evidence https://github.com/Rhadadi/search-bot
python3 -m venv search-bot/.venv && search-bot/.venv/bin/pip install -r search-bot/requirements.txt
cd epis
cp tools/deeper/sb.env.example ~/.config/epis-sb.env   # edit SEARCHBOT_DIR; keep it outside the repo
. ~/.config/epis-sb.env
python3 tools/deeper/lexical_embed_server.py &          # embedding server on :8082, no download (see below)
P=../search-bot/.venv/bin/python
$P tools/deeper/rebuild_corpus.py --check-hosts   # every source host reachable?
$P tools/deeper/rebuild_corpus.py --dry-run       # the 270 targets
$P tools/deeper/rebuild_corpus.py                 # fetch and index; ends with the coverage report
$P tools/deeper/rebuild_corpus.py --report        # any time: what is missing, by name; exit 1 if anything is
$P tools/deeper/find.py 'gettier AND luck' '%' 8 900   # a smoke test
```

The download step tolerates failures batch by batch, so a quiet run proves nothing: the closing `--report`
is the test. It lists each missing document with its link and exits 1 until the corpus is complete.

**Embeddings.** search-bot's indexer stores a vector for every passage, so it needs an embedding server, but
none of the tools here use the vectors: they search the full-text index. `lexical_embed_server.py` (standard
library only) answers the indexer with hashed word vectors and needs no download. search-bot's own
`scripts/embed_server.py` (`pip install fastembed`) serves the real model, BAAI/bge-base-en-v1.5, but downloads
it from Hugging Face's CDN (`huggingface.co` redirecting to `*.hf.co` hosts such as `us.aws.cdn.hf.co`), which
sandbox proxies often refuse. Use the real model only if you want search-bot's semantic search, and then
rebuild the corpus with it, since the two kinds of vector do not mix.

From then on, run every tool in `tools/deeper/` with the search-bot Python
(`../search-bot/.venv/bin/python`) and with `sb.env` sourced. SEP entries are fetched from the same archived
edition the pages cite, so excerpts in existing provenance files still match. A test rebuild of two sources
matched all 55 of their recorded excerpts. Passage numbers (`corpus_chunk`) will differ from those already
recorded. They belong to the snapshot they were checked against, so nothing needs regenerating; do not
regenerate `corpus.json` or provenance files as part of setup.

Hosts the corpus needs: `plato.stanford.edu`, `iep.utm.edu`, `www.gutenberg.org`, `archive.org` (and the
`*.archive.org` hosts it redirects downloads to), `en.wikisource.org`, `www.ebi.ac.uk`, `api.openalex.org`,
`api.crossref.org`, `openlibrary.org`, `doi.org` and the publisher or repository hosts OpenAlex points to,
and `pypi.org` with `files.pythonhosted.org` for installing.

**OpenAlex.** Eight articles come through OpenAlex, which needs an API key (`SEARCHBOT_OPENALEX_KEY`). Get your
own at <https://openalex.org> and set it as an environment variable or agent secret, never in a file. To check
it is set without printing it: `[ -n "${SEARCHBOT_OPENALEX_KEY:-}" ] && echo present`. Without it those eight
are reported missing; the pages that cite them were already checked.

**Hosts that refused downloads (403) from the original research container:** philpapers.org (most often),
onlinelibrary.wiley.com, read.dukeupress.edu, escholarship.org, www.tandfonline.com, www.sciencedirect.com,
quod.lib.umich.edu, jme.bmj.com. Do not work around a refusal. On a personal machine some may work normally;
otherwise cite such works through a secondary source.

### 3.3 Running this with OpenAI Codex

Codex reads `AGENTS.md` at the repository root, which points here.

- **Codex cloud** (chatgpt.com/codex): connect GitHub, choose `rhadadi/epis`, and create an environment
  ([docs](https://developers.openai.com/codex/cloud/environments)). Use this as the setup script:

  ```sh
  WORKSPACE=/workspace bash /workspace/epis/tools/deeper/codex_setup.sh
  ```

  It installs the site and research tools, runs `check.sh`, starts the lexical embedding server, tests the
  hosts, fetches what is missing from the corpus and prints the coverage report. Re-running it is safe. Put
  `SEARCHBOT_OPENALEX_KEY` in the environment's secrets and the hosts of 3.2 in its internet-access
  allowlist. Background processes do not survive into later sessions: restart the embedding server (the
  script's middle step) before fetching new texts. Searching and checking an existing corpus need no server.
- **Codex CLI** (`npm install -g @openai/codex`, <https://github.com/openai/codex>): runs on your own machine
  with your network. Do 3.1 and 3.2 once, then run `codex` in the epis directory.

## 4. The loop, one chapter at a time

For chapter `NN-name`:

1. **Read the chapter** (`guide/NN-name.md`) and list its `##` sections. Section ids are the `<h2 id>` values
   in `guide/NN-name.html` (section 8 lists them). Note which are Tier A.
2. **Find the sources.** For each section, search the corpus:
   `find.py 'gettier AND luck' '%' 8 900` (FTS5 query, title filter, count, width; use `'%'` for any title).
   Read passages with `chunks.py 4210-4216` and grep within passages with `grepc.py 4210-4300 'regex'`.
   Prefer the SEP and IEP entries on the topic, plus a public-domain original text for Tier A pages.
3. **Add missing sources** to `deeper/data/sources.json`, never by hand-typing details from memory:
   - `srcadd.py corpus <doc_id> [key]` for a corpus document (SEP, IEP, books);
   - `srcadd.py doi <doi> [key]` from Crossref; `srcadd.py isbn <isbn> <key>` from Open Library;
   - `register_all.py` registers every SEP or IEP corpus document that has no key yet.
   Check the authors afterwards: IEP entries come without authors (copy them from the entry's "Author
   Information"), and the file keeps its key order (`indent=2`, `ensure_ascii=False`).
   To fetch new texts into the corpus, write a JSON list of targets and run `acquire_json.py FILE`:
   `{"sep": "slug"}`, `{"gutenberg": "1234"}`, `{"ia": "identifier"}`, `{"openalex": "DOI"}`,
   `{"doi": "DOI"}`, `{"url": "...", "kind": "html", "title": "...", "license": "public-domain"}`.
4. **Write the page** in `deeper/src/NN-name/<section-id>.md` with `status: draft`, following `README.md`:
   - it opens with `> **In short.** ...`;
   - its `##` layers are exactly Re-learn, The full story (Tier A only), Beyond the chapter, Sources;
   - Tier A runs to 2,500–5,000 words, with an `original` block quoting a primary text where the corpus has
     one, and `argument`, `timeline` and `positions` blocks where they help;
   - Tier B is shorter: Re-learn and Beyond the chapter, without The full story;
   - every claim about the literature is cited `[@key, § 2.1]`, and the locator is the corpus passage's
     section, page or chapter;
   - prose is plain and direct. Short paragraphs, no filler, no exercises, and nothing restated from the
     chapter without adding something.
5. **Check the quotations:** `qcheck.py deeper/src/NN-name/<section-id>.md` lists every quotation and where
   it was found. A `MISS` that spans two quotations is a false alarm; a real miss means reword or fix.
6. **Write the evidence spec** in `tools/deeper/specs/NN.txt`:
   ```
   == NN-name/section-id
   Q: a research question the page answers
   ok-quote: start of a quotation on the page that is not from a cited source
   @key | § 2.1 | exact excerpt copied from the corpus passage [| note: ...]
   @key | p. 12 | ref:secondary | Quoted in X (key); the book itself was not read
   A @key: one line for the reader on why this source matters
   ```
   Each `(key, locator)` the page cites needs at least one evidence line. Then run
   `prov2.py tools/deeper/specs/NN.txt`. It writes `deeper/data/NN-name/<section>.json` and fails with a
   precise message if an excerpt is not in the source, a cited key has no evidence, a listed key is not
   cited, or a quotation on the page is not in a cited source.
7. **Publish the chapter.** When every page passes, set them all to `status: published`, run
   `tools/deeper/check.sh`, then `corpus.py` (it updates `deeper/data/corpus.json` if the corpus grew), and
   commit `deeper/`, `tools/deeper/specs/`, the rebuilt `guide/NN-name.html` and `offline.json`, plus
   anything else the build changed. Push.

Look at a finished chapter before starting: `deeper/src/03-logic-and-arguments/` and its specs in
`tools/deeper/specs/03.txt` show what passes, including `ok-quote` and `ref:secondary` use.

## 5. Tools (`tools/deeper/`)

| Tool | What it does |
|---|---|
| `corpus_lib.py` | Shared helpers: corpus connection, text folding for matching, source key to corpus documents |
| `find.py QUERY TITLE N WIDTH` | Full-text search of the corpus (SQLite FTS5 syntax) |
| `chunks.py IDS` | Print corpus passages by id or range |
| `grepc.py IDS REGEX [WIDTH]` | Sentences in those passages that match a regex |
| `qcheck.py PAGE` | Where each quotation on a page occurs in its cited sources |
| `prov2.py SPEC...` | Write and check provenance files from specs |
| `srcadd.py`, `register_all.py` | Add bibliography entries from the corpus, Crossref or Open Library |
| `acquire_json.py FILE` | Fetch and index new open texts |
| `rebuild_corpus.py` | Recreate the corpus on a new machine; `--check-hosts`, `--report` |
| `lexical_embed_server.py` | Embedding server that needs no model download |
| `codex_setup.sh` | Whole setup for a sandboxed agent (Codex cloud) |
| `corpus.py` | Regenerate `deeper/data/corpus.json` |
| `check.sh` | Strict build, frozen check, link check, EPUB timestamp restore |
| `specs/02–04.txt` | The evidence specs for chapters 2–4 (chapter 1 was made with earlier scripts) |

## 6. Matching details worth knowing

- Excerpt matching ignores case, whitespace, quote style, `*`, `_` and soft hyphens, and turns SEP's inline
  LaTeX (`\(\Box A\)`) into symbols (`□A`). It does not ignore words: copy excerpts exactly.
- Passages overlap at their edges, and a sentence can be split across two. If the start of an excerpt is
  found but not the whole, shorten it or split it into two evidence lines.
- A citation that opens the paragraph straight after a block (`[@key, § 1]`) is moved onto the block's title.
- Do not add a manual "Sources for this layer" line; the build adds Re-learn's sources itself.
- Known corpus quirk: in *Mysticism and Logic* (key `russell1918`) the passages of chapter X carry the locator
  "XII. Illusions, Hallucinations, And Dreams". Cite them as `ch. X`.

## 7. Topics already covered that later chapters should link to, not repeat

Knowledge by acquaintance, the analytic/synthetic and a priori distinctions, epistemic versus practical reasons,
Peirce on abduction, Russell on descriptions and acquaintance, vagueness, thought experiments and intuitions,
reflective equilibrium, the problem of the criterion (chapter 1 page), and the history pages of chapter 2.
Link with `deeper:<chapter>/<section>`.

## 8. Remaining sections (chapters 5–16)

Tier A sections are in bold. Sections marked "probably no page" are summary tables, practice sets or checklists.
Following README.md, they get no page unless there is something real to add. Chapters 15 and 16 are Tier B
throughout. Chapters 17 (glossary) and 18 (reading list) get no pages.

- **05-the-nature-of-knowledge** (11 pages): `the-tripartite-analysis` · **`the-gettier-problem`** (A) · **`responses-to-gettier`** (A) · `the-inescapability-of-gettier-problems` · **`epistemic-luck`** (A) · **`the-value-of-knowledge`** (A) · `understanding-and-wisdom` · `knowledge-how-revisited` · `knowledge-assertion-and-action` · `knowing-that-you-know` · `why-do-we-have-the-concept-of-knowledge` · `summary-of-theories` (probably no page)
- **06-justification** (16 pages): `what-justification-is` · `defeaters` · `the-regress-problem` · **`agrippas-trilemma`** (A) · **`foundationalism`** (A) · **`coherentism`** (A) · `infinitism` · `foundherentism` · `critical-rationalism` · `comparing-the-structures` (probably no page) · **`internalism-and-externalism`** (A) · `evidentialism` · `reliabilism-about-justification` · `phenomenal-conservatism` · `the-problem-of-the-criterion` · `deontology-and-doxastic-voluntarism` · `fallibilism`
- **07-sources-of-knowledge** (9 pages): `basic-and-derived-sources` · **`perception`** (A) · `memory` · `introspection-and-self-knowledge` · **`reason-and-the-a-priori`** (A) · **`testimony`** (A) · `inference` · **`knowledge-by-presence`** (A) · `intuition-emotion-and-other-candidate-sources`
- **08-skepticism** (10 pages): `why-study-skepticism` · `varieties-of-skepticism` · **`pyrrhonian-skepticism`** (A) · `cartesian-skepticism` · `the-brain-in-a-vat` · **`the-closure-argument`** (A) · **`responses-to-skepticism`** (A) · `skepticism-about-induction-other-minds-and-the-past` · `the-simulation-argument` · `healthy-and-corrosive-skepticism`
- **09-induction-probability-bayes** (12 pages): `kinds-of-non-deductive-inference` · **`humes-problem-of-induction`** (A) · **`responses-to-hume`** (A) · **`goodmans-new-riddle-of-induction`** (A) · `the-paradox-of-the-ravens` · `probability-the-basics` · **`bayes-theorem`** (A) · `bayesian-epistemology` · `full-belief-and-degrees-of-belief` · `common-errors-in-probabilistic-reasoning` · `calibration-and-scoring-rules` · `statistics-and-significance`
- **10-science-and-evidence** (18 pages): `what-makes-science-special` · `the-demarcation-problem` · `inductivism-and-its-limits` · `popper-and-falsificationism` · `the-duhem-quine-problem` · `ad-hoc-hypotheses` · **`kuhn-and-paradigms`** (A) · `lakatos-and-research-programmes` · `feyerabend-and-laudan` · `inference-to-the-best-explanation` · `theory-ladenness-of-observation` · **`underdetermination`** (A) · `scientific-realism-and-anti-realism` · **`causation-and-causal-inference`** (A) · `values-in-science` · `scientific-consensus` · `the-replication-crisis` · `pseudoscience-and-how-to-spot-it`
- **11-truth-and-relativism** (9 pages): `why-truth-matters` · `truth-bearers` · **`theories-of-truth`** (A) · `the-liar-paradox` · `realism-and-anti-realism` · **`relativism`** (A) · `social-constructionism` · `perspectivism-and-objectivity` · `post-truth-and-bullshit`
- **12-social-epistemology** (15 pages): `why-knowledge-is-social` · `trust-and-epistemic-dependence` · **`experts-and-novices`** (A) · **`peer-disagreement`** (A) · `why-reasonable-people-disagree` · **`epistemic-injustice`** (A) · `standpoint-and-feminist-epistemology` · `echo-chambers-and-epistemic-bubbles` · `conformity-cascades-and-herding` · `the-wisdom-and-madness-of-crowds` · `group-knowledge-and-belief` · `misinformation-disinformation-and-propaganda` · `conspiracy-theories` · `epistemic-institutions` · `epistemic-autonomy-and-artificial-intelligence`
- **13-virtues-and-ethics-of-belief** (10 pages): **`the-ethics-of-belief-clifford-and-james`** (A) · `practical-reasons-for-belief` · **`virtue-epistemology`** (A) · `a-catalogue-of-intellectual-virtues` · `intellectual-vices` · `epistemic-humility-and-confidence` · `open-mindedness-and-its-limits` · `pragmatic-encroachment` · `moral-encroachment` · **`faith-reason-and-religious-epistemology`** (A)
- **14-psychology-of-reasoning** (17 pages): `why-psychology-matters-to-epistemology` · **`dual-process-theories`** (A) · `heuristics-and-biases` · `confirmation-bias-and-myside-bias` · **`motivated-reasoning`** (A) · `belief-perseverance-and-biased-assimilation` · `fluency-and-the-illusory-truth-effect` · `overconfidence-and-the-illusion-of-explanatory-depth` · `the-dunning-kruger-effect-and-its-critics` · `identity-protective-cognition` · `mindreading-how-we-attribute-knowledge` · `the-argumentative-theory-of-reasoning` · `ecological-rationality` · `replication-and-the-psychology-of-psychology` · `debiasing-what-works` · `the-scout-mindset` · `forecasting-and-superforecasters`
- **15-fallacies** (6 pages): `how-to-use-this-field-guide` (probably no page) · `fallacies-of-relevance` · `fallacies-of-presumption` · `fallacies-of-ambiguity` · `causal-and-statistical-fallacies` · `rhetorical-tactics-that-corrupt-discussion` · `the-fallacy-fallacy` · `quick-reference-table` (probably no page) · `practice-spot-the-fallacy` (probably no page)
- **16-critical-thinking-toolkit** (16 pages): `the-core-loop` · `step-1-understand-before-you-evaluate` · `step-2-identify-the-kind-of-disagreement` · `stasis-theory` · `step-3-map-the-argument` · `step-4-evaluate-the-premises-and-the-reasoning` · `step-5-evaluate-the-evidence` · `step-6-find-the-crux` · `step-7-weigh-and-conclude` · `framing-an-argument-of-your-own` · `burden-of-proof` · `philosophical-razors-and-heuristics` · `the-baloney-detection-kit` · `the-ethics-of-discussion` · `worked-case-studies` · `checklists` (probably no page) · `daily-practices`

## 9. After the chapters: final polish

1. Read every published page once more, in order, for repetition across pages, broken flow and wording that
   overstates a source.
2. Run `check.sh`, then check a few pages on a phone-sized window (blocks, `positions` tables shown as cards).
3. Update the Tier A list in `README.md` if any choice changed, and this file's status table.
4. Persian: the Persian Deeper study is planned after the English is complete; it is not part of this
   handoff.

## 10. Links

- Codex: <https://developers.openai.com/codex> · cloud environments
  <https://developers.openai.com/codex/cloud/environments> · CLI <https://github.com/openai/codex> ·
  AGENTS.md convention <https://agents.md>
- Claude Code on the web (where this work was done): <https://code.claude.com/docs/en/claude-code-on-the-web>
- Sources: Stanford Encyclopedia of Philosophy <https://plato.stanford.edu> · Internet Encyclopedia of
  Philosophy <https://iep.utm.edu> · Project Gutenberg <https://www.gutenberg.org> · Internet Archive
  <https://archive.org> · OpenAlex <https://openalex.org> · Crossref <https://www.crossref.org> · Europe PMC
  <https://europepmc.org>
