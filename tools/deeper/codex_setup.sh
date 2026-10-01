#!/usr/bin/env bash
# Setup for a sandboxed agent (Codex cloud and the like): site build tools, the search-bot checkout and the
# research corpus. Safe to re-run: existing checkouts, environments and corpus documents are reused.
#
#   WORKSPACE=/workspace bash tools/deeper/codex_setup.sh
#
# Embeddings: the Deeper study tools never use vectors, but search-bot's indexer needs an embedding server.
# This script starts tools/deeper/lexical_embed_server.py, which needs no model download, unless a healthy
# server is already listening on :8082. (The real model, BAAI/bge-base-en-v1.5, comes from Hugging Face's
# CDN, which sandbox proxies often refuse.)
#
# Network: the source hosts must be allowed (see rebuild_corpus.py --check-hosts). Refusals are reported,
# never worked around. SEARCHBOT_OPENALEX_KEY, if set, comes from the environment's secrets, never a file.
set -euo pipefail
WS=${WORKSPACE:-/workspace}
EPIS=$WS/epis SB=$WS/search-bot CONF=$WS/epis-config
BRANCH=claude/epistemology-learning-guide-s6zuob
cd "$EPIS"

if [ "$(git branch --show-current)" != "$BRANCH" ]; then
  test -z "$(git status --porcelain)" || { echo "uncommitted work in $EPIS; not switching branch"; exit 1; }
  git fetch origin "$BRANCH"
  git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" FETCH_HEAD
fi

# site build
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q markdown-it-py mdit-py-plugins pillow

# research engine (no fastembed: the lexical server needs nothing beyond the standard library)
[ -d "$SB/.git" ] || git clone --branch epis-evidence https://github.com/Rhadadi/search-bot.git "$SB"
test "$(git -C "$SB" branch --show-current)" = epis-evidence
[ -x "$SB/.venv/bin/python" ] || python3 -m venv "$SB/.venv"
"$SB/.venv/bin/pip" install -q -r "$SB/requirements.txt"

mkdir -p "$CONF"
[ -f "$CONF/sb.env" ] || sed "s|\"\$HOME/search-bot\"|\"$SB\"|" tools/deeper/sb.env.example > "$CONF/sb.env"
# shellcheck disable=SC1091
source "$CONF/sb.env"
echo "OpenAlex key: $([ -n "${SEARCHBOT_OPENALEX_KEY:-}" ] && echo present || echo absent; true)"

# a failing check is reported but does not stop the research setup; fix it before any commit
PYTHON="$EPIS/.venv/bin/python" tools/deeper/check.sh || echo "CHECK FAILED: see above; fix before committing"

# embedding server: reuse a healthy one, otherwise start the lexical one (logs outside the repositories)
if ! curl -fsS http://127.0.0.1:8082/health >/dev/null 2>&1; then
  nohup python3 tools/deeper/lexical_embed_server.py --port 8082 > "$CONF/embed.log" 2>&1 &
  for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:8082/health >/dev/null 2>&1 && break; sleep 1; done
fi
"$SB/.venv/bin/python" - <<'PY'
import math, requests
r = requests.post("http://127.0.0.1:8082/v1/embeddings", json={"input": ["knowledge and epistemic luck"]}, timeout=60)
r.raise_for_status()
v = r.json()["data"][0]["embedding"]
assert len(v) == 768 and all(math.isfinite(x) for x in v) and any(v), "embedding server returned a bad vector"
print("embeddings: ok,", r.json().get("model"))
PY

# corpus: test the hosts, fetch whatever is missing, then report coverage document by document
"$SB/.venv/bin/python" tools/deeper/rebuild_corpus.py --check-hosts || echo "some hosts are blocked; their documents will be reported missing"
if ! "$SB/.venv/bin/python" tools/deeper/rebuild_corpus.py --report > "$CONF/corpus-report.txt" 2>&1; then
  "$SB/.venv/bin/python" tools/deeper/rebuild_corpus.py > "$CONF/corpus-rebuild.log" 2>&1 || true
fi
"$SB/.venv/bin/python" tools/deeper/rebuild_corpus.py --report | tee "$CONF/corpus-report.txt" || true
"$SB/.venv/bin/python" tools/deeper/find.py 'gettier AND luck' '%' 3 200
git -C "$EPIS" status --short
