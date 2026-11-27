// Story nav check (#1138): on a 1440x900 desktop, step through every screen of a data story and confirm the inline Next and
// Back buttons sit in the same place, at the same size, on every screen (within 2px). The first screen has no Back but its
// Next keeps the spot; the last screen's primary action takes Next's spot (same right edge, top and height; its label is longer). No floating Next is shown while the inline one is.
//
//   node e2e/story-nav.check.mjs [--base http://localhost:5173] [--path /stories/data-centers] [--shots <dir>/nav-after]
//
// The last screen's link to the records shows once the closing question is answered, so the check answers it. That answer
// is answered in the browser only: the POST is intercepted and given the real current results, so no vote is stored.
//
// Exits 1 on a mismatch. Needs the app (and its API) running; it reads the page, it changes nothing.
import { chromium } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const paths = (arg('path', '/stories/data-centers,/stories/data-centers?state=AL')).split(',')
const shots = arg('shots', null)
const TOL = 2

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
let failures = 0

// Answer without storing (see above): fulfil the vote POST from the real results GET, with the reader's answer set.
await context.route('**/api/stance/choices', async (route) => {
  if (route.request().method() !== 'POST') return route.continue()
  const body = route.request().postDataJSON()
  const qs = new URLSearchParams({ player_id: body.player_id })
  if (body.state_code) qs.set('state_code', body.state_code)
  if (body.place_name) qs.set('place_name', body.place_name)
  const res = await context.request.get(`${base}/api/stance/packs/${encodeURIComponent(body.pack_id)}/choice-results?${qs}`)
  const results = await res.json()
  results.your = { ...(results.your ?? {}), [body.moment]: body.choice }
  await route.fulfill({ json: { stance_choice_response: { ...body }, results } })
})

for (const path of paths) {
  // A fresh page per story, so each starts on its first screen.
  const page = await context.newPage()
  await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-panel="0"][data-live]', { timeout: 60_000 })
  await page.waitForTimeout(1500)
  const count = await page.locator('section[data-panel]').count()
  const rows = []
  for (let i = 0; i < count; i++) {
    await page.waitForSelector(`[data-panel="${i}"][data-live]`, { timeout: 20_000 })
    await page.waitForTimeout(1200)
    if (i === count - 1) {
      // The last screen's primary action (the link to the records) shows once its question is answered.
      const answer = page.locator(`[data-panel="${i}"] .stance-answers button`).first()
      const hasNext = await page.locator(`[data-panel="${i}"] .stance-nav [data-nav="next"], [data-panel="${i}"] .stance-nav .stance-next`).count()
      if (!hasNext && (await answer.count())) {
        await answer.click()
        await page.waitForSelector(`[data-panel="${i}"] .stance-nav [data-nav="next"], [data-panel="${i}"] .stance-nav .stance-next`, { timeout: 20_000 })
        await page.waitForTimeout(800)
      }
    }
    const r = await page.evaluate((i) => {
      const panel = document.querySelector(`[data-panel="${i}"]`)
      const box = (el) => {
        if (!el || el.getClientRects().length === 0) return null
        const b = el.getBoundingClientRect()
        return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }
      }
      const next = panel?.querySelector('.stance-nav [data-nav="next"]') ?? panel?.querySelector('.stance-nav .stance-next')
      const back = panel?.querySelector('.stance-nav [data-nav="back"]') ?? panel?.querySelector('.stance-nav .stance-back')
      const float = document.querySelector('[data-testid="floating-next"]')
      return { id: panel?.getAttribute('data-screen'), next: box(next), back: box(back), floating: Boolean(float && float.getClientRects().length) }
    }, i)
    rows.push(r)
    if (shots) await page.screenshot({ path: `${shots}-${path.replace(/[^a-z0-9]+/gi, '_')}-${String(i + 1).padStart(2, '0')}-${r.id}.png` })
    if (i < count - 1) {
      await page.keyboard.press('ArrowRight')
    }
  }
  const ref = rows.find((r) => r.next)?.next
  const refBack = rows.find((r) => r.back)?.back
  const near = (a, b) => a && b && Math.abs(a.x - b.x) <= TOL && Math.abs(a.y - b.y) <= TOL && Math.abs(a.w - b.w) <= TOL && Math.abs(a.h - b.h) <= TOL
  // The last screen's action reads longer than "Next", so it takes Next's spot by its right edge, top and height.
  const endsLike = (a, b) => a && b && Math.abs(a.x + a.w - (b.x + b.w)) <= TOL && Math.abs(a.y - b.y) <= TOL && Math.abs(a.h - b.h) <= TOL
  console.log(`\n${path}: ${rows.length} screens`)
  rows.forEach((r, i) => {
    const problems = []
    const last = i === rows.length - 1
    if (!r.next) problems.push('no Next')
    else if (last ? !endsLike(r.next, ref) : !near(r.next, ref)) problems.push(`Next ${JSON.stringify(r.next)} != ${JSON.stringify(ref)}`)
    if (i === 0 && r.back) problems.push('Back on the first screen')
    if (i > 0 && !r.back) problems.push('no Back')
    else if (i > 0 && !near(r.back, refBack)) problems.push(`Back ${JSON.stringify(r.back)} != ${JSON.stringify(refBack)}`)
    if (r.floating && r.next) problems.push('floating Next shown beside the inline one')
    failures += problems.length ? 1 : 0
    console.log(`  ${problems.length ? 'FAIL' : 'ok  '} ${String(i + 1).padStart(2)} ${r.id}: next=${JSON.stringify(r.next)} back=${JSON.stringify(r.back)}${problems.length ? '  <- ' + problems.join('; ') : ''}`)
  })
  await page.close()
}
await browser.close()
if (failures) {
  console.error(`\n${failures} screen(s) out of line.`)
  process.exit(1)
}
console.log('\nAll screens line up.')
