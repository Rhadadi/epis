/* NODE_PATH=/path/to/node_modules node tools/site/reading-path-fa.browser.cjs */
const assert = require('node:assert/strict');
const {chromium} = require('playwright-core');
const origin = process.env.READING_PATH_TEST_URL || 'http://127.0.0.1:8765';
(async () => {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  try {
    const context = await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
    const page = await context.newPage(), errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const forward = () => page.getByRole('button',{name:'ادامه ←',exact:true}).click();
    await page.goto(origin+'/fa/');
    const entry = page.getByRole('link',{name:'مسیر مطالعه‌ام را پیدا کن',exact:true});
    assert.match(await entry.getAttribute('href'),/fa\/reading-path\//);
    await entry.click(); await page.locator('#rp-goal').waitFor();
    assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
    await page.screenshot({path:'/tmp/reading-path-fa-start.png'});
    await page.locator('#rp-goal').fill('چه چیزی باور را به معرفت تبدیل می‌کند؟');
    await forward(); await page.locator('input[name="topic"][value="knowledge"]').check();
    await forward(); await forward();
    await page.locator('#rp-education').selectOption('secondary');
    await page.screenshot({path:'/tmp/reading-path-fa-background.png'});
    await forward(); await page.getByRole('button',{name:'رد کردن مثال‌ها · با مقدمات'}).click();
    await page.locator('input[name="minutes"][value="60"]').check();
    await page.getByRole('button',{name:'مسیر مطالعه‌ام را پیدا کن ←'}).click();
    assert.match(await page.locator('.rp-item').first().innerText(),/واژگان/);
    const first = page.locator('.rp-item h3 a').first();
    assert.match(await first.getAttribute('href'),/\/fa\/guide\//);
    assert.match(await page.locator('.rp-item').first().innerText(),/تحصیلات مدرسه‌ای/);
    await page.getByRole('button',{name:'علامت تکمیل',exact:true}).first().click();
    assert.equal(await page.getByRole('button',{name:'انجام شد ✓ · لغو'}).count(),1);
    await page.screenshot({path:'/tmp/reading-path-fa-plan.png'});
    await page.reload(); await page.locator('.rp-list').waitFor();
    assert.equal(await page.getByRole('button',{name:'انجام شد ✓ · لغو'}).count(),1);
    await page.locator('#lang').click(); await page.locator('.rp-list').waitFor();
    assert.match(page.url(),/\/reading-path\//); assert.ok(!page.url().includes('/fa/'));
    assert.equal(await page.getByRole('button',{name:'Done ✓ · undo'}).count(),1);
    assert.match(await page.locator('.rp-goal').innerText(),/معرفت/);
    await page.locator('#lang').click(); await page.locator('.rp-list').waitFor();
    assert.equal(await page.getByRole('button',{name:'انجام شد ✓ · لغو'}).count(),1);
    await page.locator('#rp-mode').selectOption('deep');
    const deep = page.locator('.rp-item').filter({hasText:'مطالعهٔ بیشتر'}).first();
    const deepHref = await deep.locator('h3 a').getAttribute('href');
    assert.match(deepHref,/\/deeper\//);
    if (deepHref.includes('/fa/deeper/')) {
      assert.ok(!(await deep.innerText()).includes(' · انگلیسی'));
      await deep.locator('h3 a').click();
      assert.equal(await page.locator('html').getAttribute('lang'),'fa');
      await page.locator('.deep-translation').waitFor();
      await page.goBack(); await page.locator('.rp-list').waitFor();
    } else {
      assert.match(await deep.innerText(),/انگلیسی/);
    }
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'RTL mobile overflow');
    await page.setViewportSize({width:1440,height:1000});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'RTL desktop overflow');
    await page.goto(origin+'/fa/guide/');
    await page.locator('#rp-home').getByRole('link',{name:'ادامهٔ مسیر مطالعهٔ شما ←'}).waitFor();
    assert.match(await page.locator('#rp-home a').getAttribute('href'),/\/fa\/reading-path\//);
    assert.equal(errors.length,0,errors.join('\n'));
    console.log('PASS: Persian navigation, RTL/mobile, educational introduction, localized links/reasons, saved progress, language switching and localized Deeper destinations.');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
