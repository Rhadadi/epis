# Website tools

The website is plain static HTML generated from the guide's Markdown and the
concept map's data. The generated pages are committed, so any static host
(GitHub Pages, a Raspberry Pi running nginx, `python3 -m http.server`) serves
the site as it is, with no build step on the server.

| File | What it does |
| --- | --- |
| `build.py` | Generates every page of the site (see below). |
| `art.json` | The artwork: which painting or photograph heads each page, and its caption. |
| `fetch_art.py` | Downloads the artwork in `art.json` from Wikimedia Commons into `assets/art/`. |
| `render_mermaid.cjs` | Renders the guide's Mermaid diagrams to SVG, in light and dark versions. |
| `../../.github/workflows/fetch-art.yml` | Runs `fetch_art.py` on GitHub whenever `art.json` changes and commits the images. |

## Rebuilding the pages

Run this after editing anything in `guide/`, `assets/data/concepts.js`,
`art.json` or `build.py`:

```sh
pip install markdown-it-py pillow
python3 tools/site/build.py
```

It reads:

- `guide/NN-*.md` and `guide/README.md`: the guide. The Markdown stays the source of truth and still reads well on GitHub.
- `guide/audio/tracks.js`: the audio tracks, with the start time of every section.
- `assets/data/concepts.js`: the concept map's data, shared with `map/index.html`.
- `tools/site/art.json` and `assets/art/*.jpg`: the artwork.

It writes:

- `index.html`: the starting page.
- `guide/index.html` and `guide/NN-*.html`: the contents page and one page per chapter.
- `guide/audio/index.html` and `guide/audio/about.html`: the player and how the audio was made.
- `concepts/index.html` and `concepts/<id>.html`: the concept index and one page per concept (English and Persian).
- `credits.html`, `404.html` and `.nojekyll`.
- `guide/mastering-epistemology.epub`: the whole guide as an EPUB for e-readers.
- `manifest.webmanifest` and `offline.json`: the app manifest, and the list of files that
  "Save the whole guide for offline reading" fetches.
- `assets/art/<key>-{640,1200,2000}.jpg`: the artwork, cropped and resized.
- `assets/diagrams/<hash>-{light,dark}.svg`: rendered diagrams.

Diagrams are cached by the hash of their source. Only a new or changed diagram
needs Node, with the `mermaid` (version 11) and `playwright-core` packages, and
Chrome or Chromium:

```sh
npm install --no-save mermaid@11 playwright-core
CHROMIUM_PATH=/usr/bin/chromium python3 tools/site/build.py   # the path to your Chrome or Chromium
```

Without Node, a changed diagram is shown as its Mermaid source instead.

## Changing the artwork

Each entry in `art.json` lists Wikimedia Commons file names (`file`) or
Wikipedia article titles (`wiki`, where the article's lead image is used),
tried in order. The other fields make up the caption shown under the header:
artist, title, date, place, a note on why the image fits the chapter, the focal
point used when the image is cropped to the header (`focus`, as a CSS
`object-position`), and an optional `crop` box `[left, top, right, bottom]`, as
fractions of the image, that trims scan margins.

To change an image, edit `art.json` and push. The **Fetch artwork** workflow
downloads it, commits it to `assets/art/` with its licence and credit in
`assets/art/credits.json`, and pushes. Pull that commit, run `build.py`, and
commit the rebuilt pages. You can also run `python3 tools/site/fetch_art.py`
yourself on any machine that can reach Wikimedia.

## The concept map

`map/index.html` is the interactive map. Its data lives in
`assets/data/concepts.js` (`window.EPIS = {N, R, UI}`: the nodes, the full
entries in English and Persian, and the interface strings). Selecting a concept
on the map opens its page in `concepts/`, and `map/#<id>` opens the map with
that concept in view.

## Fonts

The fonts are self-hosted from `assets/fonts/` (from the `@fontsource`
packages), all under the SIL Open Font License; the licences are in
`assets/fonts/licenses/`.

## Reading settings, focus mode and offline reading

All of this runs in the reader's browser and is stored there (`localStorage`):

- `assets/site.js` builds the reading-settings panel (the **Aa** button: text size,
  line spacing, line length, typeface, theme), focus mode (**F**, or the button next
  to **Aa**; **Esc** leaves it), the reading-progress bar, and the "Continue reading"
  prompts on chapter pages, the start page and the contents page.
- `sw.js` (hand-written, at the site root) is the service worker. Pages, styles and
  scripts come from the network first and from the cache when offline; images and
  fonts come from the cache first; audio is never cached.
