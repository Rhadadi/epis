# Epistemology Mastery

A bilingual, interactive map of epistemology for exploring concepts, thinkers,
arguments, objections, examples, and practical applications.

Live site: [epis.duckdns.org](https://epis.duckdns.org)

## Study guide

The [`guide/`](guide/README.md) folder contains **Mastering Epistemology**, a
long-form companion to the explorer: sixteen cross-linked chapters plus a
glossary and a reading list with a twelve-week study plan. It covers the
theory of knowledge, justification, skepticism, logic, probability and Bayesian
reasoning, philosophy of science, truth and relativism, social epistemology,
intellectual virtue, the psychology of reasoning, a field guide to fallacies,
and a practical toolkit for analyzing discussions and framing arguments, with
worked examples and self-check questions throughout.

Every chapter also has a narrated audio version, about 14 hours in all, with a
[player page](guide/audio/index.html) and the [track list](guide/audio/README.md).

Start with the [guide's contents page](guide/README.md).

## Features

- English and Persian reading modes
- Expandable concept map with search, pan, zoom, fit, and reset controls
- Detailed learning cards with examples, objections, common mistakes, and self-checks
- System-aware light and dark themes with a persistent manual preference
- Responsive layout for desktop, tablet, and mobile
- Accessible color contrast, keyboard-friendly controls, and reduced-motion support

## Run locally

No build step or dependencies are required.

```sh
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Structure

The application is intentionally distributed as a single static `index.html`
file. Its content, styles, data, and interaction logic are all self-contained;
only the web fonts are loaded externally.

The study guide is plain Markdown in `guide/`, one file per chapter, and
renders directly on GitHub.
