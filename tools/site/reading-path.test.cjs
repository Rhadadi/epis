const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const core = require('../../assets/reading-path-core.js');
const data = JSON.parse(fs.readFileSync(new URL('../../assets/data/reading-path.json', 'file://' + __filename)));

test('every focus, mode and time budget keeps prerequisites before their dependent sections', () => {
  for (const topic of data.topics) for (const focus of topic.focuses) {
    for (const mode of Object.keys(core.modes)) for (const minutes of [15,30,60,120,240]) {
      const plan = core.recommend(data, { topic: topic.id, focus: focus.id, mode, minutes });
      assert.ok(plan.minutes <= minutes, `${topic.id}/${focus.id}/${mode}/${minutes}`);
      assert.ok(plan.items.length <= core.modes[mode].limit);
      assert.equal(new Set(plan.items.map(s => s.id)).size, plan.items.length);
      const seen = new Set();
      for (const s of plan.items) {
        const base = s.id.replace(/:deep$/, '');
        if (s.kind === 'deep') assert.ok(seen.has(base), `Deep page precedes section: ${s.id}`);
        else for (const prereq of data.prerequisites[base] || []) assert.ok(seen.has(prereq.id), `Missing prerequisite for ${s.id}`);
        seen.add(s.id);
        const [url, anchor] = s.url.split('#');
        assert.ok(fs.existsSync(url));
        if (anchor) assert.ok(fs.readFileSync(url, 'utf8').includes(`id="${anchor}"`));
      }
    }
  }
});

test('Bayes gets probability foundations unless the visitor explicitly knows them', () => {
  const input = { topic: 'probability', focus: 'update', mode: 'guided', minutes: 60 };
  const novice = core.recommend(data, input);
  assert.equal(novice.items[0].id, '09/probability-the-basics');
  const familiar = core.recommend(data, { ...input, known: ['probability'] });
  assert.equal(familiar.items[0].id, '09/bayes-theorem');
  assert.ok(!familiar.items.some(s => s.id === '09/probability-the-basics'));
});

test('deep pages respect the time budget and require their chapter section', () => {
  const input = { topic: 'knowledge', focus: 'know', mode: 'deep', minutes: 240 };
  const plan = core.recommend(data, input);
  assert.ok(plan.items.some(s => s.kind === 'deep'));
  const alreadyRead = core.recommend(data, { ...input, done: ['05/the-gettier-problem', '05/the-tripartite-analysis'] });
  assert.ok(alreadyRead.items.some(s => s.id === '05/the-gettier-problem:deep'));
  assert.ok(!alreadyRead.items.some(s => s.id === '05/the-gettier-problem'));
});

test('only explicit familiarity or a user skip removes required foundations', () => {
  const plan = core.recommend(data, { topic: 'probability', focus: 'update', minutes: 60, excluded: ['09/probability-the-basics'] });
  assert.equal(plan.items[0].id, '09/bayes-theorem');
  const completed = core.recommend(data, { topic: 'probability', focus: 'update', minutes: 60, done: ['09/probability-the-basics'] });
  assert.equal(completed.items[0].id, '09/bayes-theorem');
});

test('unknown queries ask for a topic and short keywords match whole words', () => {
  assert.equal(core.suggest(data, 'How do I repair a bicycle?'), '');
  assert.notEqual(core.suggest(data, 'faith'), 'news'); // “ai” must not match “faith”.
  assert.equal(core.suggest(data, 'How does Bayes update probability?'), 'probability');
});

test('malformed persisted answers and unreviewed AI topic IDs are rejected', () => {
  const normalized = core.normalize(data, { mode: '__proto__', topic: 'made-up', minutes: Infinity, known: ['graduate-degree'], done: ['https://bad.example/'], goal: 'a'.repeat(900) });
  assert.equal(normalized.mode, 'guided'); assert.equal(normalized.topic, '');
  assert.equal(normalized.minutes, 30); assert.deepEqual(normalized.known, []); assert.deepEqual(normalized.done, []);
  assert.equal(normalized.goal.length, 600);
  assert.equal(core.validInterview(data, { topic: 'made-up', question: 'Which question matters?' }), null);
  assert.equal(core.validInterview(data, { topic: 'probability', question: 'x'.repeat(301) }), null);
  assert.equal(core.validInterview(data, { topic: 'probability', question: 'Which evidence would change your confidence?', url: 'https://bad.example/' }).url, undefined);
});

test('education can add an introduction; a graduate degree never proves prerequisite mastery', () => {
  const input = { topic: 'knowledge', focus: 'know', mode: 'guided', minutes: 60 };
  const school = core.recommend(data, { ...input, education: 'secondary' });
  assert.equal(school.items[0].id, '01/the-basic-vocabulary');
  const familiar = core.recommend(data, { ...input, education: 'secondary', known: ['vocabulary'] });
  assert.ok(!familiar.items.some(s => s.id === '01/the-basic-vocabulary'));
  const graduate = core.recommend(data, { topic: 'probability', focus: 'update', education: 'graduate', studies: 'quantitative', minutes: 60 });
  assert.equal(graduate.items[0].id, '09/probability-the-basics');
  assert.deepEqual(graduate.profile.known, []);
});

test('related studies add a connecting section, with a reason and within the budget', () => {
  const plan = core.recommend(data, { topic: 'knowledge', focus: 'know', education: 'graduate', studies: 'quantitative', minutes: 30 });
  assert.equal(plan.items[0].id, '01/belief-credence-and-acceptance');
  assert.match(plan.items[0].why, /quantitative studies/);
  assert.ok(plan.minutes <= 30);
});

test('Persian topics, reasons and all recommended chapter links are localized', () => {
  const fa = JSON.parse(fs.readFileSync('assets/data/reading-path-fa.json'));
  assert.equal(core.suggest(fa, 'چطور احتمال و قضیهٔ بیز را بفهمم؟'), 'probability');
  assert.equal(core.suggest(fa, 'چطور به هوش مصنوعي اعتماد كنم؟'), 'news');
  for (const topic of fa.topics) for (const focus of topic.focuses) {
    for (const mode of Object.keys(core.modes)) for (const minutes of [15,30,60,120,240]) for (const background of [{}, {education:'secondary'}, {education:'graduate',studies:'quantitative'}]) {
      const plan = core.recommend(fa, { topic: topic.id, focus: focus.id, mode, minutes, ...background });
      assert.ok(plan.minutes <= minutes);
      const seen = new Set();
      for (const s of plan.items) {
        assert.match(s.title, /[آ-ی]/); assert.match(s.why, /[آ-ی]/);
        if (s.kind === 'deep') {
          assert.ok(seen.has(s.id.replace(/:deep$/, '')));
          assert.equal(s.language, s.url.startsWith('fa/deeper/') ? 'fa' : 'en');
          assert.ok(s.url.startsWith('fa/deeper/') || s.url.startsWith('deeper/'));
        }
        else { assert.ok(s.url.startsWith('fa/guide/')); for (const p of fa.prerequisites[s.id] || []) assert.ok(seen.has(p.id)); }
        seen.add(s.id);
        const [url, anchor] = s.url.split('#');
        assert.ok(fs.existsSync(url)); if (anchor) assert.ok(fs.readFileSync(url,'utf8').includes(`id="${anchor}"`));
      }
    }
  }
});

test('the next example changes with the answer and related studies', () => {
  const profile = {topic:'arguments',focus:'evaluate',mode:'guided'};
  assert.equal(core.nextQuestion(data,profile).id,'logic-rain');
  assert.equal(core.nextQuestion(data,{...profile,studies:'philosophy'}).id,'logic-birds');
  assert.equal(core.nextQuestion(data,{...profile,diagnosticAnswers:[{question:'logic-rain',answer:'1'}]}).id,'logic-cards');
  assert.equal(core.nextQuestion(data,{...profile,diagnosticAnswers:[{question:'logic-rain',answer:'0'}]}).id,'logic-birds');
  assert.equal(core.nextQuestion(data,{...profile,diagnosticAnswers:[{question:'logic-rain',answer:'0'},{question:'logic-birds',answer:'0'}]}).dimension,'vocabulary');
});

test('demonstrated understanding changes the route; one guessed answer cannot skip foundations', () => {
  const profile = {topic:'arguments',focus:'evaluate',minutes:60,mode:'guided',diagnosticAnswers:[{question:'logic-rain',answer:'1'}]};
  assert.deepEqual(core.normalize(data,profile).known,[]);
  assert.equal(core.recommend(data,profile).items[0].id,'03/what-an-argument-is-and-is-not');
  profile.diagnosticAnswers.push({question:'logic-cards',answer:'1'});
  assert.deepEqual(core.normalize(data,profile).known,['logic']);
  const ready=core.recommend(data,profile);
  assert.equal(ready.items[0].id,'03/reconstructing-real-arguments');
  assert.ok(!ready.items.some(s=>s.id==='03/validity-and-soundness'));
});

test('not-sure answers and mixed answers keep foundations with honest reasons', () => {
  const profile={topic:'probability',focus:'update',minutes:60,diagnosticAnswers:[{question:'probability-coin',answer:'unsure',confidence:'sure'}]};
  const plan=core.recommend(data,profile);
  assert.deepEqual(plan.profile.known,[]);
  assert.equal(plan.assessment.answers[0].confidence,'tentative');
  assert.match(plan.assessment.reviews[0].why,/not sure/);
  assert.equal(plan.items[0].id,'09/probability-the-basics');
});

test('duplicates, forged options and truncated free text cannot inflate diagnostic results', () => {
  const report=core.assess(data,[{question:'logic-rain',answer:'1',reason:'x'.repeat(900)},{question:'logic-rain',answer:'1'},{question:'logic-cards',answer:'99'},{question:'fake',answer:'1'}]);
  assert.equal(report.answers.length,1); assert.equal(report.answers[0].reason.length,400); assert.deepEqual(report.familiar,[]);
});

test('adaptive interviews terminate, stay bilingual and preserve route constraints', () => {
  const fa=JSON.parse(fs.readFileSync('assets/data/reading-path-fa.json'));
  for(const topic of data.topics) for(const focus of topic.focuses) for(const mode of Object.keys(core.modes)) for(const strategy of ['correct','wrong','unsure']) {
    const profile={topic:topic.id,focus:focus.id,mode,minutes:60,diagnosticAnswers:[]};
    let q;
    while((q=core.nextQuestion(data,profile))) {
      assert.equal(core.nextQuestion(fa,profile).id,q.id);
      assert.ok(!profile.diagnosticAnswers.some(a=>a.question===q.id));
      profile.diagnosticAnswers.push({question:q.id,answer:strategy==='unsure'?'unsure':String(strategy==='correct'?q.correct:(q.correct+1)%q.choices.length)});
      assert.ok(profile.diagnosticAnswers.length<=6);
    }
    const plan=core.recommend(data,profile),seen=new Set();assert.ok(plan.minutes<=60);
    for(const s of plan.items) {
      const base=s.id.replace(/:deep$/,'');
      if(s.kind==='deep')assert.ok(seen.has(base));
      else for(const p of data.prerequisites[base]||[])assert.ok(seen.has(p.id)||plan.profile.known.includes(data.foundations[p.id]));
      seen.add(s.id);
    }
  }
});
