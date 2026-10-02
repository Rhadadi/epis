# Adaptive reading guide

`/reading-path/` and `/fa/reading-path/` offer English and Persian interviews with three modes:
Quick answer, Guided learning and Deep study. It asks for a question, an explicit
topic and focus, optional education and subjects studied, adaptive everyday scenarios and a total reading-time budget. All
recommendations come from curated section routes; AI can suggest the topic and
phrase its next question, but cannot select arbitrary pages or invent citations.

Edit `reading-path-routes.json` to maintain topics, focuses, explanations and
prerequisites. The site build resolves their IDs against actual chapter headings,
fails on nonexistent sections, derives reading estimates at 230 words/minute,
and attaches published Deeper pages. It also generates the Worker question bank.
The curated routes are editorial suggestions, not a validated assessment of
learning ability. School-level education can add an introductory section when
no relevant study or familiarity is demonstrated. Related subjects can add a short
bridge connecting previous studies with the new topic. A university or postgraduate
degree never bypasses a prerequisite: that requires demonstrated familiarity,
completion or a user skip. The path explains why each introduction or bridge
was added. All background questions can be skipped.

## Adaptive scenarios

`reading-path-diagnostics.json` defines 21 bilingual everyday examples across
logic, probability, knowledge, belief/justification, evidence, testimony and
meanings/values. Each has an explanation and a real section to revisit. The
topic/focus chooses the first area; related study can choose a different entry
example. A correct response leads to a harder independent case. An incorrect
or unsure response leads to another case; two difficulties in the first area
shift the next pair toward a supporting concept. Quick/Guided/Deep modes ask
at most 3/5/6 examples, with a skip option.

Two correct responses in an area, with no conflicting response, make its
foundation optional. One answer cannot do that. Difficulties add targeted
reading with explanations. These are limited starting suggestions, not
psychometric scores or a validated measure of ability. Written reasoning and
confidence are optional; the text is saved for comparison with explanations,
not automatically graded by AI. Feedback is shown after the examples to avoid
coaching answers to the next case. Duplicate/invalid records cannot inflate
the result. The same question and option IDs preserve progress across languages.

Persian UI and route explanations live in `reading-path-fa.json`. The build
resolves Persian section titles and links from the existing chapter pages,
estimates Persian reading at 200 words/minute, and validates each anchor.
Deeper pages remain in English and are labelled accordingly. The same saved
answers and completion IDs work across both languages.

Visitors can change modes, revise answers/time, skip familiar sections, mark
steps done, and plan a subsequent stretch. Paths stay under `epis-reading-path`
in this browser's local storage; they are not included in Google Drive sync.
Forgetting a path clears its question, answers and completion history. It does
not delete the site's separate chapter progress or notes.

## Optional AI interview

The default works without AI, sign-in, a backend, or API keys. Foundation
questions appear only when they are relevant to the selected focus. To enable AI:

1. Build the site to generate `tools/free-chat-worker/interview-bank.js`.
2. Deploy the Worker following its README. Use a free plan if you want the quota
   to stop requests rather than incur charges; check current provider terms.
3. Set `readingPathBase` in `assets/ai-config.js` to the Worker base URL (no `/v1`).
4. Rebuild and publish the static site. Verify CORS from the actual site origin.

AI is opt-in per interview. Only the visitor's question, study mode and interface language are sent
to `/reading-path`; the endpoint returns a constrained topic ID and question.
The visitor confirms the topic before receiving the two curated focus options.
Malformed output, errors, quota exhaustion and a 12-second timeout fall back to
curated questions. User/AI text is rendered as text, never HTML. The existing
chat endpoint remains separate. No provider secret belongs in static assets.
No production AI endpoint is configured by this change.

## Verification

Run `node --test tools/site/reading-path.test.cjs
tools/free-chat-worker/reading-path.test.mjs` after the site build, then
`tools/deeper/check.sh`. The browser checks use Playwright against a local HTTP
server; see `tools/site/reading-path.browser.cjs`, `reading-path-fa.browser.cjs`
and `reading-path-diagnostic.browser.cjs` for commands. They cover small
screens, persistence, mode changes, progress, AI responses and fallback.
