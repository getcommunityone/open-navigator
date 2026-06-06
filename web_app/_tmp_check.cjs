const { chromium } = require('playwright');
(async () => {
  const url = 'http://localhost:5173/decisions/c84c8b0d2c304daa1c4be3c73e15e1b5';
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [], reqs = [];
  page.on('console', m => { if (m.type()==='error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR: '+e.message));
  page.on('response', r => { if (r.url().includes('/api/decision')) reqs.push(`${r.status()} ${r.url().split('/').pop()}`); });
  try { await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 }); } catch(e){ errors.push('GOTO:'+e.message); }
  try { await page.getByText('Where they disagreed', { exact: false }).first().waitFor({ timeout: 15000 }); } catch(e){ errors.push('WAIT:'+e.message); }
  const has = async (t) => (await page.getByText(t, { exact: false }).count()) > 0;
  console.log('API_REQS:', JSON.stringify(reqs));
  console.log('not_found_shown:', await has('Decision not found'));
  console.log('Where they disagreed:', await has('Where they disagreed'));
  console.log('prevailing/other side:', await has('The prevailing view'), await has('The other side'));
  console.log('worry/why/want:', await has('The worry'), await has("what's behind it?"), await has('What they want'));
  console.log('labels:', await has('Need for Study and Regulation'), await has('Developer Concerns on Deadlines'));
  console.log('ERRORS:', JSON.stringify(errors));
  await page.screenshot({ path: '/tmp/decision_page.png', fullPage: true });
  await browser.close();
})();
