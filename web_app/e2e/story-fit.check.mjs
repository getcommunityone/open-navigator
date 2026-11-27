// Story fit check (#1290, owner phone screenshot 27 Nov 2026: "Not fitting on phone by default."): on a phone, every story
// screen shows its headline, its one supporting line and its panel above the fixed bottom bar (`data-testid="story-bottombar"`),
// with nothing to scroll inside the screen. For each story path and each phone size (360x740 and 412x915) it opens every
// screen by `?screen=` and checks that
//   - the live screen's panel (`.stance-right`) ends above the bottom bar's top,
//   - the headline starts below the story's top bar and is in view,
//   - the screen's grid has no inner scroll (scrollHeight within its height) while "More" is closed.
//
//   node e2e/story-fit.check.mjs [--base http://localhost:5173] [--path /stories/data-centers?state=AL,...] [--shots <dir>]
//
// Exits 1 on a screen that doesn't fit. Needs the app (and its API) running; it reads the page, it changes nothing.
import { chromium } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const paths = arg('path', '/stories/data-centers?state=AL,/stories/data-centers,/stories/guns?state=AL').split(',')
const shots = arg('shots', null)
const SIZES = [
  { name: '360x740', viewport: { width: 360, height: 740 } },
  { name: '412x915', viewport: { width: 412, height: 915 } },
]
const TOL = 1

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
let failures = 0
const fail = (m) => {
  failures++
  console.log(`  FAIL ${m}`)
}

for (const size of SIZES) {
  const context = await browser.newContext({ viewport: size.viewport, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
  for (const path of paths) {
    const page = await context.newPage()
    await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
    await page.waitForSelector('section[data-panel]', { timeout: 60_000 })
    const ids = await page.$$eval('section[data-panel]', (els) => els.map((e) => e.getAttribute('data-screen')))
    console.log(`\n${size.name} ${path}: ${ids.length} screens`)
    for (const [i, id] of ids.entries()) {
      const sep = path.includes('?') ? '&' : '?'
      await page.goto(`${base}${path}${sep}screen=${id}`, { waitUntil: 'networkidle', timeout: 120_000 })
      await page.waitForSelector(`section[data-screen="${id}"][data-live]`, { timeout: 60_000 }).catch(() => null)
      await page.waitForTimeout(4000)
      // Put the screen in its snap place first: this checks the fit, not the landing (story-nav / story-next check that).
      await page.evaluate((sid) => document.querySelector(`section[data-screen="${sid}"]`)?.scrollIntoView({ block: 'start', behavior: 'instant' }), id)
      await page.waitForTimeout(400)
      const m = await page.evaluate((sid) => {
        const s = document.querySelector(`section[data-screen="${sid}"]`)
        if (!s) return null
        const r = (el) => (el ? el.getBoundingClientRect() : null)
        const bar = r(document.querySelector('[data-testid="story-bottombar"]'))
        const top = r(document.querySelector('.stance-top'))
        const right = s.querySelector('.stance-right')
        const grid = s.querySelector('.stance-grid')
        const head = r(s.querySelector('.stance-headline'))
        const shown = right && getComputedStyle(right).display !== 'none' && right.getBoundingClientRect().height > 0
        return {
          live: s.hasAttribute('data-live'),
          barTop: bar ? bar.top : innerHeight,
          topBottom: top ? top.bottom : 0,
          headTop: head ? head.top : null,
          rightBottom: shown ? right.getBoundingClientRect().bottom : null,
          scroll: grid ? grid.scrollHeight - grid.clientHeight : 0,
          more: s.hasAttribute('data-fit-more'),
        }
      }, id)
      if (shots) await page.screenshot({ path: `${shots}/fit-${size.name}-${path.replace(/[^a-z0-9]+/gi, '_')}-${String(i).padStart(2, '0')}-${id}.png` })
      if (!m) {
        fail(`${id}: screen not found`)
        continue
      }
      const problems = []
      if (!m.live) problems.push('not the live screen')
      if (m.rightBottom != null && m.rightBottom > m.barTop + TOL) problems.push(`panel ends at ${Math.round(m.rightBottom)}, under the bar at ${Math.round(m.barTop)}`)
      if (m.headTop != null && m.headTop < m.topBottom - TOL) problems.push(`headline at ${Math.round(m.headTop)} is under the top bar (${Math.round(m.topBottom)})`)
      if (m.scroll > 2) problems.push(`scrolls inside by ${m.scroll}px`)
      if (problems.length) fail(`${String(i).padStart(2)} ${id}: ${problems.join('; ')}`)
      else console.log(`  ok   ${String(i).padStart(2)} ${id}: panel bottom ${m.rightBottom == null ? '—' : Math.round(m.rightBottom)} ≤ bar ${Math.round(m.barTop)}`)
    }
    await page.close()
  }
  await context.close()
}
await browser.close()
console.log(failures ? `\n${failures} screen(s) don't fit` : '\nall screens fit')
process.exit(failures ? 1 : 0)
