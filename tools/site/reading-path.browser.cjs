/* Run with a local HTTP server at :8765:
   NODE_PATH=/path/to/playwright-core/node_modules node tools/site/reading-path.browser.cjs
   CHROMIUM_PATH can override /usr/bin/chromium. No real AI requests are made. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright-core');
const origin = process.env.READING_PATH_TEST_URL || 'http://127.0.0.1:8765';

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
    const page = await context.newPage(), errors = [];
    page.on('pageerror', e => errors.push(e.message));
    async function visit() { await page.goto(origin + '/reading-path/'); await page.getByRole('heading', { name: 'What would you like to understand?' }).waitFor(); }
    async function continueInterview() {
      await page.getByRole('button', { name: 'Continue →', exact: true }).click();
      await page.locator('input[name="topic"][value="probability"]').check();
      await page.getByRole('button', { name: 'Continue →', exact: true }).click();
      await page.getByRole('button', { name: 'Continue →', exact: true }).click();
      await page.getByRole('button', { name: 'Skip · include foundations' }).click();
      await page.locator('input[name="minutes"][value="30"]').check();
      await page.getByRole('button', { name: 'Find my reading path →' }).click();
    }
    await visit();
    assert.match(await page.locator('#reading-path').innerText(), /optional AI interview is not enabled/);
    await page.locator('#rp-goal').fill('How can Bayes change my confidence? <img src=x onerror=alert(1)>');
    await continueInterview();
    assert.match(await page.locator('.rp-item').first().innerText(), /Probability: the basics/);
    assert.equal(await page.locator('.rp-goal img').count(), 0);
    const count = await page.locator('.rp-item').count();
    await page.getByRole('button', { name: 'Mark done', exact: true }).first().click();
    assert.equal(await page.locator('.rp-item').count(), count); // Completion doesn't silently re-plan.
    await page.reload(); await page.locator('.rp-list').waitFor();
    assert.equal(await page.getByRole('button', { name: 'Done ✓ · undo' }).count(), 1);
    await page.goto(origin + '/');
    await page.locator('#rp-home').getByRole('link', { name: 'Continue your reading path →' }).waitFor();
    await page.locator('#rp-home a').click(); await page.locator('.rp-list').waitFor();
    await page.getByRole('button', { name: 'Change my time' }).click();
    await page.locator('input[name="minutes"][value="120"]').check();
    await page.getByRole('button', { name: 'Find my reading path →' }).click();
    await page.locator('#rp-mode').selectOption('deep');
    assert.match(await page.locator('.rp-list').innerText(), /Deeper study/i);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow');
    await page.screenshot({ path: '/tmp/reading-path-mobile.png', fullPage: true });
    await page.getByRole('button', { name: 'Forget this path' }).click();
    assert.equal(await page.locator('#rp-goal').inputValue(), '');

    // A focus without prerequisites omits the familiarity screen.
    await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    await page.locator('input[name="topic"][value="science"]').check();
    await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    assert.equal(await page.locator('#reading-path h2').innerText(), 'How much time for your first path?');
    assert.equal(await page.locator('.rp-step').textContent(), 'Question 4 of 4');
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    await page.getByRole('button', { name: 'Back', exact: true }).click();

    // Mock only the optional interview, never a paid API or live provider.
    await page.route('**/assets/ai-config.js*', route => route.fulfill({ contentType: 'text/javascript', body: 'window.EPIS_AI_CONFIG={readingPathBase:"https://interview.example"};' }));
    let calls = 0, invalid = false, fail = false;
    await page.route('https://interview.example/reading-path', async route => {
      calls++;
      const body = route.request().postDataJSON();
      assert.deepEqual(Object.keys(body).sort(), ['goal', 'mode']);
      if (fail) return route.fulfill({ status: 503, body: '{}' });
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ topic: invalid ? 'invented' : 'probability', question: 'Is it updating your confidence or interpreting a statistical result that matters here?' }) });
    });
    await visit();
    await page.locator('#rp-goal').fill('How does Bayes help me think?');
    await page.locator('input[name="ai"]').check();
    await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    await page.getByRole('button', { name: 'Use this suggestion' }).click();
    await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    assert.match(await page.locator('#reading-path h2').innerText(), /interpreting a statistical result/);
    assert.equal(calls, 1);
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    invalid = true;
    await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'AI is unavailable' }).waitFor();
    await page.locator('input[name="topic"][value="probability"]').check();
    await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    assert.equal(await page.locator('#reading-path h2').innerText(), 'What would you like to do with uncertainty?');
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    invalid = false; fail = true;
    await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'AI is unavailable' }).waitFor();
    assert.equal(errors.length, 0, errors.join('\n'));
    await page.setViewportSize({ width: 1440, height: 1000 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Desktop overflow');
    console.log('PASS: mobile questionnaire, valid links, persistence, completion, resume, modes, safe text, AI consent, AI success and fallback.');
    await context.close();

    // Check real service-worker caching separately from mocked AI requests.
    const offlineContext = await browser.newContext();
    const offlinePage = await offlineContext.newPage();
    await offlinePage.goto(origin + '/reading-path/');
    await offlinePage.locator('#rp-goal').waitFor();
    await offlinePage.evaluate(async () => { await navigator.serviceWorker.ready; if (!navigator.serviceWorker.controller) await new Promise(resolve => navigator.serviceWorker.addEventListener('controllerchange', resolve, {once:true})); });
    await offlinePage.reload(); await offlinePage.locator('#rp-goal').waitFor();
    // Wait for cache puts; no dependence on a download of the whole guide.
    await offlinePage.waitForFunction(async () => { const cache = await caches.open('epis-v1'); return !!(await cache.match(location.origin + '/assets/data/reading-path.json')); });
    await offlineContext.setOffline(true);
    await offlinePage.reload(); await offlinePage.locator('#rp-goal').waitFor();
    await offlinePage.locator('#rp-goal').fill('Bayes and probability');
    await offlinePage.getByRole('button', { name: 'Continue →', exact: true }).click();
    assert.equal(await offlinePage.locator('input[name="topic"][value="probability"]').isChecked(), true);
    console.log('PASS: questionnaire loads and adapts offline after being visited.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
