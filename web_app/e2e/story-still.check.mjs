// Story stillness check (#1415): with no input, a story screen is completely still. After a screen settles, three seconds of
// idling must show no layout shift, no change in the screen's or its figure's box, no scroll movement, no flight canvas, and
// no fit change (`.fit-hidden` / zoom toggling is what a measure-and-move-back loop looks like).
//   node e2e/story-still.check.mjs [--base http://localhost:5173] [--path /stories/data-centers?state=AL&city=Tuscaloosa] [--sizes 412x915,360x740] [--idle 3000]
import { chromium } from 'playwright'
const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? process.argv[i + 1] : d }
const base = arg('base', 'http://localhost:5173')
const path = arg('path', '/stories/data-centers?state=AL&city=Tuscaloosa')
const sizes = arg('sizes', '412x915,360x740').split(',').map((s) => s.split('x').map(Number))
const idle = Number(arg('idle', '3000'))
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu'] })
let failures = 0
for (const [w, h] of sizes) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
  const page = await ctx.newPage()
  await page.addInitScript(() => {
    window.__cls = 0
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value }).observe({ type: 'layout-shift', buffered: true })
  })
  await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-panel]', { state: 'attached', timeout: 60_000 })
  await page.waitForTimeout(4000)
  const next = page.locator('[data-testid="story-next"]').first()
  let step = 0
  for (;;) {
    await page.waitForTimeout(1500)
    await page.waitForFunction(() => !document.querySelector('canvas.box-flight-canvas'), null, { timeout: 8000 }).catch(() => {})
    await page.waitForTimeout(1500)
    const screen = new URL(page.url()).searchParams.get('screen')
    const r = await page.evaluate((ms) => new Promise((res) => {
      const live = () => document.querySelector('[data-live]')
      const box = (e) => { if (!e) return '-'; const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map((v) => Math.round(v * 10) / 10).join(',') }
      const fitSig = () => [...(live()?.querySelectorAll('.fit-hidden, [data-fit-zoom]') ?? [])].map((e) => (e.className?.baseVal ?? e.className) + (e.style.zoom || e.style.maxHeight)).join('|')
      const sig = () => JSON.stringify([Math.round(scrollY), live()?.getAttribute('data-screen'), box(live()), box(live()?.querySelector('.stance-figure, .stance-right')), fitSig()])
      const cls0 = window.__cls
      const first = sig()
      let moves = 0, canvas = 0
      let fit = 0
      let last = first
      const t0 = performance.now()
      const tick = () => {
        if (document.querySelector('canvas.box-flight-canvas')) canvas++
        const s = sig(); if (s !== last) { moves++; last = s }
        if (performance.now() - t0 < ms) requestAnimationFrame(tick)
        else { res({ cls: window.__cls - cls0, moves, canvas, fit, first, last }) }
      }
      requestAnimationFrame(tick)
    }), idle)
    const bad = []
    if (r.cls > 0.001) bad.push(`layout shift ${r.cls.toFixed(4)}`)
    if (r.moves > 0) bad.push(`${r.moves} box, scroll or fit changes (${r.first} -> ${r.last})`)
    if (r.canvas > 0) bad.push(`flight canvas present in ${r.canvas} frames`)
    if (bad.length) { failures++; console.log(`FAIL ${w}x${h} ${screen}: ${bad.join('; ')}`) } else console.log(`ok   ${w}x${h} ${screen}: still`)
    if (step++ > 20 || !(await next.count()) || !(await next.isVisible().catch(() => false)) || (await next.evaluate((e) => e.classList.contains('is-quiet')))) break
    await next.click({ timeout: 5000 }).catch(() => {})
  }
  await ctx.close()
}
await browser.close()
console.log(failures ? `${failures} screen(s) not still` : 'OK: every screen is still when idle')
process.exit(failures ? 1 : 0)
