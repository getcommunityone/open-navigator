// Header place toggle check (#1301, #1331). At phone width the header always shows the place selector, outside the
// menu: with no town, "📍 Find your town" (opens the picker); with one, a [📍 town | National] toggle that switches both ways in one
// tap without retyping, on Home (?scope=national) and on a story (?state=&city=). A page with no place scope shows the
// town only.
//
//   node e2e/phone-place-header.check.mjs [--base http://localhost:5173] [--shots <dir>]
//
// The saved town is written to localStorage (as the picker does). Exits 1 on any failure.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', null)
let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}
const browser = await chromium.launch()
const ctx = await browser.newContext({ ...devices['iPhone 13'], reducedMotion: 'reduce' })
const page = await ctx.newPage()
const sel = '[data-testid="header-place-toggle"]'
const saved = { state: 'AL', city: 'Tuscaloosa' }
const shot = async (name) => shots && page.screenshot({ path: `${shots}/phone-place-${name}.png`, clip: { x: 0, y: 0, width: 390, height: 200 } })
const pressed = (side) => page.locator(`${sel} [data-side="${side}"]`).getAttribute('aria-pressed')
const settle = (side) => page.waitForSelector(`${sel} [data-side="${side}"][aria-pressed="true"]`, { timeout: 8000 }).catch(() => {})
const path = () => { const u = new URL(page.url()); return u.pathname + u.search }

console.log(`\niPhone 13 ${base}`)
await page.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 120_000 })
ok(await page.locator(sel).isVisible(), 'the toggle is in the header, outside the menu')
ok((await page.locator(`${sel} [data-side="place"]`).innerText()).includes('Find your town'), 'with no town: the left half reads "Find your town"')
await shot('1-find')
await page.locator(`${sel} [data-side="place"]`).click()
ok(await page.locator('[role="dialog"]').isVisible(), 'and it opens the place picker')
await page.keyboard.press('Escape')
// A saved town (the picker writes this same key).
await page.evaluate((loc) => localStorage.setItem('user_location', JSON.stringify(loc)), saved)
await page.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 120_000 })
const town = (await page.locator(`${sel} [data-side="place"]`).innerText()).replace('📍', '').replace('▾', '').trim()
ok(town.includes('Tuscaloosa') && (await pressed('place')) === 'true', `a saved town: it is on (${town})`)
await shot('2-town')
await page.locator(`${sel} [data-side="place"]`).click()
ok(await page.locator('[role="dialog"]').isVisible(), 'tapping the active town opens the picker')
await page.keyboard.press('Escape')
await page.locator(`${sel} [data-side="national"]`).click()
await page.waitForTimeout(1200)
ok(path().includes('scope=national') && (await pressed('national')) === 'true', `one tap to National on Home (${path()})`)
await shot('3-home-national')
await page.locator(`${sel} [data-side="place"]`).click()
await settle('place')
ok(!path().includes('scope=national') && (await pressed('place')) === 'true', `one tap back to ${town}, no retyping (${path()})`)
await page.goto(`${base}/stories/data-centers`, { waitUntil: 'networkidle', timeout: 120_000 })
ok((await pressed('national')) === 'true', 'a story with no place in the URL: National is on')
await page.locator(`${sel} [data-side="place"]`).click()
await page.waitForTimeout(1500)
ok(/[?&]state=[A-Z]{2}/.test(path()) && (await pressed('place')) === 'true', `one tap to the town on a story (${path()})`)
await shot('4-story-town')
await page.locator(`${sel} [data-side="national"]`).click()
await page.waitForTimeout(1500)
ok(!/[?&]state=/.test(path()) && (await pressed('national')) === 'true', `and back to National (${path()})`)
await page.goto(`${base}/chat`, { waitUntil: 'networkidle', timeout: 120_000 })
ok((await page.locator(`${sel} [data-side="place"]`).isVisible()) && (await page.locator(`${sel} [data-side="national"]`).count()) === 0, 'a page with no place scope: the town only')
await shot('5-other')
// A deep link with nothing saved (#1304 review): National, then one tap back to the linked place.
const ctx2 = await browser.newContext({ ...devices['iPhone SE'], reducedMotion: 'reduce' })
const p2 = await ctx2.newPage()
await p2.goto(`${base}/search?state=GA`, { waitUntil: 'networkidle', timeout: 120_000 })
await p2.locator(`${sel} [data-side="national"]`).click()
await p2.waitForTimeout(1200)
const backOk = await p2.locator(`${sel} [data-side="place"]`).isVisible()
await p2.locator(`${sel} [data-side="place"]`).click().catch(() => {})
await p2.waitForTimeout(1200)
ok(backOk && new URL(p2.url()).search.includes('state=GA'), `deep link, nothing saved: National and back to GA (${new URL(p2.url()).search})`)
const fits = await p2.evaluate(() => {
  const h = document.querySelector('.site-header')
  return h ? h.scrollWidth <= window.innerWidth + 1 : false
})
ok(fits, 'the header fits a 320px-wide phone without sideways scroll')
if (shots) await p2.screenshot({ path: `${shots}/phone-place-6-iphone-se.png`, clip: { x: 0, y: 0, width: 320, height: 160 } })
await browser.close()
if (failures) {
  console.error(`\n${failures} check(s) failed.`)
  process.exit(1)
}
console.log('\nThe place selector stays in the phone header; National is one tap away and back.')
