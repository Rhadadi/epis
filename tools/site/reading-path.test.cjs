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
