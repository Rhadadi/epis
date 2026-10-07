# How Do You Know? / «از کجا می‌دانی؟» — writing and production guide

The children's section of *Mastering Epistemology*, for ages 7–14, in English and Persian. Every unit is written
twice: **Explorers** (ages 7–10) and **Investigators** (ages 11–14), and each level is written in both
languages. Read this before writing or changing anything in `kids/`.

## The four detective questions (the spine of every unit)

| | English | فارسی |
|---|---|---|
| 1 | What exactly is being said? | دقیقاً چه گفته می‌شود؟ |
| 2 | How do they know? | از کجا می‌داند؟ |
| 3 | What else could explain it? | چه توضیحِ دیگری ممکن است؟ |
| 4 | How sure should I be? | چقدر باید مطمئن باشم؟ |

Explorers use three: *What? How do you know? How sure?* / *چه؟ از کجا می‌دانی؟ چقدر مطمئنی؟*

## The two levels

| | Explorers (7–10) | Investigators (11–14) |
|---|---|---|
| Reading level (English) | Flesch–Kincaid grade ≤ 4 | Flesch–Kincaid grade ≤ 7 |
| Sentences | about 10 words; Persian ≤ 12 words on average | about 15 words; Persian ≤ 18 on average |
| Length | 600–900 words | 1,200–1,800 words |
| New words | 3–4, each with a picture card | 6–8 real terms |
| Voice | warm, playful, read aloud | direct, curious, a little challenging |

`tools/kids/check.py` measures these.

## Files

```
kids/units.json                       the 16 units in 4 quests, with status (planned / draft / published)
kids/src/<unit>/unit.json             story id, pictures (shots) with English and Persian alt text, adult links
kids/src/<unit>/story.<lang>.md       the story, shared by both levels: one paragraph per line;
                                      "@role: text" is spoken in that role's voice; "@shot s01" starts a picture
kids/src/<unit>/explorers.<lang>.md   the Explorers lesson (ages 7–10)
kids/src/<unit>/investigators.<lang>.md  the Investigators lesson (ages 11–14)
kids/src/<unit>/grownups.<lang>.md    notes for parents and teachers
kids/games/<id>.json                  games and quizzes: English at the top level, Persian under "fa";
                                      cards and questions may carry "levels"
kids/words.json, stories.json, books.json, cast.json, voices.json, grownups.<lang>.md
tools/kids/                           kidslib.py, site_kids.py (pages), check.py, narrate.py
assets/kids/                          kids.css, kids.js, player.js, games/*.js, audio/, sync/, art/
```

A draft unit is built only with `EPIS_KIDS_DRAFTS=1`. Narrate a story with
`python3 tools/kids/narrate.py <unit> --dry-run`, then without `--dry-run`.

## Lesson anatomy (blocks, in this order)

The story comes first on both level pages automatically. Ordinary Markdown may sit between the blocks.

```
::: think              2–3 open questions (no single right answer)
::: bigidea            one sentence
::: words              word ids from kids/words.json, separated by commas
::: tryit <game-id>    one or two sentences that introduce the game (a unit may have several)
::: check <quiz-id>    (empty) the quick check
::: talk               2 questions for the dinner table or the class circle
::: further            Investigators only: links to the grown-up guide
```

## Writing rules

- Story first, then the question, then the idea, then the word: "This is called *evidence*."
- Talk to the reader ("you"). Be kind and a little funny. Never shame a wrong answer: "Not quite — here's why."
- One idea per paragraph; at most three sentences per paragraph for Explorers.
- No death, violence or fear for Explorers. Folk tales are retold gently (the wolf runs away; nobody is eaten).
- Religion and politics stay neutral. Misinformation examples are harmless and invented.
- Every real fact (history, science) is checked; invented stories are labelled as made up.
- Classic stories are retold from the old originals (public domain). Never copy a modern translation or a modern
  illustrated edition. Each story has a record in `kids/stories.json`.
- Books recommended in the book club are listed in `kids/books.json` with a catalogue link; never copied.

## Persian

- Written fresh in plain, natural children's Persian — an adaptation, not a translation. Read every sentence
  aloud before shipping; if a child would not say it, rewrite it.
- Simple written Persian with natural dialogue; avoid heavy Arabic-derived words where a common Persian one
  exists.
- Examples may change to fit Iranian children's lives (bread from the bakery, Nowruz, football); activities,
  games and answers stay identical in both languages (same ids).
- Persian digits in prose; ی and ک (never ي or ك).

## The kids' word list (fixed translations)

| English | فارسی |
|---|---|
| know | دانستن |
| believe / belief | باور کردن / باور |
| guess | حدس |
| hope | امید / امیدوار بودن |
| evidence | نشانه، مدرک |
| reason | دلیل |
| clue | سرنخ |
| fact | واقعیت |
| opinion | نظر |
| taste | سلیقه |
| thinking trap | تلهٔ فکری |
| fair test | آزمایشِ منصفانه |
| chance | احتمال |
| sure / confident | مطمئن |
| check | وارسی کردن، امتحان کردن |
| explanation | توضیح |

## The cast

- **Ava** (آوا), 9: curious, asks "How do you know?" — the Explorers' guide.
- **Nima** (نیما), 6: her little brother, the "why? why? why?" kid.
- **Kian** (کیان), 12: their neighbour; quick, confident, often too fast — learns the most. The Investigators' guide.
- **Grandma Mehri** (مادربزرگ مهری): patient; asks the best questions; tells the old stories.
- **Hudhud the hoopoe** (هدهد): the guide bird from Attar's *Conference of the Birds*; answers questions with
  questions. (Not an owl: in Iran the owl is an unlucky bird.)
- Animal friends step out of the fables: the goat kids Shangul and Mangul, the fox (sour grapes), the hare who
  tricked the lion, Rumi's parrot.

## Pictures

AI-generated (the service is chosen before the first pictures are made), with one style block and the
approved character sheet as a reference for every scene. No text inside pictures (all words stay in HTML so
both languages share one picture). Nothing frightening for Explorers. Every picture is reviewed by a person and
has English and Persian alt text. Until a picture exists, the page shows a drawn placeholder panel.

## Sound

Narration by ElevenLabs (`tools/kids/narrate.py`, key from `ELEVENLABS_API_KEY`), keeping word-level timings for
read-along highlighting. Voices: narrator, Ava, Kian, Grandma Mehri, Hudhud (chosen once, recorded in
`kids/voices.json`).
