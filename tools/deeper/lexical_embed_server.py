"""lexical_embed_server.py [--port 8082] [--dim 768]: a stand-in embedding server that needs no model download.

search-bot's indexer asks an OpenAI-compatible /v1/embeddings endpoint for a vector for every passage it stores.
The real server (search-bot's scripts/embed_server.py) downloads BAAI/bge-base-en-v1.5 from Hugging Face, which
some sandboxes block. The Deeper study tools never use the vectors: find.py, chunks.py, grepc.py, qcheck.py and
prov2.py work on the full-text index and the stored passages. So when the model cannot be downloaded, run this
instead. It returns hashed bag-of-words vectors (words and word pairs, signed feature hashing), which are
deterministic, never zero, and good enough for rough lexical similarity.

Standard library only. A corpus indexed with these vectors should be re-embedded before anyone relies on
search-bot's semantic search (research_section); the evidence workflow in deeper/HANDOFF.md does not."""
import argparse, hashlib, json, math, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WORD = re.compile(r"[a-z0-9]+")


def vector(text, dim):
    words = WORD.findall(text.lower())
    feats = words + [a + " " + b for a, b in zip(words, words[1:])]
    v = [0.0] * dim
    v[0] = 1e-3  # never a zero vector, even for empty text
    for f in feats:
        h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
        v[h % dim] += 1.0 if (h >> 32) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8082)
    ap.add_argument("--dim", type=int, default=768)  # the dimension of bge-base, so a later switch keeps the schema
    args = ap.parse_args()
    name = f"lexical-hash-{args.dim}"

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.rstrip("/") in ("/v1/models", "/models"):
                return self._send(200, {"object": "list", "data": [{"id": name, "object": "model"}]})
            if self.path.rstrip("/") in ("/health", ""):
                return self._send(200, {"status": "ok"})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path.rstrip("/") not in ("/v1/embeddings", "/embeddings"):
                return self._send(404, {"error": "not found"})
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            texts = req.get("input", [])
            texts = [texts] if isinstance(texts, str) else texts
            self._send(200, {"object": "list", "model": name,
                             "data": [{"object": "embedding", "index": i, "embedding": vector(t, args.dim)}
                                      for i, t in enumerate(texts)]})

        def log_message(self, *a):
            pass

    print(f"embeddings: {name} on http://{args.host}:{args.port}/v1", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
