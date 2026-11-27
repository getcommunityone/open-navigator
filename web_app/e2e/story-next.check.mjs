// Story Next and Close check (#1224, owner 2026-11-27: one green Next fixed at the bottom right, Close (×) at the top right,
// no Next story button): on a topic story, step from the cover to the last screen at Pixel 7, iPhone 13 and 1440x900 and
// confirm the one Next ([data-testid="story-next"]; Done on the last screen) is at the same bottom-right spot on every screen
// (right edge and bottom within 2px, near the window's corner), Close ([data-testid="story-close"]) is the same box at the
// top right on every screen, no "Next story" button shows, the cover has no Start / Next story pair, and each step lands on
// the next screen. Steps alternate between the Next button, a progress segment (wide) and a swipe left (phones).
//
//   node e2e/story-next.check.mjs [--base http://localhost:5173] [--path /stories/guns,/stories/pickleball?state=CA] [--shots <dir>/next] [--devices pixel-7,iphone-13,desktop]
//
// Exits 1 on a mismatch. Needs the app (and its API) running; it reads the page, it changes nothing.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const paths = arg('path', '/stories/guns,/stories/pickleball?state=CA,/stories/water-fluoridation').split(',')
const shots = arg('shots', null)
const TOL = 2
const CORNER = 40
const DEVICES = { 'pixel-7': devices['Pixel 7'], 'iphone-13': devices['iPhone 13'], desktop: { viewport: { width: 1440, height: 900 } } }

// Software-only rendering: some headless hosts never produce a frame with the GPU path (rAF stalls).
const browser = await chromium.launch({ args: ['--disable-gpu', '--disable-software-rasterizer'] })
let failures = 0
const fail = (msg) => {
  failures += 1
  console.log(`  FAIL ${msg}`)
}

const nextBox = (page) =>
  page.evaluate(() => {
    const box = (sel) => {
      const el = document.querySelector(sel)
      if (!el || el.getClientRects().length === 0) return null
      const b = el.getBoundingClientRect()
      return { x: Math.round(b.x), y: Math.round(b.y), right: Math.round(b.right), bottom: Math.round(b.bottom), w: Math.round(b.width), h: Math.round(b.height), text: el.textContent.trim() }
    }
    const next = box('[data-testid="story-next"]')
    return next ? { ...next, vw: innerWidth, vh: innerHeight, close: box('[data-testid="story-close"]'), nextStory: [...document.querySelectorAll('a, button')].some((e) => e.getClientRects().length && /next story/i.test(e.textContent)) } : null
  })

const only = arg('devices', null)?.split(',')
for (const [name, device] of Object.entries(DEVICES)) {
  if (only && !only.includes(name)) continue
  const context = await browser.newContext(device)
  const phone = name !== 'desktop'
  for (const path of paths) {
    const page = await context.newPage()
    await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
    await page.waitForSelector('[data-panel="0"]', { timeout: 60_000 })
    await page.waitForTimeout(2000)
    const ids = await page.$$eval('section[data-panel]', (els) => els.map((e) => e.getAttribute('data-screen')))
    console.log(`\n${name} ${path}: ${ids.length} screens (${ids.join(', ')})`)
    const pair = await page.locator('[data-cover] .home-story-start, [data-cover] .home-story-next').count()
    if (pair) fail('the cover still shows its own Start / Next story buttons')
    const rows = [{ id: 'cover', box: await nextBox(page) }]
    if (shots) await page.screenshot({ path: `${shots}-${name}-${path.replace(/[^a-z0-9]+/gi, '_')}-00-cover.png` })
    await page.locator('[data-testid="story-next"]').click()
    await page.waitForTimeout(1800)
    for (let i = 0; i < ids.length; i++) {
      const live = await page.evaluate(() => document.querySelector('[data-panel][data-live]')?.getAttribute('data-screen'))
      if (live !== ids[i]) fail(`step ${i + 1}: expected ${ids[i]}, on ${live}`)
      rows.push({ id: ids[i], box: await nextBox(page) })
      if (shots) await page.screenshot({ path: `${shots}-${name}-${path.replace(/[^a-z0-9]+/gi, '_')}-${String(i + 1).padStart(2, '0')}-${ids[i]}.png` })
      if (i === ids.length - 1) break
      if (i % 3 === 1 && phone) {
        // A swipe left on the screen's headline.
        await page.evaluate(() => {
          const el = document.querySelector('[data-panel][data-live] .stance-head') ?? document.body
          const t = (x, y) => new Touch({ identifier: 1, target: el, clientX: x, clientY: y })
          el.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, touches: [t(300, 400)], changedTouches: [t(300, 400)] }))
          el.dispatchEvent(new TouchEvent('touchend', { bubbles: true, touches: [], changedTouches: [t(140, 410)] }))
        })
      } else if (i % 3 === 1 && !phone) {
        await page.locator('[data-testid="stance-pips"] button').nth(i + 1).click()
      } else {
        await page.locator('[data-testid="story-next"]').click()
      }
      await page.waitForTimeout(1800)
    }
    const ref = rows.find((r) => r.box)?.box
    const screenClose = rows.find((r, k) => k > 0 && r.box?.close)?.box.close
    rows.forEach((r, i) => {
      const problems = []
      if (!r.box) problems.push('no Next in view')
      else {
        if (Math.abs(r.box.right - ref.right) > TOL || Math.abs(r.box.bottom - ref.bottom) > TOL) problems.push(`moved: ${JSON.stringify(r.box)} vs ${JSON.stringify(ref)}`)
        if (r.box.vw - r.box.right > CORNER || r.box.vh - r.box.bottom > CORNER) problems.push(`not at the bottom right: ${JSON.stringify(r.box)}`)
        const c = r.box.close
        const rc = ref.close
        if (!c) problems.push('no Close (×)')
        // The site header above the story's bar is taller at the top of the page (the cover), so the cover's Close sits lower by
        // that difference; on the screens it must not move at all. Its right edge and size never change.
        else if (!rc || Math.abs(c.x - rc.x) > TOL || Math.abs(c.w - rc.w) > TOL || Math.abs(c.h - rc.h) > TOL || (i > 0 && Math.abs(c.y - screenClose.y) > TOL)) problems.push(`Close moved: ${JSON.stringify(c)} vs ${JSON.stringify(i > 0 ? screenClose : rc)}`)
        else if (r.box.vw - c.right > CORNER) problems.push(`Close not at the top right: ${JSON.stringify(c)}`)
        if (r.box.nextStory) problems.push('a "Next story" button is shown')
      }
      if (problems.length) fail(`${String(i).padStart(2)} ${r.id}: ${problems.join('; ')}`)
      else console.log(`  ok   ${String(i).padStart(2)} ${r.id}: next right=${r.box.right} bottom=${r.box.bottom} "${r.box.text}" · close ${r.box.close.x},${r.box.close.y}`)
    })
    await page.close()
  }
  await context.close()
}
await browser.close()
if (failures) {
  console.error(`\n${failures} problem(s).`)
  process.exit(1)
}
console.log('\nNext and Close sit at the same spots on every screen.')
