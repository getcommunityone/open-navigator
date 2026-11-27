// Story header, summary and pager check (#1337). At 360x740 and 412x915, on a city that steps up to its state
// (/stories/data-centers?state=AL&city=Tuscaloosa) it asserts: the headline and the scope note do not intersect; the note is
// one short line with its full reason behind "Why?"; the sticky bar is at most 25% of the viewport; the first screen is the
// summary card; the pager reads "k of N · <screen word>" on every screen, and no screen's content runs under the bottom bar
// (a screen taller than the space scrolls inside its own frame). Walks every screen with Next.
//
//   node e2e/story-header.check.mjs [--base http://localhost:5173] [--path /stories/data-centers?state=AL&city=Tuscaloosa]
//
// Needs the app and its API running; it reads the page, it changes nothing. Exits 1 on any failure.
import { chromium } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const path = arg('path', '/stories/data-centers?state=AL&city=Tuscaloosa')
let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}
const intersects = (a, b) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
for (const [w, h] of [[360, 740], [412, 915]]) {
  console.log(`\n${w}x${h}`)
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' })
  const page = await ctx.newPage()
  await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-testid="story-scope-note"]', { timeout: 60_000 })
  await page.waitForTimeout(3000)

  const head = await page.locator('.stance-top .stance-sentence').boundingBox()
  const note = await page.locator('[data-testid="story-scope-note"]').boundingBox()
  ok(head && note && !intersects(head, note), 'the headline and the scope note do not intersect')
  ok(head && note && note.y >= head.y + head.height - 1, 'the note sits below the headline')
  const lineH = await page.locator('.stance-top .stance-sentence').evaluate((e) => parseFloat(getComputedStyle(e).lineHeight))
  ok(head.height <= lineH * 3 + 48, `the headline takes at most about three lines (${Math.round(head.height)}px)`)
  const short = await page.locator('[data-testid="story-scope-short"]').innerText()
  ok(/^Showing .+ · .+too few meetings/.test(short), `the note is one short line (${short})`)
  ok((await page.locator('[data-testid="story-scope-full"]').count()) === 0, 'the full reason is hidden until "Why?"')
  await page.locator('[data-testid="story-scope-why"]').click()
  ok((await page.locator('[data-testid="story-scope-full"]').count()) === 1, '"Why?" shows the full reason')
  const open = await page.locator('.stance-top').boundingBox()
  const noteOpen = await page.locator('[data-testid="story-scope-note"]').boundingBox()
  ok(!intersects(await page.locator('.stance-top .stance-sentence').boundingBox(), noteOpen), 'the opened note does not overlap the headline')
  await page.locator('[data-testid="story-scope-why"]').click()
  const bar = await page.locator('.stance-top').boundingBox()
  ok(bar.height <= h * 0.25, `the sticky bar is ${Math.round(bar.height)}px, at most 25% of ${h} (open: ${Math.round(open.height)}px)`)

  ok(await page.locator('[data-testid="story-summary"]').isVisible(), 'the first screen is the summary card')
  const facts = await page.locator('[data-testid="story-summary"] li').count()
  ok(facts >= 1 && facts <= 3, `the summary has ${facts} fact(s)`)

  // Every screen: the pager matches it, and its content stays above the bottom bar.
  const pager = page.locator('[data-testid="story-pager"]')
  const total = Number(((await pager.innerText()).match(/of (\d+)/) ?? [])[1])
  ok(total > 1, `the pager counts ${total} screens`)
  let prevAt = null
  for (let i = 0; i < total; i++) {
    if (prevAt === total) break
    await page.waitForTimeout(2000)
    const text = (await pager.innerText()).replace(/\s+/g, ' ').replace('▴', '').trim()
    const word = await page.evaluate(() => {
      const top = document.querySelector('.stance-top')?.getBoundingClientRect().bottom ?? 0
      const live = [...document.querySelectorAll('[data-panel]')].find((p) => p.hasAttribute('data-live')) ?? null
      return live?.querySelector(".stance-card-title")?.textContent?.trim() ?? null
    })
    const at = Number((text.match(/^(\d+) of/) ?? [])[1])
    ok(at > (prevAt ?? 0), `screen ${i + 1}: the pager moved forward (${at})`)
    prevAt = at
    ok(text.startsWith(`${at} of ${total} · `) && (word == null || text.endsWith(word)), `screen ${i + 1}: pager "${text}" matches "${word}"`)
    const fit = await page.evaluate(() => {
      const live = [...document.querySelectorAll('[data-panel]')].find((p) => p.hasAttribute('data-live'))
      const barTop = document.querySelector('[data-testid="story-bottombar"]')?.getBoundingClientRect().top ?? innerHeight
      const grid = live?.querySelector('.stance-grid')
      if (!grid) return { under: false, paged: true }
      // Scroll-independent: the frame is no taller than the room between the sticky bar and the bottom bar.
      const room = barTop - (document.querySelector('.stance-top')?.getBoundingClientRect().bottom ?? 0)
      return { under: grid.clientHeight > room + 2, paged: grid.scrollHeight <= grid.clientHeight + 1 || getComputedStyle(grid).overflowY !== 'visible' }
    })
    ok(!fit.under && fit.paged, `screen ${i + 1} ${JSON.stringify(fit)}: its frame ends above the bottom bar and scrolls inside itself`)
    if (i < total - 1) {
      await page.locator('.story-next-fixed').click()
      await page.waitForFunction((t) => !document.querySelector('[data-testid="story-pager"]')?.textContent?.startsWith(t), `${at} of`, { timeout: 8000 }).catch(() => {})
    }
  }
  // The list jumps.
  await pager.click()
  const items = await page.locator('[data-testid="story-pager-list"] button').count()
  ok(items === total, `the pager lists all ${total} screens`)
  await page.locator('[data-testid="story-pager-list"] button').first().click()
  await page.waitForTimeout(1200)
  ok((await pager.innerText()).startsWith(`1 of ${total}`), 'choosing the first screen in the list jumps back to it')
  await ctx.close()
}
await browser.close()
process.exit(failures ? 1 : 0)
