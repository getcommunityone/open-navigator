// Topic county map screenshots (#1349): each topic story's Overview at a state draws the county map with town rings.
//   node e2e/topic-county-map.shots.mjs --base http://127.0.0.1:5481 --shots <dir>
// It reads the page and changes nothing. Exits 1 when a state Overview still draws the outline only or a page errors.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const BASE = arg('base', 'http://localhost:5173')
const SHOTS = arg('shots', '/tmp/topicmap')
const PAGES = [
  ['wf-al', '/stories/water-fluoridation?state=AL&screen=overview', true],
  ['wf-ga', '/stories/water-fluoridation?state=GA&screen=overview', true],
  ['guns-al', '/stories/guns?state=AL&screen=overview', true],
  ['pickleball-ga', '/stories/pickleball?state=GA&screen=overview', true],
  ['str-national', '/stories/short-term-rentals?screen=overview', false],
  ['str-al', '/stories/short-term-rentals?state=AL&screen=overview', true],
  ['home-wf-al', '/?story=water-fluoridation&state=AL', true],
]
const VIEWS = [
  ['pixel7', devices['Pixel 7']],
  ['1440', { viewport: { width: 1440, height: 900 } }],
]

const browser = await chromium.launch()
let failed = 0
for (const [vname, opts] of VIEWS) {
  const ctx = await browser.newContext(opts)
  for (const [name, path, county] of PAGES) {
    const page = await ctx.newPage()
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded' })
    const sel = county ? 'svg[data-map="county"]' : 'svg rect[data-state]'
    const ok = await page.waitForSelector(sel, { timeout: 30000 }).then(() => true, () => false)
    await page.waitForTimeout(1200)
    const info = await page.evaluate(() => ({
      title: document.querySelector('.stance-map-title')?.textContent ?? null,
      rings: document.querySelectorAll('svg[data-map="county"] .stance-map-place').length,
      outline: Boolean(document.querySelector('[data-zoom-note]')),
      unplaced: document.querySelector('[data-unplaced]')?.textContent ?? null,
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    }))
    await page.screenshot({ path: `${SHOTS}/${name}-${vname}.png`, fullPage: false })
    const bad = !ok || errors.length > 0 || info.overflow || (county && info.outline)
    if (bad) failed++
    console.log(`${bad ? 'FAIL' : 'ok  '} ${vname} ${name}: ${JSON.stringify(info)}${errors.length ? ` errors=${errors.join(' | ')}` : ''}`)
    await page.close()
  }
  await ctx.close()
}
await browser.close()
process.exit(failed ? 1 : 0)
