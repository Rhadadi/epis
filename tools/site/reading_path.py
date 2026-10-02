"""Reading-path catalogue: curated routes resolved against the real chapter headings."""
import json
import math
import re


def build_catalogue(root, chapters, md, clean, deep):
    config = json.loads((root / 'tools/site/reading-path-routes.json').read_text())
    sections = {}
    for n, ch in chapters.items():
        if n > 16:
            continue
        text = clean(ch.text)
        _, heads = md.render(text, lambda href: href)
        headings = [h for h in heads if h[0] == 2]
        chunks = re.split(r'^## .+\n', text, flags=re.M)[1:]
        if len(chunks) != len(headings):
            raise ValueError(f'Reading-path section mismatch: {ch.slug}')
        for (_, slug, title, _), chunk in zip(headings, chunks):
            sid = f'{n:02d}/{slug}'
            entry = {
                'id': sid, 'title': title, 'chapter': n, 'chapterTitle': ch.title,
                'url': f'guide/{ch.href}#{slug}',
                'minutes': max(1, math.ceil(len(re.findall(r"[A-Za-z][A-Za-z’'-]*", chunk)) / 230)),
            }
            pg = deep.get(ch.slug, {}).get(slug)
            if pg and pg['meta'].get('status') == 'published':
                entry['deep'] = {
                    'url': f'deeper/{ch.slug}/{slug}.html',
                    'minutes': max(1, math.ceil(len(re.findall(r"[A-Za-z][A-Za-z’'-]*", pg['text'])) / 230)),
                }
            sections[sid] = entry
    for topic in config['topics']:
        for focus in topic['focuses']:
            for step in focus['steps']:
                if step['id'] not in sections:
                    raise ValueError(f'Unknown reading-path section: {step["id"]}')
    for sid, prereqs in config['prerequisites'].items():
        if sid not in sections or any(p['id'] not in sections for p in prereqs):
            raise ValueError(f'Unknown reading-path prerequisite: {sid}')
    config.update(version=1, sections=sections)
    out = root / 'assets/data/reading-path.json'
    out.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    bank = [{k: t[k] for k in ('id', 'label', 'question')} | {
        'focuses': [f['label'] for f in t['focuses']]
    } for t in config['topics']]
    (root / 'tools/free-chat-worker/interview-bank.js').write_text(
        '// Generated from tools/site/reading-path-routes.json by the site build.\n'
        + 'export default ' + json.dumps(bank, ensure_ascii=False, indent=2) + ';\n')


def page_body():
    return '''<main id="main" class="rp-main">
      <header class="rp-intro wrap"><span class="kicker">Your question. Your reading path.</span>
        <h1>Where do you want<br>to go from here?</h1>
        <p class="rp-lede">Start with something you want to understand. We’ll find the sections that help,
          put them in a useful order, and explain why they belong.</p>
        <div class="rp-meta"><span>Three ways to study</span><span>A few questions</span><span>No sign-in needed</span></div>
      </header>
      <section class="wrap rp-layout" aria-label="Build your reading path">
        <div class="rp-workspace"><div id="reading-path" aria-busy="true"><p>Loading the reading guide…</p></div>
          <noscript><p>This questionnaire needs JavaScript. You can still use the
            <a href="../guide/">suggested paths in the guide</a> or browse its contents.</p></noscript>
          <p id="rp-notice" class="rp-notice" role="status" aria-live="polite"></p>
        </div>
        <aside class="rp-aside"><span class="kicker">A guide, with room to change</span>
          <h2>Start where you are.</h2><p>You can skip optional questions, change your answers, or switch between a quick answer,
            guided learning and deep study. Your first path fits the time you have.</p>
          <h3>Your background is yours.</h3><p>Tell us what you already understand and what matters to you.
            We don’t use your degree, gender or sexuality to guess your ability or beliefs.</p>
          <h3>Your own pace.</h3><p>Reading times are estimates at 230 words a minute. Reflection, exercises and
            listening can take longer. Mark a section done when you are ready.</p>
          <p class="rp-small">Answers and progress stay in this browser. AI is optional: when you turn it on,
            your question and interview answers go to the configured AI service. Avoid sharing private details.</p>
          <a href="../guide/">Browse all sixteen chapters →</a>
        </aside>
      </section>
    </main>'''
