#!/usr/bin/env python3
"""Have Gemini watch and listen to a made clip and report problems a person should look at before it is published.

    python3 tools/video/qa.py tools/video/.cache/big-feet-c1-*.mp4 [--ask "extra question"]

It reports: any speech, words or singing in the soundtrack (the voices are added later, so there should be none),
any writing on screen, characters who change look, extra limbs or melting faces, and anything not right for young
children. This is a first look only; a person still watches every clip.

The key comes only from the GEMINI_API_KEY environment variable and is never written anywhere."""
import argparse
import base64
import json
import os
import sys

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = "gemini-flash-latest"
ASK = ("You check short animated clips for a children's learning site (ages 7 to 14). Watch and listen to this clip "
       "and answer briefly, as a list: 1) Soundtrack: describe it; is there any human speech, words or singing? If so, "
       "transcribe it. 2) Any written text, letters or numbers on screen? 3) Do characters keep the same face, hair, "
       "clothes and size throughout, or does anything morph, melt, duplicate, or grow extra limbs? 4) Anything "
       "frightening or not right for young children? 5) Describe the very last frame: who is where (left, middle, "
       "right) and what they are doing. End with one line: VERDICT: OK or VERDICT: CHECK.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--ask", default="")
    args = ap.parse_args()
    token = os.environ.get("GEMINI_API_KEY")
    if not token:
        raise SystemExit("GEMINI_API_KEY is not set")
    for path in args.clips:
        data = base64.b64encode(open(path, "rb").read()).decode()
        body = {"contents": [{"parts": [{"inline_data": {"mime_type": "video/mp4", "data": data}},
                                        {"text": ASK + (" " + args.ask if args.ask else "")}]}]}
        r = requests.post(f"{API}/{MODEL}:generateContent", headers={"x-goog-api-key": token},
                          json=body, timeout=300)
        if r.status_code != 200:
            print(f"{path}: Gemini refused ({r.status_code}): {r.text[:300]}")
            continue
        parts = r.json()["candidates"][0]["content"]["parts"]
        print(f"== {os.path.basename(path)}\n" + "".join(p.get("text", "") for p in parts).strip() + "\n")


if __name__ == "__main__":
    sys.exit(main())
