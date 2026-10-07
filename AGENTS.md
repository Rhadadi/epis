# Agent instructions

This repository is *Mastering Epistemology*, a bilingual guide published at https://epis.duckdns.org/.

- **Current job:** writing the Deeper study pages for chapters 5–16. Read `deeper/HANDOFF.md` (workflow, setup,
  rules, remaining sections) and `deeper/README.md` (page format) before changing anything.
- **Children's section** (`kids/`, published at /kids/ and /fa/kids/): read `kids/STYLE.md` first; `tools/kids/check.py` runs in
  `tools/deeper/check.sh`.
- **Branch:** `claude/epistemology-learning-guide-s6zuob`. Fetch and merge; never rebase or force-push. No pull
  request unless asked.
- **Never edit** the narrated chapters (`guide/NN-*.md`, `guide/fa/`, audio). `python3 tools/site/frozen.py`
  must pass.
- **Never commit secrets** (API keys, tokens, OAuth secrets). Use environment variables.
- **No invented citations:** every cited source needs word-for-word evidence checked by `tools/deeper/prov2.py`.
- **Check before every commit:** `tools/deeper/check.sh` (strict build, frozen check, link check).
- Site build needs `pip install markdown-it-py mdit-py-plugins pillow`.
