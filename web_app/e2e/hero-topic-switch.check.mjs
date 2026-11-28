// Home hero hot-topic pills and the box-flight topic switch (#1416).
//   node e2e/hero-topic-switch.check.mjs [--base http://localhost:5173] [--out dir] [--throttle 4] [--reduced 0|1]
// For each viewport (Pixel 7, 1440) and place (national, GA, FL): the pills render (live, rising, heated badges, Compare
// all last), picking a pill changes the headline and ?topic=, [data-box] marks are present before and after, and the switch
// is timed under CPU throttling (long tasks, frame gaps). Fails on a long task over 100 ms or a missing piece.
import { chromium } from 'playwright'
import fs from 'node:fs'
const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? process.argv[i + 1] : d }
const base = arg('base', 'http://localhost:5173')
const out = arg('out', '/tmp/hotpills')
const rate = Number(arg('throttle', '4'))
const reduced = arg('reduced', '0') === '1'
fs.mkdirSync(out, { recursive: true })
const views = [
  { name: 'pixel7', viewport: { width: 412, height: 915 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  { name: 'd1440', viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 },
]
const places = [['national', ''], ['GA', '?state=GA'], ['FL', '?state=FL']]
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu'] })
const report = []
const pillLists = {}
let failures = 0
const fail = (m) => { failures++; console.log('FAIL', m) }
for (const v of views) {
  for (const [pn, qs] of places) {
    const tag = `${v.name}-${pn}`
    const ctx = await browser.newContext({ viewport: v.viewport, deviceScaleFactor: v.deviceScaleFactor, isMobile: v.isMobile, hasTouch: v.hasTouch, reducedMotion: reduced ? 'reduce' : 'no-preference' })
    const page = await ctx.newPage()
    const errs = []
    page.on('pageerror', (e) => errs.push(String(e)))
    await page.addInitScript(() => {
      window.__canvasFrames = 0
      const loop = () => { if (document.querySelector('.box-flight-canvas')) window.__canvasFrames++; requestAnimationFrame(loop) }
      requestAnimationFrame(loop)
      window.__lt = []
      new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push({ s: e.startTime, d: e.duration }) }).observe({ type: 'longtask', buffered: true })
    })
    await page.goto(`${base}/${qs}`, { waitUntil: 'networkidle', timeout: 120_000 })
    await page.waitForSelector('.home-tbar [role="tab"]', { timeout: 60_000 })
    await page.waitForSelector('.home-story-map [data-box]', { state: 'attached', timeout: 150_000 })
    await page.waitForTimeout(2500)
    const pills = await page.$$eval('.home-tbar [role="tab"]', (els) => els.map((e) => ({
      id: e.dataset.topic, text: e.textContent.replace(/,.*$/, '').trim(), live: e.hasAttribute('data-live'),
      rising: !!e.querySelector('[data-badge=rising]'), heated: !!e.querySelector('[data-badge=heated]'),
    })))
    pillLists[tag] = pills.map((p) => `${p.id}${p.live ? '*' : ''}${p.rising ? '▲' : ''}${p.heated ? '🔥' : ''}`)
    if (pills.length < 3) fail(`${tag}: only ${pills.length} pills`)
    const lastIsAll = await page.$eval('.home-tbar-tail a', (a) => a.textContent.includes('Compare all') && !a.closest('[role=tablist]'))
    if (!lastIsAll) fail(`${tag}: Compare all is not last`)
    const scrollW = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
    if (!scrollW) fail(`${tag}: horizontal page overflow`)
    const rows = await page.$eval('.home-tbar-list', (l) => { const r = l.getBoundingClientRect(); const tops = new Set([...l.querySelectorAll('[role=tab]')].map((e) => e.getBoundingClientRect()).filter((b) => b.bottom <= r.bottom + 1).map((b) => Math.round(b.top))); return tops.size })
    if (v.name === 'd1440' && rows > 2) fail(`${tag}: ${rows} visible rows`)
    await page.screenshot({ path: `${out}/${tag}-0-before.png` })
    // Pick the first pill that is not the current one and has no story (the meeting view), then one with a story.
    const cur = new URL(page.url()).searchParams.get('topic') ?? 'data-centers'
    const picks = [pills.find((p) => p.id !== cur && !p.live), pills.find((p) => p.id !== cur && p.live && p.id !== 'data-centers')].filter(Boolean)
    if (picks.length === 0) fail(`${tag}: nothing to pick`)
    const cdp = await ctx.newCDPSession(page)
    await cdp.send('Emulation.setCPUThrottlingRate', { rate })
    let prevEmpty = false
    for (const pick of picks) {
      const beforeH = (await page.locator('#home-story-dc').first().textContent())?.trim()
      const boxesBefore = await page.locator('.home-story-map [data-box]').count()
      await page.evaluate(() => {
        window.__f = []; window.__lt = []
        let last = performance.now(); const t0 = last
        const tick = (n) => { window.__f.push(n - last); last = n; if (n - t0 < 6000) requestAnimationFrame(tick) }
        requestAnimationFrame(tick)
      })
      const tab = page.locator(`.home-tbar [role=tab][data-topic="${pick.id}"]`)
      await tab.scrollIntoViewIfNeeded()
      if (!(await tab.isVisible())) { const more = page.locator('.home-tbar-chip.is-more'); if (await more.count()) await more.click() }
      const t = Date.now()
      await tab.click({ timeout: 60000, noWaitAfter: true })
      await page.waitForFunction((id) => new URL(location.href).searchParams.get('topic') === id || (id === 'data-centers' && !new URL(location.href).searchParams.get('topic')), pick.id, { timeout: 8000 }).catch(() => fail(`${tag}: URL did not take ?topic=${pick.id}`))
      const urlMs = Date.now() - t
      await page.waitForFunction((h) => document.querySelector('#home-story-dc')?.textContent?.trim() !== h, beforeH, { timeout: 25000 }).catch(() => {})
      await page.waitForFunction(() => !document.querySelector('.box-flight-canvas'), null, { timeout: 20000 }).catch(() => {})
      await page.waitForTimeout(1200)
      const { f, lt } = await page.evaluate(() => ({ f: window.__f.slice(1), lt: window.__lt }))
      const afterH = (await page.locator('#home-story-dc').first().textContent())?.trim()
      const boxesAfter = await page.locator('.home-story-map [data-box]').count()
      const emptyMap = /\b0 meetings on record/.test((await page.locator('.home-story-map').first().textContent()) ?? '')
      const kind = await page.locator('[data-hero-kind]').count() ? 'meetings' : 'story'
      const sorted = [...f].sort((a, b) => a - b)
      const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? 0
      const maxLong = Math.max(0, ...lt.map((x) => x.d))
      if (afterH === beforeH) fail(`${tag}->${pick.id}: headline did not change`)
      if (boxesBefore === 0 && !prevEmpty) fail(`${tag}->${pick.id}: no [data-box] before`)
      if (boxesAfter === 0 && !emptyMap) fail(`${tag}->${pick.id}: no [data-box] after`)
      prevEmpty = emptyMap
      if (maxLong > 100) fail(`${tag}->${pick.id}: long task ${maxLong.toFixed(0)} ms`)
      if (await page.locator('.box-flight-canvas').count()) fail(`${tag}->${pick.id}: flight canvas still mounted`)
      report.push({ tag, to: pick.id, kind, boxesBefore, boxesAfter, urlMs, frames: f.length, p95FrameMs: +p95.toFixed(1), maxFrameMs: +Math.max(0, ...f).toFixed(1), longTasks: lt.length, maxLongTaskMs: +maxLong.toFixed(0), headline: afterH?.slice(0, 70) })
      await page.screenshot({ path: `${out}/${tag}-${pick.id}.png` })
    }
    if (errs.length) fail(`${tag}: page errors ${errs.join(' | ').slice(0, 200)}`)
    await ctx.close()
  }
}

// Place changes fly too: National -> AL -> National (#1416). Boxes before and after, and the flight canvas drew frames.
const placeReport = []
for (const v of views) {
  const tag = `${v.name}-place`
  const ctx = await browser.newContext({ viewport: v.viewport, deviceScaleFactor: v.deviceScaleFactor, isMobile: v.isMobile, hasTouch: v.hasTouch, reducedMotion: reduced ? 'reduce' : 'no-preference' })
  const page = await ctx.newPage()
  await page.addInitScript(() => {
    window.__canvasFrames = 0
    const loop = () => { if (document.querySelector('.box-flight-canvas')) window.__canvasFrames++; requestAnimationFrame(loop) }
    requestAnimationFrame(loop)
    window.__lt = []
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push({ s: e.startTime, d: e.duration }) }).observe({ type: 'longtask', buffered: true })
  })
  await page.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('.home-story-map [data-box]', { state: 'attached', timeout: 150_000 })
  await page.waitForTimeout(2500)
  const cdp = await ctx.newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate })
  const steps = [['AL', 'Alabama'], [null, 'America']]
  for (const [code, word] of steps) {
    const boxesBefore = await page.locator('.home-story-map [data-box]').count()
    const headBefore = (await page.locator('#home-story-dc').first().textContent())?.trim()
    await page.evaluate(() => { window.__canvasFrames = 0; window.__lt = [] })
    await page.locator('#home-story-dc button.stance-blank').first().click()
    const dlg = page.locator('[role=dialog]').first()
    await dlg.waitFor({ timeout: 8000 })
    // On a phone the map is below the headline: scroll it into view (the dialog is a fixed sheet) and let the snapshot settle.
    await page.locator('.home-story-map').first().scrollIntoViewIfNeeded()
    await page.waitForTimeout(900)
    if (code) await dlg.locator('select').first().selectOption(code)
    else await dlg.getByRole('button', { name: /United States/ }).first().click()
    // A state pick may need an explicit apply.
    const apply = dlg.getByRole('button', { name: /^(Apply|Show|Done|Go)/ })
    if (await apply.count()) await apply.first().click()
    await page.waitForFunction((w) => document.querySelector('#home-story-dc')?.textContent?.includes(w), word, { timeout: 15000 }).catch(() => fail(`${tag}->${code ?? 'national'}: headline never named ${word}`))
    await page.waitForFunction(() => !document.querySelector('.box-flight-canvas'), null, { timeout: 20000 }).catch(() => fail(`${tag}->${code ?? 'national'}: flight never finished`))
    await page.waitForTimeout(800)
    const frames = await page.evaluate(() => window.__canvasFrames)
    const lt = await page.evaluate(() => window.__lt)
    const boxesAfter = await page.locator('.home-story-map [data-box]').count()
    const maxLong = Math.max(0, ...lt.map((x) => x.d))
    if (boxesBefore === 0) fail(`${tag}->${code ?? 'national'}: no boxes before`)
    if (boxesAfter === 0) fail(`${tag}->${code ?? 'national'}: no boxes after`)
    if (!reduced && frames === 0) fail(`${tag}->${code ?? 'national'}: flight drew no canvas frames`)
    if (maxLong > 100) fail(`${tag}->${code ?? 'national'}: long task ${maxLong.toFixed(0)} ms`)
    placeReport.push({ tag, to: code ?? 'national', boxesBefore, boxesAfter, canvasFrames: frames, longTasks: lt.length, maxLongTaskMs: +maxLong.toFixed(0), headChanged: headBefore !== (await page.locator('#home-story-dc').first().textContent())?.trim() })
    await page.screenshot({ path: `${out}/${tag}-${code ?? 'national'}.png` })
  }
  await ctx.close()
}
console.table(placeReport)
fs.writeFileSync(`${out}/frame-timings${reduced ? '-reduced' : ''}.json`, JSON.stringify({ report, placeReport, pillLists }, null, 1))
console.table(report.map(({ headline, ...r }) => r))
for (const [k, v] of Object.entries(pillLists)) console.log(k, v.join(' '))
console.log(failures ? `${failures} failure(s)` : 'OK')
await browser.close()
process.exit(failures ? 1 : 0)
