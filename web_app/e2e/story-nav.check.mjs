// Story nav check (#1138, #1234): on a 1440x900 desktop, step through every screen of a data story and confirm the one
// fixed Next (bottom right, `data-testid="story-next"`, owner 2026-11-27) sits in the same place, at the same size, on every
// screen and on the cover (within 2px; on the last screen it is a quiet "Done" with the same right edge and bottom), and
// that the inline Back sits in the same place from the second screen on. No inline Next button shows beside the fixed one.
// The cover (#1182) is checked first: no Start/Next story button pair, one progress indicator, a Close (×); then Next.
//
// Topic stories (#1224) have one fixed Next instead of the inline one: e2e/story-next.check.mjs checks them.
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

// Software GL: on some machines (WSL after a restart) headless Chromium produces no frames with the default GPU path,
// so screenshots and clicks wait forever.
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
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
  // The story opens on its cover (#1182): Start is the way forward there, so no floating Next; one progress indicator (the
  // top bar's segments, no rail of numbered dots) and no Close (×) (#1192). Then Start lands on the first screen.
  const box = (sel) =>
    page.evaluate((sel) => {
      const el = document.querySelector(sel)
      if (!el || el.getClientRects().length === 0) return null
      const b = el.getBoundingClientRect()
      return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height), r: Math.round(innerWidth - b.right), b: Math.round(innerHeight - b.bottom), text: el.textContent.trim() }
    }, sel)
  const cover = await page.evaluate(() => {
    const shown = (sel) => [...document.querySelectorAll(sel)].some((el) => el.getClientRects().length > 0)
    return {
      pair: shown('[data-cover] .home-story-start') || shown('[data-cover] .home-story-next'),
      progress: ['[data-testid="stance-pips"]', '.story-dots', '[data-testid="story-topbar"]', '.story-bottombar-progress'].filter(shown).length,
      close: shown('[aria-label="Close story"]'),
    }
  })
  const coverNext = await box('[data-testid="story-next"]')
  const coverProblems = []
  if (cover.pair) coverProblems.push('the Start / Next story button pair is back on the cover')
  if (!coverNext) coverProblems.push('no fixed Next on the cover')
  else if (coverNext.r > 40 || coverNext.b > 40 || coverNext.h < 44) coverProblems.push(`Next not at the bottom right: ${JSON.stringify(coverNext)}`)
  if (cover.progress !== 1) coverProblems.push(`${cover.progress} progress indicators`)
  // Close (×) is back, top right (owner 2026-11-27, reversing #1199's removal).
  if (!cover.close) coverProblems.push('no Close (×) button')
  failures += coverProblems.length ? 1 : 0
  console.log(`\n${path}: cover ${coverProblems.length ? 'FAIL  <- ' + coverProblems.join('; ') : 'ok'} next=${JSON.stringify(coverNext)}`)
  if (coverNext) {
    await page.locator('[data-testid="story-next"]').click()
    await page.waitForTimeout(1500)
  }
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
        return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height), r: Math.round(innerWidth - b.right), b: Math.round(innerHeight - b.bottom) }
      }
      const fixed = document.querySelector('[data-testid="story-next"]')
      const inline = panel?.querySelector('.stance-nav button.stance-next[data-nav="next"]')
      const back = panel?.querySelector('.stance-nav [data-nav="back"]') ?? panel?.querySelector('.stance-nav .stance-back')
      return { id: panel?.getAttribute('data-screen'), next: box(fixed), label: fixed?.textContent?.trim() ?? '', inline: Boolean(box(inline)), back: box(back) }
    }, i)
    rows.push(r)
    if (shots) await page.screenshot({ path: `${shots}-${path.replace(/[^a-z0-9]+/gi, '_')}-${String(i + 1).padStart(2, '0')}-${r.id}.png` })
    if (i < count - 1) {
      await page.keyboard.press('ArrowRight')
    }
  }
  const ref = rows[0]?.next
  const refBack = rows.find((r) => r.back)?.back
  const near = (a, b) => a && b && Math.abs(a.x - b.x) <= TOL && Math.abs(a.y - b.y) <= TOL && Math.abs(a.w - b.w) <= TOL && Math.abs(a.h - b.h) <= TOL
  // The last screen's Next is a quiet "Done" (owner 2026-11-27), so it keeps Next's right edge, bottom and height.
  const endsLike = (a, b) => a && b && Math.abs(a.r - b.r) <= TOL && Math.abs(a.b - b.b) <= TOL && Math.abs(a.h - b.h) <= TOL
  console.log(`\n${path}: ${rows.length} screens`)
  rows.forEach((r, i) => {
    const problems = []
    const last = i === rows.length - 1
    if (!r.next) problems.push('no fixed Next')
    else if (last ? !endsLike(r.next, ref) : !near(r.next, ref)) problems.push(`Next ${JSON.stringify(r.next)} != ${JSON.stringify(ref)}`)
    if (r.next && (r.next.r > 40 || r.next.b > 40 || r.next.h < 44)) problems.push('Next not at the bottom right or under 44px')
    if (last && !/^Done/.test(r.label)) problems.push(`last screen's Next reads "${r.label}", not a quiet Done`)
    if (r.inline) problems.push('an inline Next beside the fixed one')
    if (i === 0 && r.back) problems.push('Back on the first screen')
    if (i > 0 && !r.back) problems.push('no Back')
    else if (i > 0 && !near(r.back, refBack)) problems.push(`Back ${JSON.stringify(r.back)} != ${JSON.stringify(refBack)}`)
    failures += problems.length ? 1 : 0
    console.log(`  ${problems.length ? 'FAIL' : 'ok  '} ${String(i + 1).padStart(2)} ${r.id}: next=${JSON.stringify(r.next)} "${r.label}" back=${JSON.stringify(r.back)}${problems.length ? '  <- ' + problems.join('; ') : ''}`)
  })
  await page.close()
}
await browser.close()
if (failures) {
  console.error(`\n${failures} screen(s) out of line.`)
  process.exit(1)
}
console.log('\nAll screens line up.')
