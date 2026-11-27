// Phone header location selector check (#1301). At phone width the header always shows the place selector, outside the
// menu: with no town, a pin and a ZIP field; after a ZIP, a [📍 town | National] toggle that switches both ways in one
// tap without retyping, on Home (?scope=national) and on a story (?state=&city=). A page with no place scope shows the
// town only.
//
//   node e2e/phone-place-header.check.mjs [--base http://localhost:5173] [--zip 35401] [--shots <dir>]
//
// It uses the real ZIP lookup (/api/geocode). When the ZIP spans places, it picks the first choice. Exits 1 on any failure.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const zip = arg('zip', '35401')
const shots = arg('shots', null)
let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}
const browser = await chromium.launch()
const ctx = await browser.newContext({ ...devices['iPhone 13'], reducedMotion: 'reduce' })
const page = await ctx.newPage()
const sel = '[data-testid="header-place-phone"]'
const shot = async (name) => shots && page.screenshot({ path: `${shots}/phone-place-${name}.png`, clip: { x: 0, y: 0, width: 390, height: 200 } })
const pressed = (side) => page.locator(`${sel} [data-side="${side}"]`).getAttribute('aria-pressed')
const path = () => { const u = new URL(page.url()); return u.pathname + u.search }

console.log(`\niPhone 13 ${base}`)
await page.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 120_000 })
ok(await page.locator(sel).isVisible(), 'the selector is in the header, outside the menu')
ok(await page.locator(`${sel} input[aria-label="ZIP code"]`).isVisible(), 'with no town: a pin + ZIP field')
await shot('1-zip')
await page.locator(`${sel} input[aria-label="ZIP code"]`).fill(zip)
await page.locator(`${sel} button[type=submit]`).click()
await page.waitForSelector(`${sel} [data-side="place"], ${sel} .sh-pzip-choice`, { timeout: 60_000 })
if (await page.locator(`${sel} .sh-pzip-choice`).count()) await page.locator(`${sel} .sh-pzip-choice`).first().click()
await page.waitForSelector(`${sel} [data-side="place"]`, { timeout: 30_000 })
const town = (await page.locator(`${sel} [data-side="place"]`).innerText()).replace('📍', '').trim()
ok(town.length > 0 && (await pressed('place')) === 'true', `after the ZIP: the town is on (${town})`)
await shot('2-town')
await page.locator(`${sel} [data-side="national"]`).click()
await page.waitForTimeout(1200)
ok(path().includes('scope=national') && (await pressed('national')) === 'true', `one tap to National on Home (${path()})`)
await shot('3-home-national')
await page.locator(`${sel} [data-side="place"]`).click()
await page.waitForTimeout(1200)
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
await browser.close()
if (failures) {
  console.error(`\n${failures} check(s) failed.`)
  process.exit(1)
}
console.log('\nThe place selector stays in the phone header; National is one tap away and back.')
