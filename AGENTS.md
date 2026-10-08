# Agent instructions

This repository is *Mastering Epistemology*, a bilingual guide published at https://epis.duckdns.org/.

- **Current job:** writing the Deeper study pages for chapters 5–16. Read `deeper/HANDOFF.md` (workflow, setup,
  rules, remaining sections) and `deeper/README.md` (page format) before changing anything.
- **Children's section** (`kids/`, published at /kids/ and /fa/kids/): read `kids/STYLE.md` first; `tools/kids/check.py` runs in
  `tools/deeper/check.sh`.
- **Games section** (Baloney Detector, `play/`, published at /play/ and /fa/play/): `tools/play/site_play.py` builds
  it, `tools/play/check.py` checks it; the engines in `assets/games/` are shared with the kids' site.
- **Scene decks** (one idea per screen, animated drawings; `assets/scenes/`, `tools/scenes/`) belong to the kids' site and the games only
  (units: `kids/src/<unit>/deck.<level>.json`, homes: `kids/home.deck.json`, `play/home.deck.json`). The main grown-up site has none: keep
  kids' and games' elements (decks, characters, game bands) off its pages. `tools/scenes/check.py` runs in `tools/deeper/check.sh`.
- **Episodes** (`kids/episodes/`, published at /kids/watch/<id>/): animated films the child plays inside; see the
  Episodes section of `kids/STYLE.md`. Video comes from Pruna p-video-2 (`tools/video/pruna.py`, key only in `PRUNA_API_KEY`) or Google Veo (`veo.py`, `GEMINI_API_KEY`).
- **Look of the kids' site and Baloney Detector** (white paper, black line, hand lettering, bottom bar, after ncase.me/trust):
  `assets/games/paper.css` and `paper.js`, the shell is `safe_shell()` in `tools/site/build.py`. A child picks the age once (the age
  scene of `kids/home.deck.json`, kept in `localStorage["epis-kids"].level`); pages that exist per age (`index.html` = Explorers,
  `investigators.html`) send a child who chose the other age to the right file (`LEVEL_BOOT`) and have **no** Explorers/Investigators
  switch. Title screens use the `title` scene (ring of tiny people, `Puppets.crowd`), the age question the `pick` scene.
- **Branch:** `claude/epistemology-learning-guide-s6zuob`. Fetch and merge; never rebase or force-push. No pull
  request unless asked.
- **Never edit** the narrated chapters (`guide/NN-*.md`, `guide/fa/`, audio). `python3 tools/site/frozen.py`
  must pass.
- **Never commit secrets** (API keys, tokens, OAuth secrets). Use environment variables.
- **No invented citations:** every cited source needs word-for-word evidence checked by `tools/deeper/prov2.py`.
- **Check before every commit:** `tools/deeper/check.sh` (strict build, frozen check, link check).
- Site build needs `pip install markdown-it-py mdit-py-plugins pillow`.
