"""Reading-path catalogue: curated routes resolved against the real chapter headings."""
import json
import math
import re
from copy import deepcopy


def build_catalogue(root, chapters, md, clean, deep, lang='en', fa_heads=None):
    if lang == 'fa':
        return build_persian_catalogue(root, chapters, fa_heads or {})
    config = json.loads((root / 'tools/site/reading-path-routes.json').read_text())
    diagnostics = json.loads((root / 'tools/site/reading-path-diagnostics.json').read_text())
    config['diagnostics'] = diagnostics
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
    for step in list(config.get('educationIntroductions', {}).values()) + list(config.get('studyBridges', {}).values()):
        if step['id'] not in sections:
            raise ValueError(f'Unknown background reading-path section: {step["id"]}')
    for q in diagnostics['questions']:
        if q['review']['id'] not in sections or not 0 <= q['correct'] < len(q['choices']):
            raise ValueError(f'Invalid diagnostic question: {q["id"]}')
        if len(q['choices']) != len(q['fa']['choices']):
            raise ValueError(f'Persian diagnostic choices mismatch: {q["id"]}')
    config.update(version=1, sections=sections)
    out = root / 'assets/data/reading-path.json'
    out.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    fa = json.loads((root / 'tools/site/reading-path-fa.json').read_text())
    (root / 'assets/reading-path-i18n.js').write_text(
        '// Generated from tools/site/reading-path-fa.json.\nwindow.EpisReadingPathI18n = '
        + json.dumps(fa['ui'], ensure_ascii=False, indent=2) + ';\n')
    bank = [{k: t[k] for k in ('id', 'label', 'question')} | {
        'focuses': [f['label'] for f in t['focuses']]
    } for t in config['topics']]
    (root / 'tools/free-chat-worker/interview-bank.js').write_text(
        '// Generated from tools/site/reading-path-routes.json by the site build.\n'
        + 'export default ' + json.dumps(bank, ensure_ascii=False, indent=2) + ';\n')


def build_persian_catalogue(root, chapters, fa_heads):
    config = deepcopy(json.loads((root / 'assets/data/reading-path.json').read_text()))
    fa = json.loads((root / 'tools/site/reading-path-fa.json').read_text())
    for c in config['competencies']:
        c['label'], c['description'] = fa['competencies'][c['id']]
    for t in config['topics']:
        tr = fa['topics'][t['id']]
        t['label'], t['question'] = tr['label'], tr['question']
        t['keywords'] += tr['keywords']
        for f in t['focuses']:
            fr = tr['focuses'][f['id']]
            f['label'] = fr['label']
            if len(f['steps']) != len(fr['reasons']):
                raise ValueError(f'Persian reading-path reasons mismatch: {t["id"]}/{f["id"]}')
            for s, reason in zip(f['steps'], fr['reasons']):
                s['why'] = reason
    for sid, prereqs in config['prerequisites'].items():
        if len(prereqs) != len(fa['prerequisites'][sid]):
            raise ValueError(f'Persian prerequisite reasons mismatch: {sid}')
        for p, reason in zip(prereqs, fa['prerequisites'][sid]):
            p['why'] = reason
    for name in ('educationIntroductions', 'studyBridges'):
        for key, step in config[name].items():
            step['why'] = fa[name][key]
    for q in config['diagnostics']['questions']:
        translation = q.pop('fa')
        for key in ('title', 'prompt', 'choices', 'explanation'):
            q[key] = translation[key]
        q['review']['why'] = translation['reviewWhy']
    for sid, section in config['sections'].items():
        slug = sid.split('/', 1)[1]
        ch = chapters[section['chapter']]
        section['chapterTitle'] = ch.title
        section['title'] = fa_heads.get((ch.num, slug), section['title'])
        section['url'] = 'fa/' + section['url']
        # Estimate the actual Persian section, including its subheadings.
        html_path = root / 'fa' / 'guide' / ch.href
        content = html_path.read_text()
        match = re.search(r'<h2 id="' + re.escape(slug) + r'">(.*?)(?=<h2 id=|</article>)', content, re.S)
        if not match:
            raise ValueError(f'Persian reading-path anchor missing: {sid}')
        plain = re.sub(r'<[^>]*>', ' ', match[1])
        section['minutes'] = max(1, math.ceil(len(plain.split()) / 200))
        section['language'] = 'en' if ch.fallback else 'fa'
        if 'deep' in section:
            section['deep']['language'] = 'en'
    config['language'] = 'fa'
    config['deepReason'] = fa['deepReason']
    config['unsureReason'] = 'از توضیح این ایده آغاز کنید، چون در مثال گزینهٔ «مطمئن نیستم» را انتخاب کردید.'
    (root / 'assets/data/reading-path-fa.json').write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    (root / 'assets/reading-path-i18n.js').write_text(
        '// Generated from tools/site/reading-path-fa.json.\nwindow.EpisReadingPathI18n = '
        + json.dumps(fa['ui'], ensure_ascii=False, indent=2) + ';\n')


def page_body(lang='en'):
    if lang == 'fa':
        return '''<main id="main" class="rp-main">
          <header class="rp-intro wrap"><span class="kicker">پرسش شما، مسیر مطالعهٔ شما</span>
            <h1>از اینجا می‌خواهید<br>به کجا برسید؟</h1>
            <p class="rp-lede">از چیزی آغاز کنید که می‌خواهید بفهمید. بخش‌های مرتبط را پیدا می‌کنیم،
              به ترتیب مناسب می‌چینیم و توضیح می‌دهیم چرا خواندنشان به شما کمک می‌کند.</p>
            <div class="rp-meta"><span>سه شیوهٔ مطالعه</span><span>چند پرسش کوتاه</span><span>بدون نیاز به ورود</span></div>
          </header>
          <section class="wrap rp-layout" aria-label="ساختن مسیر مطالعه">
            <div class="rp-workspace"><div id="reading-path" aria-busy="true"><p>در حال آماده‌سازی راهنمای مطالعه…</p></div>
              <noscript><p>این پرسش‌نامه به جاوااسکریپت نیاز دارد. همچنان می‌توانید از
                <a href="../guide/">مسیرهای پیشنهادی و فهرست راهنما</a> استفاده کنید.</p></noscript>
              <p id="rp-notice" class="rp-notice" role="status" aria-live="polite"></p>
            </div>
            <aside class="rp-aside"><span class="kicker">راهنمایی که می‌توانید تغییرش دهید</span>
              <h2>از همان‌جا که هستید آغاز کنید.</h2>
              <p>می‌توانید پرسش‌های اختیاری را رد کنید، پاسخ‌هایتان را تغییر دهید یا میان پاسخ کوتاه،
                یادگیری هدایت‌شده و مطالعهٔ عمیق جابه‌جا شوید. مسیر نخست با زمان شما هماهنگ می‌شود.</p>
              <h3>از پاسخ‌هایتان یاد می‌گیریم.</h3><p>چند موقعیت روزمره دربارهٔ استدلال، شواهد، احتمال و معرفت را بررسی می‌کنید.
                پاسخ‌ها، پرسش بعدی و مقدمات پیشنهادی را تغییر می‌دهند. تحصیلات و موضوعاتی که خوانده‌اید نیز به انتخاب مثال‌ها کمک می‌کنند.</p>
              <h3>با سرعت خودتان</h3><p>زمان خواندن متن فارسی با سرعت تقریبی ۲۰۰ واژه در دقیقه برآورد می‌شود.
                فکر کردن، تمرین و شنیدن ممکن است زمان بیشتری بخواهد. هر بخش را وقتی آماده‌اید تکمیل‌شده علامت بزنید.</p>
              <p class="rp-small">صفحه‌های «مطالعهٔ بیشتر» فعلاً انگلیسی‌اند و با همین برچسب مشخص می‌شوند.</p>
              <p class="rp-small">پاسخ‌ها و پیشرفت در همین مرورگر می‌مانند. هوش مصنوعی اختیاری است؛ با فعال‌کردنش،
                پرسش و شیوهٔ مطالعه برای سرویس تعیین‌شده فرستاده می‌شوند. اطلاعات خصوصی وارد نکنید.</p>
              <a href="../guide/">دیدن همهٔ شانزده فصل ←</a>
            </aside>
          </section>
        </main>'''
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
          <h3>We learn from your answers.</h3><p>Try everyday situations about arguments, evidence, probability and knowledge.
            Your answers change the next example and the suggested foundations. Education and related studies also help choose the examples.</p>
          <h3>Your own pace.</h3><p>Reading times are estimates at 230 words a minute. Reflection, exercises and
            listening can take longer. Mark a section done when you are ready.</p>
          <p class="rp-small">Answers and progress stay in this browser. Optional AI receives your opening question,
            study mode and interface language. Your example answers and written reasoning stay here. Avoid sharing private details.</p>
          <a href="../guide/">Browse all sixteen chapters →</a>
        </aside>
      </section>
    </main>'''
