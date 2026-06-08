import { chromium } from 'playwright';

const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' });
const page = await browser.newPage({ viewport: { width: 1280, height: 1800 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 60000 });

// Activate the "Money Moves" story lens (which contains FollowTheMoney).
const moneyMoves = page.getByText(/^Money Moves$/).first();
if (await moneyMoves.count()) {
  await moneyMoves.click().catch(() => {});
  await page.waitForTimeout(1500);
}

// Scroll the Follow-the-money section into view and switch to the Grants tab.
const section = page.locator('#follow-the-money');
await section.scrollIntoViewIfNeeded({ timeout: 20000 }).catch(() => {});
await page.waitForTimeout(1000);
const grantsTab = section.getByRole('button', { name: /^Grants$/ });
if (await grantsTab.count()) {
  await grantsTab.first().click();
  await page.waitForTimeout(3000); // let the sankey re-lay-out
}
await section.scrollIntoViewIfNeeded().catch(() => {});

await section.screenshot({ path: '/tmp/ftm_grants.png' }).catch(async () => {
  await page.screenshot({ path: '/tmp/ftm_grants.png', fullPage: false });
});

// Report the rendered left-side org labels (the ones that were clipping).
const labels = await section.locator('svg text').allTextContents();
console.log('rendered svg labels:', JSON.stringify(labels.slice(0, 24)));
if (errors.length) console.log('page errors:', errors.slice(0, 5));
await browser.close();
