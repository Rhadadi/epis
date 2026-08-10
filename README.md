# Epistemology Mastery

A bilingual, interactive map of epistemology for exploring concepts, thinkers,
arguments, objections, examples, and practical applications.

Live site: [epis.duckdns.org](https://epis.duckdns.org)

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
