// Box transition perf check (#1406): steps through every screen of a story with Next on a phone at 4x CPU throttle,
// records frame gaps (rAF) and long tasks during each transition, and fails on a long task over 100 ms.
//   node e2e/box-transition-perf.check.mjs [--base http://localhost:5173] [--path /stories/data-centers?state=AL] [--out dir]
import { chromium } from 'playwright'
import fs from 'node:fs'
const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? process.argv[i + 1] : d }
const base = arg('base', 'http://localhost:5173')
const paths = arg('path', '/stories/data-centers?state=AL').split(',')
const out = arg('out', '/tmp/boxmorph')
fs.mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu'] })
const context = await browser.newContext({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, reducedMotion: arg('reduced', '0') === '1' ? 'reduce' : 'no-preference' })
let failures = 0
const report = []
for (const path of paths) {
  const page = await context.newPage()
  await page.addInitScript(() => {
    window.__lt = []
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push({ s: e.startTime, d: e.duration }) }).observe({ type: 'longtask', buffered: true })
  })
  await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-panel]', { state: 'attached', timeout: 60_000 })
  await page.waitForTimeout(4000)
  const cdp = await context.newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  const next = page.locator('[data-testid="story-next"]').first()
  let i = 0
  while (i < 14 && (await next.count()) > 0 && (await next.isVisible().catch(() => false)) && !(await next.evaluate((e) => e.classList.contains('is-quiet')))) {
    await page.evaluate(() => {
      window.__f = []; window.__lt = []
      let last = performance.now(); const t0 = last
      const tick = (n) => { window.__f.push(n - last); last = n; if (n - t0 < 1600) requestAnimationFrame(tick) }
      requestAnimationFrame(tick)
    })
    const t = Date.now()
    await next.click({ timeout: 5000 }).catch(() => {})
    const clickMs = Date.now() - t
    await page.waitForTimeout(1800)
    const { f, lt } = await page.evaluate(() => ({ f: window.__f.slice(1), lt: window.__lt }))
    const sorted = [...f].sort((a, b) => a - b)
    const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? 0
    const maxLong = Math.max(0, ...lt.map((x) => x.d))
    const screen = new URL(page.url()).searchParams.get('screen')
    report.push({ path, step: i + 1, screen, frames: f.length, avgFrameMs: +(f.reduce((a, b) => a + b, 0) / Math.max(1, f.length)).toFixed(1), p95FrameMs: +p95.toFixed(1), maxFrameMs: +Math.max(0, ...f).toFixed(1), longTasks: lt.length, maxLongTaskMs: +maxLong.toFixed(0), clickMs })
    if (maxLong > 100) { failures++; console.log(`FAIL ${path} step ${i + 1} (${screen}): long task ${maxLong.toFixed(0)} ms`) }
    await page.screenshot({ path: `${out}/${path.split('/')[2]?.split('?')[0]}-${String(i + 1).padStart(2, '0')}-${screen}.png` })
    i++
  }
  await page.close()
}
fs.writeFileSync(`${out}/frame-timings.json`, JSON.stringify(report, null, 1))
console.table(report)
console.log(failures ? `${failures} failure(s)` : 'OK: no long task over 100 ms during transitions')
await browser.close()
process.exit(failures ? 1 : 0)
