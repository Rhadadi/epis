import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// Import this Worker as ESM without adding a package.json to the static site.
const bank = await readFile(new URL('./interview-bank.js', import.meta.url), 'utf8');
const bankURL = 'data:text/javascript;base64,' + Buffer.from(bank).toString('base64');
const source = (await readFile(new URL('./worker.js', import.meta.url), 'utf8')).replace('"./interview-bank.js"', JSON.stringify(bankURL));
const { default: worker } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const allowed = 'https://epis.duckdns.org';
const request = (body, origin = allowed) => new Request('https://worker.example/reading-path', { method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' }, body: typeof body === 'string' ? body : JSON.stringify(body) });
const environment = response => ({ ALLOWED_ORIGINS: allowed, MODEL: 'test', AI: { run: async () => ({ response }) } });

test('validated interview strips extra model fields, returns JSON and never caches personal goals', async () => {
  const res = await worker.fetch(request({ goal: 'How do I judge a study?', mode: 'guided' }), environment(JSON.stringify({ topic: 'science', question: 'Do you want to assess a claim or explore scientific method?', url: 'bad' })));
  assert.equal(res.status, 200); assert.equal(res.headers.get('Access-Control-Allow-Origin'), allowed);
  assert.equal(res.headers.get('Cache-Control'), 'no-store');
  assert.deepEqual(await res.json(), { topic: 'science', question: 'Do you want to assess a claim or explore scientific method?' });
});

test('invalid inputs and disallowed origins never invoke AI', async () => {
  let calls = 0;
  const env = { ALLOWED_ORIGINS: allowed, AI: { run: async () => { calls++; } } };
  for (const body of ['not json', {}, { goal: 'x'.repeat(601), mode: 'quick' }, { goal: 'hello', mode: 'made-up' }]) {
    assert.equal((await worker.fetch(request(body), env)).status, 400);
  }
  assert.equal((await worker.fetch(request({ goal: 'x'.repeat(5000), mode: 'quick' }), env)).status, 413);
  assert.equal((await worker.fetch(request({ goal: 'hello', mode: 'quick' }, 'https://other.example'), env)).status, 403);
  assert.equal(calls, 0);
});

test('bad model output and quota exhaustion fail closed for frontend fallback', async () => {
  const body = { goal: 'How does Bayes work?', mode: 'deep' };
  for (const response of ['{"topic":"invented","question":"Which question matters?"}', '{"topic":"probability","question":"short"}', '{}']) {
    assert.equal((await worker.fetch(request(body), environment(response))).status, 502);
  }
  assert.equal((await worker.fetch(request(body), environment('not JSON'))).status, 503);
  const env = { ALLOWED_ORIGINS: allowed, AI: { run: async () => { throw new Error('quota'); } } };
  assert.equal((await worker.fetch(request(body), env)).status, 503);
});

test('preflight and existing chat streaming continue to work', async () => {
  const preflight = await worker.fetch(new Request('https://worker.example/reading-path', { method: 'OPTIONS', headers: { Origin: allowed } }), {});
  assert.equal(preflight.status, 200);
  const env = { ALLOWED_ORIGINS: allowed, AI: { run: async () => new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('data: {"response":"Hello"}\n\n')); controller.close(); } }) } };
  const res = await worker.fetch(new Request('https://worker.example/v1/chat/completions', { method: 'POST', headers: { Origin: allowed }, body: JSON.stringify({ messages: [{ role: 'user', content: 'Hi' }] }) }), env);
  assert.equal(res.status, 200); assert.match(await res.text(), /"content":"Hello"/);
});
