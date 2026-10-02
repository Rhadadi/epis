/* Tests actual adaptive interviews in both languages against a local HTTP server. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright-core');
const origin=process.env.READING_PATH_TEST_URL||'http://127.0.0.1:8765';
const bank=JSON.parse(fs.readFileSync('assets/data/reading-path.json')).diagnostics.questions;
(async()=>{
  const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  try{
    for(const fa of [false,true]){
      const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'}),page=await context.newPage(),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      const next=()=>page.getByRole('button',{name:fa?'ادامه ←':'Continue →',exact:true}).click();
      await page.goto(origin+(fa?'/fa':'')+'/reading-path/');await page.locator('#rp-goal').waitFor();
      await page.locator('#rp-goal').fill(fa?'چگونه استدلال‌ها را ارزیابی کنم؟':'How can I evaluate arguments?');
      await next();await page.locator('input[name="topic"][value="arguments"]').check();await next();await next();
      await page.locator('#rp-education').selectOption('graduate');await page.locator('#rp-studies').selectOption('philosophy');await next();
      const seen=[];
      while(await page.locator('[data-question]').count()){
        const id=await page.locator('[data-question]').getAttribute('data-question'),q=bank.find(q=>q.id===id);
        seen.push(id);
        const wrong=id==='evidence-coffee';
        await page.locator('input[name="diagnostic-answer"][value="'+(wrong?(q.correct+1)%q.choices.length:q.correct)+'"]').check();
        if(wrong){await page.locator('#rp-confidence').selectOption('sure');await page.locator('#rp-reason').fill('<img src=x onerror=alert(1)> '+ 'r'.repeat(250));}
        if(seen.length===1)await page.screenshot({path:fa?'/tmp/diagnostic-fa.png':'/tmp/diagnostic-en.png',fullPage:true});
        await next();
      }
      assert.deepEqual(seen,['logic-birds','logic-cards','evidence-coffee','evidence-reviews','knowledge-clock']);
      await page.locator('input[name="minutes"][value="60"]').check();
      await page.getByRole('button',{name:fa?'مسیر مطالعه‌ام را پیدا کن ←':'Find my reading path →'}).click();
      const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem('epis-reading-path')));
      assert.equal(stored.planProfile.diagnosticAnswers.length,5);
      assert.deepEqual(stored.planProfile.known,['logic']);
      const links=await page.locator('.rp-item h3 a').evaluateAll(nodes=>nodes.map(n=>n.href));
      assert.ok(links.some(s=>s.includes('#causation-and-causal-inference')));
      assert.ok(links.some(s=>s.includes('#reconstructing-real-arguments')));
      assert.ok(!links.some(s=>s.includes('#validity-and-soundness')));
      await page.getByText(fa?'مثال‌ها چه چیزی نشان دادند؟':'What your examples showed',{exact:true}).click();
      assert.equal(await page.locator('#reading-path img').count(),0);
      assert.match(await page.locator('#reading-path').innerText(),/onerror=alert/);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      assert.equal(errors.length,0,errors.join('\n'));
      console.log('PASS: '+(fa?'Persian':'English')+' adaptive difficulty, 5 examples, education context, diagnostic route, feedback and safe reasoning text.');
      await context.close();
    }
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
