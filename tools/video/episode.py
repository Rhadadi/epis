#!/usr/bin/env python3
"""Publish a kids' episode: voice its lines (ElevenLabs), and turn the Veo clips into small web files.

    python3 tools/video/episode.py kids/episodes/big-feet.json --dry-run   # what would be voiced, nothing sent
    python3 tools/video/episode.py kids/episodes/big-feet.json             # voice what is missing, publish

For every clip: assets/kids/episodes/<id>/<clip>.mp4 (the Veo picture and its own soft sound, 960x540) and
<clip>.last.webp (its last frame: the picture the child acts in, and the one shown again after a rewind); and per
language <clip>.<lang>.mp3, the characters' lines for that clip. Every other line (questions, reactions) gets its
own <line>.<lang>.mp3. Times of every line (for the captions) go to assets/kids/episodes/<id>/media.json.

Voices are ElevenLabs, as for the stories (tools/kids/narrate.py): the voice of each role is named in the episode's
"voices" block and looked up in kids/voices.json. Generated speech is kept in tools/kids/.eleven-kids/ (not
committed) by a hash of model, voice and text, so running again costs nothing unless a line changed. Before
generating, the subscription is read and nothing is made unless the remaining credits cover it.

Keys come only from the environment (ELEVENLABS_API_KEY) and are never written anywhere."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "kids"))
sys.path.insert(0, str(ROOT / "tools" / "video"))
import narrate as N  # noqa: E402  (narrator_module, ffmpeg, seconds, STATE)
import veo as V  # noqa: E402
import pruna as P  # noqa: E402

LEAD, GAP = 0.5, 0.35
VOICE = ["-ac", "1", "-ar", "24000", "-c:a", "libmp3lame", "-b:a", "40k"]
LANGS = ("en", "fa")


def voice_ids(ep):
    """role -> ElevenLabs voice id, per language, from the names in the episode and the ids in kids/voices.json."""
    known = json.loads((ROOT / "kids" / "voices.json").read_text(encoding="utf-8"))
    by_name = {}
    for lang in LANGS:
        for v in known[lang].values():
            by_name[v["name"]] = v["id"]
    out = {}
    for lang in LANGS:
        out[lang] = {}
        for role, name in ep["voices"][lang].items():
            if name not in by_name:
                raise SystemExit(f"voice {name} ({lang} {role}) is not in kids/voices.json")
            out[lang][role] = by_name[name]
    return known["model"], out


def every_line(ep):
    """(where, line) for every spoken line: ("c1", line) for clip lines, ("ask-why", line) for the others."""
    for c in ep["clips"]:
        for ln in c["lines"]:
            yield c["id"], ln
    for k, ln in ep["lines"].items():
        yield k, ln


def key_of(model, vid, text):
    return hashlib.sha1(json.dumps([model, vid, text], ensure_ascii=False).encode()).hexdigest()[:16]


def speak_all(ep, model, ids, dry):
    todo = []
    for _, ln in every_line(ep):
        for lang in LANGS:
            vid = ids[lang][ln["who"]]
            k = key_of(model, vid, ln[lang])
            if not (N.STATE / f"{k}.mp3").exists() and (vid, ln[lang]) not in [(t[0], t[1]) for t in todo]:
                todo.append((vid, ln[lang], k))
    need = sum(len(t[1]) for t in todo)
    print(f"lines to voice: {len(todo)} ({need} characters)")
    if dry or not todo:
        return
    en = N.narrator_module()
    en.MODEL = model
    sub = en.subscription()
    print(f"  credits: {sub['remaining']} remaining of {sub['limit']}")
    if sub["remaining"] < need * 1.1 + 200:
        raise SystemExit("  not enough credits left; nothing generated")
    N.STATE.mkdir(exist_ok=True)
    settings = {}
    for i, (vid, text, k) in enumerate(todo):
        settings.setdefault(vid, en.voice_settings(vid))
        audio, alignment, rid, cost = en.speak_timed(text, vid, settings[vid], seed=7)
        (N.STATE / f"{k}.mp3").write_bytes(audio)
        (N.STATE / f"{k}.json").write_text(json.dumps({"alignment": alignment, "request_id": rid, "cost": cost}), encoding="utf-8")
        print(f"  {i + 1}/{len(todo)}: {text[:50]}… cost {cost}", flush=True)


def join(lines, model, ids, lang, out, tmp):
    """The lines one after another (lead silence, short gaps) as one web mp3; returns [(begin, end, text)]."""
    pieces, t, times = [], 0.0, []

    def silence(sec):
        p = tmp / f"sil-{sec:.2f}.wav"
        if not p.exists():
            N.ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{sec:.2f}", "-c:a", "pcm_s16le", str(p))
        return p
    pieces.append(silence(LEAD))
    t = LEAD
    for i, ln in enumerate(lines):
        if i:
            pieces.append(silence(GAP))
            t += GAP
        wav = tmp / f"{out.stem}-{i}.wav"
        N.ffmpeg("-i", str(N.STATE / f"{key_of(model, ids[lang][ln['who']], ln[lang])}.mp3"), "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(wav))
        d = N.seconds(wav)
        times.append({"b": round(t, 2), "e": round(t + d, 2), "who": ln["who"], "t": ln[lang]})
        pieces.append(wav)
        t += d
    pieces.append(silence(0.3))
    listing = tmp / f"{out.stem}.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in pieces), encoding="utf-8")
    N.ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), *VOICE, str(out))
    return times


def veo_raw(ep, c):
    png = V.frame_png(ep, c)
    if not png:
        return None
    k = V.key_of(ep["veo"]["model"], V.prompt_of(ep, c), ep["veo"].get("negative", ""), c.get("seconds", 8),
                 V.frame_bytes(png, ep["veo"].get("aspect", "16:9")))
    raw = V.CACHE / f"{ep['id']}-{c['id']}-{k}.mp4"
    return raw if raw.exists() else None


def raw_clip(ep, c):
    """(the clip's video file, the file whose sound to use): from the engine the episode (or the clip) names."""
    video = {**ep.get("video", {"engine": "veo"}), **c.get("video", {})}
    vr = veo_raw(ep, c)
    if video["engine"] == "pruna":
        if not V.frame_png(ep, c):
            return None, None
        pr = P.cache_path(ep, c, video.get("model", "p-video-2"), video.get("hold", True))
        return (pr if pr.exists() else None), vr
    return vr, vr


SFX_API = "https://api.elevenlabs.io/v1/sound-generation"


def sound_effect(ep, c, seconds):
    """The clip's own sound (birds, knocks, bells, footsteps) made from its "sound" description with ElevenLabs sound
    effects, kept in tools/video/.cache/ by a hash of the description and length; None when the clip has none."""
    text = c.get("sound")
    if not text:
        return None
    seconds = round(min(22.0, max(1.0, seconds)), 1)
    h = hashlib.sha1(json.dumps([text, seconds, ep.get("sound_style", "")], ensure_ascii=False).encode()).hexdigest()[:16]
    out = V.CACHE / f"{ep['id']}-{c['id']}-sfx-{h}.mp3"
    if out.exists():
        return out
    import os
    import requests
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is not set")
    prompt = f"{text}. {ep.get('sound_style', '')}".strip()
    r = requests.post(SFX_API, headers={"xi-api-key": key, "Content-Type": "application/json"}, timeout=180,
                      json={"text": prompt, "duration_seconds": seconds, "prompt_influence": 0.55})
    if r.status_code != 200:
        raise SystemExit(f"sound effect refused for {c['id']} ({r.status_code}): {r.text[:300]}")
    out.write_bytes(r.content)
    print(f"  {c['id']}: sound made ({r.headers.get('character-cost', '?')} credits)", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ep = json.loads((ROOT / args.episode).read_text(encoding="utf-8"))
    model, ids = voice_ids(ep)
    speak_all(ep, model, ids, args.dry_run)
    if args.dry_run:
        return
    out = ROOT / "assets" / "kids" / "episodes" / ep["id"]
    out.mkdir(parents=True, exist_ok=True)
    media = {"v": 1, "clips": {}, "lines": {},
             "made": {"video": ep.get("video", {}).get("model", ep["veo"]["model"]), "voices": f"ElevenLabs {model}",
                      "voice_names": ep["voices"]}}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for c in ep["clips"]:
            raw, sound = raw_clip(ep, c)
            if not raw:
                print(f"{c['id']}: no clip yet (tools/video/pruna.py or veo.py), skipped")
                continue
            mp4 = out / f"{c['id']}.mp4"
            # the picture from the chosen clip; the soft film sound from the Veo clip when there is one (Pruna's is
            # near silent), otherwise silence
            fx = sound_effect(ep, c, N.seconds(raw))
            if fx:
                sound = fx
            snd = ["-i", str(sound)] if sound else ["-f", "lavfi", "-t", "8", "-i", "anullsrc=r=44100:cl=mono"]
            N.ffmpeg("-i", str(raw), *snd, "-map", "0:v", "-map", "1:a", "-shortest",
                     "-vf", "scale=960:540:flags=lanczos,setsar=1", "-c:v", "libx264", "-preset", "slow", "-crf", "27",
                     "-pix_fmt", "yuv420p", "-profile:v", "main", "-movflags", "+faststart",
                     "-af", "loudnorm=I=-29:TP=-5", "-c:a", "aac", "-b:a", "48k", "-ac", "1", str(mp4))
            N.ffmpeg("-sseof", "-0.1", "-i", str(raw), "-frames:v", "1", "-vf", "scale=960:540:flags=lanczos", "-q:v", "80", str(out / f"{c['id']}.last.webp"))
            N.ffmpeg("-i", str(raw), "-frames:v", "1", "-vf", "scale=960:540:flags=lanczos", "-q:v", "75", str(out / f"{c['id']}.first.webp"))
            entry = {"dur": round(N.seconds(mp4), 2), "voice": {}}
            for lang in LANGS:
                entry["voice"][lang] = {"lines": join(c["lines"], model, ids, lang, out / f"{c['id']}.{lang}.mp3", tmp)}
                entry["voice"][lang]["dur"] = round(N.seconds(out / f"{c['id']}.{lang}.mp3"), 2)
            media["clips"][c["id"]] = entry
            print(f"{c['id']}: {mp4.stat().st_size // 1024} KB video, voices {entry['voice']['en']['dur']} / {entry['voice']['fa']['dur']} s")
        for k, ln in ep["lines"].items():
            media["lines"][k] = {}
            for lang in LANGS:
                times = join([ln], model, ids, lang, out / f"{k}.{lang}.mp3", tmp)
                media["lines"][k][lang] = {"dur": round(N.seconds(out / f"{k}.{lang}.mp3"), 2), "b": times[0]["b"], "e": times[0]["e"]}
    (out / "media.json").write_text(json.dumps(media, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in out.iterdir())
    print(f"published {out.relative_to(ROOT)}: {size / 1e6:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
