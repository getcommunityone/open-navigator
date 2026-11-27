// Home link check (#1341): the way home is obvious at 360, 412 and 1440. The C1 mark is a link named "Open Navigator home"
// with a visible label (phones: "Home"; desktop: the wordmark), the menu's first item is Home, a story's close says where it goes,
// and the mark keeps the place scope. No header wrap/overflow, and the place toggle fits.
//
//   node e2e/home-link.check.mjs [--base http://localhost:5173] [--shots <dir>]
import { chromium } from 'playwright'

const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? process.argv[i + 1] : d }
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', null)
let failures = 0
const ok = (c, m) => { console.log(`  ${c ? 'ok  ' : 'FAIL'} ${m}`); if (!c) failures++ }
const browser = await chromium.launch()
const saved = { state: 'AL', city: 'Tuscaloosa' }

for (const [w, h] of [[360, 740], [412, 915], [1440, 900]]) {
  console.log(`\n${w}x${h}`)
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, reducedMotion: 'reduce' })
  const page = await ctx.newPage()
  await page.addInitScript((loc) => localStorage.setItem('user_location', JSON.stringify(loc)), saved)
  await page.goto(`${base}/stories/data-centers?state=AL&city=Tuscaloosa`, { waitUntil: 'networkidle', timeout: 120_000 })
  const mark = page.locator('[data-testid="header-home-link"]')
  ok((await mark.getAttribute('aria-label')) === 'Open Navigator home', 'the mark is named "Open Navigator home"')
  const text = (await mark.evaluate((el) => el.innerText)).trim()
  ok(/Home|Open Navigator/.test(text), `and shows a visible label (${text.replace(/\n/g, ' / ')})`)
  const fit = await page.evaluate(() => {
    const hd = document.querySelector('.site-header'), inner = document.querySelector('.sh-inner')
    const t = document.querySelector('[data-testid="header-place-toggle"]')?.getBoundingClientRect()
    return { over: hd.scrollWidth > innerWidth + 1, tall: inner.getBoundingClientRect().height, tr: t ? t.right : null, tl: t ? t.left : null, vw: innerWidth }
  })
  ok(!fit.over, 'no horizontal overflow in the header')
  ok(fit.tall < 80, `header is one row (${Math.round(fit.tall)}px)`)
  ok(fit.tl !== null && fit.tl >= 0 && fit.tr <= fit.vw, 'the place toggle is fully on screen')
  const close = page.locator('[data-testid="story-close"]')
  await close.waitFor({ timeout: 20000 }).catch(() => {})
  if (await close.count()) {
    ok((await close.getAttribute('title')) === 'Close · back to home', 'the story close says "Close · back to home"')
    ok((await close.innerText()).includes('Close'), 'and shows a "Close" caption')
  }
  if (shots) await page.screenshot({ path: `${shots}/home-${w}-story.png`, clip: { x: 0, y: 0, width: w, height: 160 } })
  await mark.click()
  await page.waitForURL((u) => u.pathname === '/', { timeout: 8000 }).catch(() => {})
  const u = new URL(page.url())
  ok(u.pathname === '/' && u.searchParams.get('state') === 'AL' && u.searchParams.get('city') === 'Tuscaloosa', `the mark goes to / and keeps the place (${u.pathname}${u.search})`)
  if (shots) await page.screenshot({ path: `${shots}/home-${w}-home.png`, clip: { x: 0, y: 0, width: w, height: 160 } })
  if (w < 760) {
    await page.goto(`${base}/chat?state=AL&city=Tuscaloosa`, { waitUntil: 'networkidle', timeout: 120_000 })
    await page.getByRole('button', { name: 'Open menu' }).click()
    const first = page.locator('#site-mobile-menu nav button, [aria-label="Site menu"] nav button').first()
    ok((await first.innerText()).includes('Home'), 'the menu\'s first item is Home')
    if (shots) await page.screenshot({ path: `${shots}/home-${w}-menu.png` })
    await page.locator('[data-testid="menu-home"]').click()
    await page.waitForURL((x) => x.pathname === '/', { timeout: 8000 }).catch(() => {})
    const m = new URL(page.url())
    ok(m.pathname === '/' && m.searchParams.get('city') === 'Tuscaloosa', `Home in the menu keeps the place (${m.pathname}${m.search})`)
  }
  await ctx.close()
}
await browser.close()
console.log(failures ? `\n${failures} FAILED` : '\nall ok')
process.exit(failures ? 1 : 0)
