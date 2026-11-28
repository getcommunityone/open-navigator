// Box coverage check (#1415): steps through every screen of each story with Next and asserts the settled screen has at
// least one visible [data-box] (so a particle flight always has somewhere to land). Optional screenshots per screen.
//   node e2e/box-coverage.check.mjs [--base http://localhost:5173] [--path /stories/data-centers?state=GA,/stories/guns?state=AL] [--out dir] [--width 412]
import { chromium } from 'playwright'
import fs from 'node:fs'
const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? process.argv[i + 1] : d }
const base = arg('base', 'http://localhost:5173')
const paths = arg('path', '/stories/data-centers?state=GA,/stories/guns?state=AL').split(',').flatMap((p, i, a) => (p.includes('?') || !a[i - 1] ? [p] : [`${a[i - 1].split('?')[0]}?${p}`]))
const width = Number(arg('width', '412'))
const height = Number(arg('height', width < 700 ? (width <= 360 ? '740' : '915') : '900'))
const fit = arg('fit', '1') === '1'
const out = arg('out', '')
if (out) fs.mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu'] })
const mobile = width < 700
const innerWidth0 = width
const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile })
let failures = 0
const rows = []
for (const path of paths) {
  const page = await context.newPage()
  await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-panel]', { state: 'attached', timeout: 60_000 })
  await page.waitForTimeout(3000)
  const next = page.locator('[data-testid="story-next"]').first()
  let i = 0
  const slug = path.split('/')[2]?.split('?')[0]
  const state = new URL(base + path).searchParams.get('state') ?? 'US'
  for (;;) {
    await page.waitForTimeout(3200)
    const measure = () => page.evaluate(() => {
      const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth }
      const panels = [...document.querySelectorAll('[data-panel]')]
      const want = new URLSearchParams(location.search).get('screen')
      const panel = ((want && panels.find((p) => p.getAttribute("data-screen") === want)) || panels.find((p) => { const r = p.getBoundingClientRect(); return r.bottom > innerHeight * 0.3 && r.top < innerHeight * 0.7 })) ?? panels[0]
      const boxes = panel ? [...panel.querySelectorAll('[data-box]')].filter(vis).length : 0
      const emptyQuotes = [...document.querySelectorAll('blockquote')].filter((b) => !b.textContent.replace(/[“”"\s]/g, '')).length
      // Fit (#1415): on a phone the headline is fully below the top bar, and the screen's visual and legend end above the bottom bar.
      const top = document.querySelector('.stance-top')?.getBoundingClientRect().bottom ?? 0
      const bar = document.querySelector('[data-testid="story-bottombar"]')?.getBoundingClientRect().top ?? innerHeight
      const hl = panel?.querySelector('.stance-headline')?.getBoundingClientRect()
      const vz = panel ? [...panel.querySelectorAll('[data-screen-boxes], .wf-wrap')].filter((e) => e.getBoundingClientRect().height > 0) : []
      const vEnd = vz.length ? Math.max(...vz.map((e) => e.getBoundingClientRect().bottom)) : 0
      const fitInfo = { headTop: hl ? Math.round(hl.top - top) : null, visEnd: Math.round(bar - vEnd) }
      return { ...fitInfo, screen: new URLSearchParams(location.search).get('screen'), panel: panel?.getAttribute('data-panel'), boxes, emptyQuotes }
    })
    // A screen still scrolling into its snap place is measured again, up to four times, before it counts as failing.
    let info = await measure()
    for (let k = 0; k < 4 && (info.boxes < 1 || (mobile && ((info.headTop ?? 0) < -1 || info.visEnd < 0))); k++) { await page.waitForTimeout(1200); info = await measure() }
    rows.push({ path, step: i, ...info })
    if (info.boxes < 1) { failures++; console.log(`FAIL ${path} screen ${info.screen} (panel ${info.panel}): no visible [data-box]`) }
    if (fit && innerWidth0 < 700 && info.headTop != null && info.headTop < -1) { failures++; console.log(`FAIL ${path} screen ${info.screen}: headline clipped ${-info.headTop}px under the top bar`) }
    if (fit && innerWidth0 < 700 && info.visEnd < 0) { failures++; console.log(`FAIL ${path} screen ${info.screen}: visual ends ${-info.visEnd}px under the bottom bar`) }
    if (info.emptyQuotes) { failures++; console.log(`FAIL ${path} screen ${info.screen}: ${info.emptyQuotes} empty blockquote(s)`) }
    if (out) await page.screenshot({ path: `${out}/${slug}-${state}-${width}-${String(i).padStart(2, '0')}-${info.screen}.png` })
    if (i > 20 || (await next.count()) === 0 || !(await next.isVisible().catch(() => false)) || (await next.evaluate((e) => e.classList.contains('is-quiet')))) break
    await next.click({ timeout: 5000 }).catch(() => {})
    i++
  }
  await page.close()
}
console.table(rows)
console.log(failures ? `${failures} failure(s)` : 'OK: every screen has visible boxes')
await browser.close()
process.exit(failures ? 1 : 0)
