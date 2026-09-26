# Mastering Epistemology: Audio Edition

Every chapter of the guide is also available as a narrated audio track. Listen in the **[audio player](index.html)**, which has section markers, playback speed and resume. You can also open the MP3 files directly: each one carries chapter markers that podcast and audiobook apps can use.

> The narration is generated with a synthetic voice, the open-source [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) text-to-speech model. It was not read by a person.

<!-- TRACKS -->

---

## What changes when the guide is read aloud

A page is scanned by the eye, but a recording has to be followed in order. So the audio does not read the markdown word for word. Each chapter is first turned into a **narration script** ([`scripts/`](scripts/)), a plain-text version written for the ear:

- **A spoken roadmap replaces the "In this chapter" list.** Each chapter opens with its title and epigraphs and then says, in a few conversational sentences, where it is going. A short wrap-up and a look ahead to the next chapter replace the further-reading list. These parts are hand-written ([`tools/script_extras.py`](tools/script_extras.py)).
- **Links become plain words**, and sentences that only point elsewhere ("See Chapter 9") are dropped.
- **Citations are dropped from the flow of speech.** Parentheses such as *(Knowledge and Its Limits, 2000)* or *(Treatise 1.4.1)* would interrupt every other sentence. Names, titles and dates that are part of the story stay in.
- **Numbers, symbols and formulas are spoken the way a teacher would say them.** For example, "P(H | E)" becomes "the probability of H given E", "¬P ∨ Q" becomes "not P or Q", "1:99" becomes "one to ninety-nine", "1963" becomes "nineteen sixty-three" and "$1.10" becomes "one dollar and ten cents". The truth table in Chapter 3 and a few proofs are rewritten as short explanations.
- **Tables are read row by row** as sentences ("Foundationalism: yes. Coherentism: no."). The 42-row fallacy table in Chapter 15, which only repeats the chapter, is mentioned but not read.
- **Diagrams are left out.** The text around each diagram already says what it shows.
- **"Check your understanding" becomes a spoken quiz.** Each question is followed by five seconds of silence to think. Pause the recording if you want longer. The answer follows.

## How the reading is made less robotic

Monotone text-to-speech comes from three things: every sentence has the same shape, every pause is the same length, and one voice does everything. The narration works against all three.

1. **Several voices.** The narrator (Kokoro's `af_heart` voice) reads the main text. Quotations from philosophers and scientists are read in a second voice (`am_michael`), and the narrator then says who said it. In dialogues, each speaker has their own voice (`am_puck`, and the British `bf_emma`, which also gets British pronunciation). The argument between two friends in Chapter 1 and the social-media thread in Chapter 16 sound like people talking.
2. **Pacing and structure you can hear.** A soft two-note chime and a pause mark each new section. Headings are read a little more slowly. Example arguments and other set-off passages are read slightly slower, with space around them. List items and table rows have shorter gaps than paragraphs. Sentences and clauses get real pauses. A quieter single bell introduces each "critical-thinking lesson" box, and the narrator names the box: "Here's the critical-thinking lesson."
3. **Accurate pronunciation.** Words are converted to sounds by [misaki](https://github.com/hexgrad/misaki), the grapheme-to-phoneme system Kokoro was trained with. It gets part-of-speech tags from a bundled tagger, so that "a", "the", "read" and "live" come out right in context. A pronunciation lexicon ([`tools/lexicon.txt`](tools/lexicon.txt)) covers about 350 names and terms that dictionaries get wrong, including Gettier, Peirce, Nagel, Lakatos, Frege, Semmelweis, Theaetetus, *a priori*, *tu quoque*, Nyāya, *pramāṇa*, al-Ghazālī, Suhrawardī and Zhuangzi.
4. **Consistent sound.** Each track starts and ends with silence and is normalized to −18 LUFS, a comfortable speech level that makes chapters equally loud. Tracks are encoded as 40 kbps mono MP3 and tagged with title, album and track number. Each section is a chapter marker in the MP3.

The voice is synthetic, so expect occasional oddities: a stress on the wrong syllable, a flat reading of a joke, or a rare mispronounced name. The written chapter is always the reference.

## Files

| Path | What it is |
|---|---|
| `NN-*.mp3` | One track per chapter, with chapter markers |
| `index.html`, `tracks.js` | The player page and its track list with section times |
| `scripts/NN-*.txt` | The narration scripts: what is read, in which voice, with which pauses |
| `tools/make_script.py` | Converts a chapter's markdown into a narration script |
| `tools/script_extras.py` | Hand-written intros and outros, table readings, and spoken rewrites of formulas |
| `tools/lexicon.txt` | Pronunciations for names and foreign terms |
| `tools/narrate.py` | Renders scripts to MP3: pronunciation, voices, pacing, chimes, loudness, tags |

## Regenerating the audio

After editing a chapter, rebuild its script and audio. Rendered sentences are cached, so only changed lines are synthesized again.

```sh
cd guide/audio/tools
python3 make_script.py              # rebuild all scripts from the chapters
python3 narrate.py 05               # re-render chapter 5 (or --all --jobs 4)
python3 narrate.py --phonemes "Gettier's paper"   # check a pronunciation
```

Requirements: Python 3.10 or later with `onnxruntime`, `kokoro-onnx`, `misaki[en]`, `spacy`, `textblob`, `num2words`, `soundfile` and `numpy`, plus `espeak-ng` and `ffmpeg`. Put the Kokoro v1.0 ONNX model (`kokoro-v1.0.onnx`, or a quantized version) and the voice file (`voices-v1.0.bin`) in `tools/kokoro/`. Both are published with [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx/releases). These tracks were rendered with the full-precision (fp32) v1.0 model, which on a CPU is both faster and better-sounding than the 8-bit quantized one.

To fix a mispronunciation, add a line to `tools/lexicon.txt` and re-render the chapter. To change what is read, edit the chapter and run `make_script.py`, or add a rewrite to `script_extras.py`. Edits made by hand to a script are overwritten the next time `make_script.py` runs.

## Credits and licenses

- Voice model: [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad, Apache License 2.0.
- Grapheme-to-phoneme: [misaki](https://github.com/hexgrad/misaki), Apache License 2.0, with [espeak-ng](https://github.com/espeak-ng/espeak-ng) as a fallback for unknown words.
- Part-of-speech tagging: the Pattern tagger bundled with [TextBlob](https://github.com/sloria/TextBlob), MIT License.
- ONNX runtime wrapper: [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), MIT License.
