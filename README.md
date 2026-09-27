# Epistemology Mastery

A complete, illustrated guide to epistemology and critical thinking: sixteen
chapters with a glossary and reading list, a bilingual (English and Persian)
map of 135 concepts, and a narrated audio edition.

Live site: [rhadadi.github.io/epis](https://rhadadi.github.io/epis/) (GitHub Pages)
and [epis.duckdns.org](https://epis.duckdns.org) (self-hosted).

## The site

| Page | Where | What it is |
| --- | --- | --- |
| Start | [`/`](https://rhadadi.github.io/epis/) | The starting page: what the guide covers and where to begin. |
| فارسی | [`/fa/`](https://rhadadi.github.io/epis/fa/) | The Persian starting page, with a right-to-left version of the same design and translated chapter introductions. |
| The guide | [`/guide/`](https://rhadadi.github.io/epis/guide/) | The contents, then one web page per chapter, each headed by a painting or photograph chosen for its topic. Every chapter has a contents sidebar, and the sixteen main chapters have a built-in audio player that can jump to any section. |
| Concepts | [`/concepts/`](https://rhadadi.github.io/epis/concepts/) | One readable page per concept, in English or Persian: the idea, examples, objections, common mistakes and self-check questions, linked to the chapter that covers it. |
| Map | [`/map/`](https://rhadadi.github.io/epis/map/) | The interactive concept map with its floating, expandable nodes. Selecting a concept opens its page. `/map/#<id>` opens the map at that concept. |
| Listen | [`/guide/audio/`](https://rhadadi.github.io/epis/guide/audio/) | The audio edition: 16 chapters, about 14½ hours, with chapter and section navigation. |
| Credits | [`/credits.html`](https://rhadadi.github.io/epis/credits.html) | The artwork, with sources and licences, plus the voice and fonts. |

Other features:

- Reading settings (text size, spacing, line length, typeface, light, sepia, dark and black themes)
  and a distraction-free focus mode (press F on a chapter)
- Remembers where you stopped reading, and can save the whole guide for offline reading
- Highlights and notes: select any passage to highlight it or write a note; the [Notebook](https://rhadadi.github.io/epis/notes/)
  collects them, with search and export to Markdown or a backup file
- An [EPUB edition](guide/mastering-epistemology.epub) for e-readers
- Key terms in the chapters show their definition on hover; search (press /) covers chapters, glossary and concepts
- Self-check questions you can mark "Got it" or "Not yet", with a [review page](https://rhadadi.github.io/epis/review/)
  that brings them back on a spaced schedule
- **My study** ([/account/](https://rhadadi.github.io/epis/account/)): sign in with Google to sync progress, notes,
  the review deck, settings and AI keys through a private app folder in your own Google Drive (no server)
- A study companion on every chapter and concept page: chat about the page, or select text and press
  **Explain**. With your own Claude or ChatGPT key it answers on the page; without one it prepares the
  question for the free ChatGPT or Claude website (or uses a free endpoint, see `tools/free-chat-worker/`)
- Responsive layout for desktop, tablet and phone
- Keyboard-friendly controls and reduced-motion support
- Self-hosted fonts and no third-party requests, so the site also works offline

## Study guide

The [`guide/`](guide/README.md) folder contains **Mastering Epistemology**
as plain Markdown, one file per chapter, which also reads well on GitHub. It
covers the theory of knowledge, justification, skepticism, logic, probability
and Bayesian reasoning, philosophy of science, truth and relativism, social
epistemology, intellectual virtue, the psychology of reasoning, a field guide
to fallacies, and a practical toolkit for analyzing discussions and framing
arguments, with worked examples and self-check questions throughout. The
twelve-week study plan is in the [reading list](guide/18-reading-list.md).

Every chapter also has a narrated MP3, with a [track list](guide/audio/README.md)
that explains how the audio was made.

## Run locally

The pages are static and already built, so any web server works:

```sh
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Structure

```
index.html, fa/index.html             English and Persian starting pages
credits.html, 404.html                credits and "not found" page
guide/*.md                            the guide (source of truth)
guide/*.html, guide/index.html        the guide as web pages (generated)
guide/audio/                          MP3s, tracks.js, player page, narration scripts
concepts/                             one page per concept (generated)
map/index.html                        the interactive concept map
assets/data/concepts.js               the map's data, also used for the concept pages
assets/art/                           header artwork from Wikimedia Commons, with credits.json
assets/site.css, assets/site.js       the site's styles and scripts
assets/fonts/, assets/diagrams/       self-hosted fonts, rendered diagrams
tools/site/                           the generator and the artwork scripts
```

After editing the guide, the concept data or the artwork list, rebuild the pages
with `python3 tools/site/build.py`; see [`tools/site/README.md`](tools/site/README.md).
