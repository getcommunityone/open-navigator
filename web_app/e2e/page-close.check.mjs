// Page Close check (#1405). On every audited sub-page at 360x740, 412x915 and 1440x900 it asserts: Close is visible without
// scrolling, is at least 44px, sits below the site header and does not touch the place toggle, and the header does not overflow.
// Then it clicks Close twice: from a page reached in-app (it returns to the page before, the scope kept) and from a page opened
// directly (it goes home with ?state=&city=&topic= kept). Also checks the story's Close caption stays off the bar's bottom rule.
//
//   node e2e/page-close.check.mjs [--base http://localhost:5173] [--shots <dir>]
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? process.argv[i + 1] : d }
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', null)
if (shots) mkdirSync(shots, { recursive: true })
let failures = 0
const ok = (c, m) => { console.log(`  ${c ? 'ok  ' : 'FAIL'} ${m}`); if (!c) failures++ }
const Q = 'state=AL&city=Tuscaloosa&topic=fluoride'
const PAGES = [
  '/browse-topics/all', '/browse-topics', '/browse-causes', '/decisions/1', '/meetings/1', '/jurisdiction/1/meetings',
  '/jurisdictions', '/data-explorer/scorecard', '/search?q=fluoride', '/nonprofits', '/organizations/1', '/settings',
  '/explore', '/people', '/stories', '/bill/1', '/documents', '/profile',
]
const VIEWPORTS = [[360, 740, true], [412, 915, true], [1440, 900, false]]
const intersects = (a, b) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height

const browser = await chromium.launch()
for (const [w, h, mobile] of VIEWPORTS) {
  console.log(`\n${w}x${h}`)
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, isMobile: mobile, hasTouch: mobile, reducedMotion: 'reduce' })
  const page = await ctx.newPage()
  for (const p of PAGES) {
    const url = `${base}${p}${p.includes('?') ? '&' : '?'}${Q}`
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60_000 })
    const btn = page.locator('[data-testid="page-close"]').first()
    await btn.waitFor({ state: 'visible', timeout: 30_000 }).catch(() => {})
    const box = await btn.boundingBox()
    ok(!!box && box.width >= 44 && box.height >= 44 && box.y >= 0 && box.y + box.height <= h, `${p}: Close visible in the first screen, >= 44px`)
    if (box && p !== '/settings') { // Settings is a dialog over the whole screen, with its own Close
      const hdr = await page.evaluate(() => {
        const hd = document.querySelector('.site-header')
        const t = document.querySelector('[data-testid="header-place-toggle"]')?.getBoundingClientRect()
        return { bottom: hd.getBoundingClientRect().bottom, over: hd.scrollWidth > innerWidth + 1, t: t && { x: t.x, y: t.y, width: t.width, height: t.height } }
      })
      ok(box.y >= hdr.bottom - 1 && !hdr.over && !(hdr.t && intersects(box, hdr.t)), `${p}: below the site header, no overflow, clear of the place toggle`)
      ok(await btn.evaluate((e) => e.getAttribute('title').startsWith('Close · back to ')), `${p}: tooltip "Close · back to <where>"`)
    }
    if (shots && p === '/browse-topics/all') await page.screenshot({ path: `${shots}/${w}-browse-topics-all.png` })
    // Direct open: no history, so Close goes home with the scope and topic kept.
    await btn.click()
    await page.waitForURL((u) => u.pathname === '/', { timeout: 15_000 }).catch(() => {})
    const u = new URL(page.url())
    ok(u.pathname === '/' && u.searchParams.get('state') === 'AL' && u.searchParams.get('city') === 'Tuscaloosa' && u.searchParams.get('topic') === 'fluoride', `${p}: direct open, Close goes home with scope + topic kept`)
  }
  // In-app: /browse-topics -> its "all topics" link -> Close returns to /browse-topics with the scope kept; Escape does the same.
  await page.goto(`${base}/browse-topics?${Q}`, { waitUntil: 'domcontentloaded' })
  const link = page.locator('a[href^="/browse-topics/all"]').first()
  if (await link.count()) {
    await link.click()
    await page.locator('[data-testid="page-close"]').waitFor({ state: 'visible' })
    await page.locator('[data-testid="page-close"]').click()
    await page.waitForURL((u) => u.pathname === '/browse-topics', { timeout: 15_000 }).catch(() => {})
    const b = new URL(page.url())
    ok(b.pathname === '/browse-topics' && b.searchParams.get('state') === 'AL' && b.searchParams.get('city') === 'Tuscaloosa', 'in-app: Close returns to the page before, scope kept')
    await link.click()
    await page.locator('[data-testid="page-close"]').waitFor({ state: 'visible' })
    await page.waitForTimeout(800)
    await page.keyboard.press('Escape')
    await page.waitForURL((u) => u.pathname === '/browse-topics', { timeout: 15_000 }).catch(() => {})
    ok(new URL(page.url()).pathname === '/browse-topics', 'in-app: Escape closes too')
  } else ok(false, 'in-app: found the "all topics" link on /browse-topics')

  // The story's Close caption stays inside the bar, off its bottom rule.
  await page.goto(`${base}/stories/data-centers?${Q}`, { waitUntil: 'domcontentloaded', timeout: 60_000 })
  await page.locator('[data-testid="story-close"]').waitFor({ state: 'visible', timeout: 60_000 })
  await page.waitForTimeout(1500)
  const sc = await page.evaluate(() => {
    const bar = document.querySelector('.stance-top').getBoundingClientRect()
    const cap = document.querySelector('.story-close-label').getBoundingClientRect()
    const btn = document.querySelector('[data-testid="story-close"]').getBoundingClientRect()
    const dd = document.querySelector('.stance-top .stance-sentence')?.getBoundingClientRect()
    return { bar: bar.toJSON(), cap: cap.toJSON(), btn: btn.toJSON(), dd: dd && dd.toJSON() }
  })
  ok(sc.cap.bottom <= sc.bar.bottom - 2 && sc.cap.top >= sc.bar.top, 'story: the Close caption sits inside the bar, off the bottom rule')
  ok(sc.btn.width >= 44 && sc.btn.height >= 44 && sc.btn.bottom <= sc.bar.bottom - 2, 'story: the Close target is >= 44px and inside the bar')
  ok(!sc.dd || sc.dd.right <= sc.btn.left + 1, 'story: Close does not overlap the headline and its topic dropdown')
  if (shots) await page.screenshot({ path: `${shots}/${w}-story-close.png` })
  await ctx.close()
}
await browser.close()
console.log(failures ? `\n${failures} FAILED` : '\nall ok')
process.exit(failures ? 1 : 0)
