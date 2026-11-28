// Box flight landing check (#1485): on every screen of a story, at 412x915 and 1440x900, the canvas boxes of the flight end
// on the settled DOM boxes. Each flight leaves its final poses (window.__boxFlightLast, set when __boxFlightProbe is true);
// after the page has settled they are compared with the live rects of the DOM boxes they landed on. Fails over 1 px.
//   node e2e/box-flight-landing.check.mjs [--base http://localhost:5173] [--path /stories/data-centers?state=AL,...] [--frames dir]
// --frames dir also saves a screenshot every ~80 ms through the first transition of each viewport (the owner's before/after).
import { chromium } from 'playwright'
import fs from 'node:fs'
const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? process.argv[i + 1] : d }
const base = arg('base', 'http://localhost:5173')
const paths = arg('path', '/stories/data-centers?state=AL').split(',')
const frames = arg('frames', '')
const TOL = Number(arg('tol', '1'))
const views = [
  { name: '412', viewport: { width: 412, height: 915 }, mobile: true },
  { name: '1440', viewport: { width: 1440, height: 900 }, mobile: false },
]
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu'] })
let failures = 0
const rows = []
for (const v of views) {
  const context = await browser.newContext({ viewport: v.viewport, deviceScaleFactor: 1, isMobile: v.mobile, hasTouch: v.mobile })
  for (const path of paths) {
    const page = await context.newPage()
    await page.addInitScript(() => { window.__boxFlightProbe = true })
    await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
    await page.waitForSelector('[data-panel]', { state: 'attached', timeout: 60_000 })
    await page.waitForTimeout(3000)
    const next = page.locator('[data-testid="story-next"]').first()
    let framesDone = false
    for (let i = 0; i < 14 && (await next.count()) > 0 && (await next.isVisible().catch(() => false)) && !(await next.evaluate((e) => e.classList.contains('is-quiet'))); i++) {
      const prevAt = await page.evaluate(() => window.__boxFlightLast?.at ?? 0)
      const t = Date.now()
      await next.click({ timeout: 5000 }).catch(() => {})
      if (frames && !framesDone) {
        framesDone = true
        fs.mkdirSync(frames, { recursive: true })
        for (let f = 0; f < 22; f++) { await page.screenshot({ path: `${frames}/${v.name}-${String(f).padStart(2, "0")}-${Date.now() - t}ms.png` }); await page.waitForTimeout(Math.max(0, 80 * (f + 1) - (Date.now() - t))) }
      }
      await page.waitForTimeout(2600)
      const screen = new URL(page.url()).searchParams.get('screen')
      const r = await page.evaluate((prev) => {
        const l = window.__boxFlightLast
        if (!l || l.at === prev) return { flew: false }
        let worst = 0, n = 0, lost = 0
        for (const p of l.poses) {
          if (!p.el || p.kind === 'fade' || p.kind === 'scatter') continue
          if (!p.el.isConnected) { lost++; continue }
          const b = p.el.getBoundingClientRect()
          const d = Math.max(Math.abs(b.left + b.width / 2 - p.x), Math.abs(b.top + b.height / 2 - p.y), Math.abs(b.width - p.w) / 2, Math.abs(b.height - p.h) / 2)
          worst = Math.max(worst, d); n++
        }
        return { flew: true, n, worst, lost }
      }, prevAt)
      rows.push({ view: v.name, path, step: i + 1, screen, ...r })
      if (r.flew && (r.worst > TOL || r.lost > 0)) { failures++; console.log(`FAIL ${v.name} ${path} -> ${screen}: worst ${r.worst.toFixed(2)} px over ${r.n} boxes, ${r.lost} detached`) }
    }
    await page.close()
  }
  await context.close()
}
console.table(rows)
const flown = rows.filter((r) => r.flew)
console.log(`${flown.length} flights checked, worst landing error ${Math.max(0, ...flown.map((r) => r.worst)).toFixed(2)} px`)
console.log(failures ? `${failures} failure(s)` : `OK: every flight ends within ${TOL} px of its DOM boxes`)
await browser.close()
process.exit(failures ? 1 : 0)
