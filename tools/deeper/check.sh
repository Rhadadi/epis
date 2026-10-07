#!/usr/bin/env bash
# Build the site strictly and run every check. Run from anywhere; exits non-zero on the first failure.
# Restores the two EPUBs when the rebuild changed only their timestamp, so commits stay clean.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=${PYTHON:-python3}
unset EPIS_DEEPER_DRAFTS   # the strict build: published pages must have full provenance
timeout 900 "$PY" tools/site/build.py
"$PY" tools/deeper/check_fa.py
"$PY" tools/site/frozen.py
"$PY" tools/site/check_links.py
for f in guide/mastering-epistemology.epub fa/guide/mastering-epistemology-fa.epub; do
  tmp=$(mktemp)
  git show "HEAD:$f" > "$tmp" 2>/dev/null && "$PY" tools/deeper/epub_same.py "$tmp" "$f" && git checkout -- "$f" || true
  rm -f "$tmp"
done
git status --short
