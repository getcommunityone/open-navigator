// Story flow check (#1234, #1208): how a reader gets into and moves through the Data Center Story.
//   1. Home's Start opens the story on the Overview (no second Start), at national, state and city scope.
//   2. `?screen=<id>` deep links open that screen.
//   3. Every progress segment "N of M: <name>" opens <name> (1440x900), also when pressed as soon as the bar shows.
//   4. Phones (Pixel 7, iPhone 13): the bottom bar has Back ("Back: <previous>", >= 44px) from the second screen, none on
//      the first; a swipe left moves to the next screen and a swipe right back; a vertical swipe never turns a screen.
//   5. Titles are short, with no "AI reading" text and no count, and the Overview never repeats the title.
//   6. (owner 2026-11-27) Close (×) sits at the same top-right box on the cover and every screen, and the one fixed Next at
//      the same bottom-right box, at Pixel 7, iPhone 13 and 1440x900; the last screen's Next is a quiet "Done"; no
//      "← Data stories", no "Showing:" row, no Next story button; Close and Escape go home with the place kept.
//
//   node e2e/story-flow.check.mjs [--base http://localhost:5173] [--shots <dir>]
//
// Exits 1 on a failure. Needs the app (and its API) running; it reads the page, it changes nothing.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', null)
const SCOPES = ['', '?state=AL', '?state=AL&city=Tuscaloosa']
let failures = 0
const check = (ok, what) => {
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`)
  if (!ok) failures += 1
}
const shot = async (page, name) => shots && page.screenshot({ path: `${shots}/${name}.png` })

// Software GL: on some machines (WSL after a restart) headless Chromium produces no frames with the default GPU path,
// so screenshots and clicks wait forever.
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
const state = (page) =>
  page.evaluate(() => ({
    label: document.querySelector('[data-testid="stance-current"]')?.textContent?.trim() ?? '',
    url: location.pathname + location.search,
    h1: document.querySelector('.stance-top h1, .stance-top [role="heading"]')?.textContent?.replace('▾', '').trim() ?? '',
    overview: document.querySelector('[data-panel="0"] h2')?.textContent?.trim() ?? '',
    back: (() => {
      const b = document.querySelector('.story-bottombar-back')
      if (!b || !b.getClientRects().length) return null
      const r = b.getBoundingClientRect()
      return { name: b.getAttribute('aria-label'), w: Math.round(r.width), h: Math.round(r.height) }
    })(),
    eyebrows: [...document.querySelectorAll('section[data-panel]')].map((s) => s.getAttribute('data-screen')),
  }))
const settle = (page, ms = 3000) => page.waitForTimeout(ms)

// 1 + 5. Home Start lands on the Overview; titles short and plain.
for (const [dev, opts] of [['pixel7', devices['Pixel 7']], ['desk', { viewport: { width: 1440, height: 900 } }]]) {
  for (const q of SCOPES) {
    console.log(`\n${dev} home${q} -> Start`)
    const ctx = await browser.newContext(opts)
    const page = await ctx.newPage()
    await page.goto(`${base}/${q}`, { waitUntil: 'networkidle', timeout: 120_000 })
    await page.waitForFunction(() => !document.querySelector('#home-story-dc[aria-busy]'), null, { timeout: 60_000 })
    const homeTitle = (await page.locator('#home-story-dc').first().textContent())?.replace('▾', '').trim() ?? ''
    check(homeTitle.length <= 70 && !/AI read|\d/.test(homeTitle), `home title short and plain: "${homeTitle}"`)
    await shot(page, `${dev}-home${q.replace(/[^a-z]+/gi, '_')}`)
    await page.locator('.home-story-start').first().click()
    await page.waitForSelector('[data-panel="0"]', { state: 'attached', timeout: 60_000 })
    await settle(page, 4000)
    const s = await state(page)
    check(s.label === 'Overview' && /screen=overview/.test(s.url), `lands on the Overview (${s.label}, ${s.url})`)
    check(!s.overview || s.overview.replace(/\W/g, '') !== s.h1.replace(/\W/g, ''), `Overview headline is not the title: "${s.overview}"`)
    await shot(page, `${dev}-start${q.replace(/[^a-z]+/gi, '_')}`)
    await ctx.close()
  }
}

// 2. Deep links.
const desk = await browser.newContext({ viewport: { width: 1440, height: 900 } })
console.log('\ndeep links')
for (const [screen, label] of [['meetings', 'Meetings'], ['concerns', 'Concerns'], ['voices', 'Who spoke up']]) {
  const page = await desk.newPage()
  await page.goto(`${base}/stories/data-centers?state=AL&screen=${screen}`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForFunction(() => document.querySelector('[data-testid="stance-current"]')?.textContent, null, { timeout: 120_000 })
  await settle(page, 5000)
  const s = await state(page)
  check(s.label === label, `?screen=${screen} opens ${label} (got ${s.label})`)
  await page.close()
}

// 3. Every segment, from the cover, and one pressed as soon as the bar shows (#1208).
console.log('\nsegments')
{
  const page = await desk.newPage()
  await page.goto(`${base}/stories/data-centers?state=AL`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-testid="stance-pips"] button', { timeout: 120_000 })
  await settle(page, 5000)
  const segs = page.locator('[data-testid="stance-pips"] button')
  const count = await segs.count()
  for (let i = 0; i < count; i++) {
    const name = (await segs.nth(i).getAttribute('aria-label')) ?? ''
    await segs.nth(i).click()
    await settle(page, 2200)
    const s = await state(page)
    check(name.endsWith(`: ${s.label}`), `${name} -> ${s.label}`)
  }
  await page.close()
}
for (const q of SCOPES) {
  const page = await desk.newPage()
  await page.goto(`${base}/stories/data-centers${q}`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="stance-pips"] button', { timeout: 120_000 })
  const segs = page.locator('[data-testid="stance-pips"] button')
  const k = Math.min(6, (await segs.count()) - 1)
  const name = (await segs.nth(k).getAttribute('aria-label')) ?? ''
  await segs.nth(k).click()
  await settle(page, 6000)
  const s = await state(page)
  check(name.endsWith(`: ${s.label}`), `early ${q || '(national)'}: ${name} -> ${s.label}`)
  await page.close()
}
await desk.close()

// 4. Phones: Back in the bar, swipes.
const swipe = (page, dx, dy) =>
  page.evaluate(
    ([dx, dy]) => {
      // A touch on the screen's heading area (not a chart or map), moved by (dx, dy).
      const panel = [...document.querySelectorAll('section[data-panel]')].find((s) => {
        const r = s.getBoundingClientRect()
        return r.top < innerHeight / 2 && r.bottom > innerHeight / 2
      })
      const el = panel?.querySelector('h2') ?? panel ?? document.body
      const r = el.getBoundingClientRect()
      const x = Math.min(Math.max(r.left + r.width / 2, 60), innerWidth - 60)
      const y = r.top + Math.min(r.height / 2, 20)
      const touch = (cx, cy) => new Touch({ identifier: 1, target: el, clientX: cx, clientY: cy })
      el.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, touches: [touch(x, y)], changedTouches: [touch(x, y)] }))
      el.dispatchEvent(new TouchEvent('touchend', { bubbles: true, touches: [], changedTouches: [touch(x + dx, y + dy)] }))
    },
    [dx, dy],
  )
for (const [dev, opts] of [['pixel7', devices['Pixel 7']], ['iphone13', devices['iPhone 13']]]) {
  console.log(`\n${dev} phone bar and swipe`)
  const ctx = await browser.newContext(opts)
  const page = await ctx.newPage()
  await page.goto(`${base}/stories/data-centers?state=AL&screen=overview`, { waitUntil: 'networkidle', timeout: 120_000 })
  await settle(page, 3500)
  let s = await state(page)
  check(s.label === 'Overview' && s.back == null, `first screen: no Back (${s.label})`)
  await swipe(page, -160, 8)
  await settle(page)
  s = await state(page)
  check(s.label === 'Who spoke up', `swipe left -> next (${s.label})`)
  check(Boolean(s.back) && s.back.name === 'Back: Overview' && s.back.w >= 44 && s.back.h >= 44, `Back in the bar: ${JSON.stringify(s.back)}`)
  await shot(page, `${dev}-bar-back`)
  await swipe(page, -160, 8)
  await settle(page)
  s = await state(page)
  const after2 = s.label
  await swipe(page, 10, -220) // vertical: never a screen turn by the swipe hook
  await settle(page, 1200)
  await swipe(page, 170, 6)
  await settle(page)
  s = await state(page)
  check(s.label === 'Who spoke up', `swipe right -> back (from ${after2} to ${s.label})`)
  await page.locator('.story-bottombar-back').click()
  await settle(page)
  s = await state(page)
  check(s.label === 'Overview', `Back button -> ${s.label}`)
  await shot(page, `${dev}-after-back`)
  await ctx.close()
}

// 6. Close top right, Next bottom right, on every screen.
const boxOf = (page, sel) =>
  page.evaluate((sel) => {
    const el = document.querySelector(sel)
    if (!el || !el.getClientRects().length) return null
    const r = el.getBoundingClientRect()
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), r: Math.round(innerWidth - r.right), b: Math.round(innerHeight - r.bottom), text: el.textContent.trim() }
  }, sel)
const near = (a, b, tol = 2) => a && b && Math.abs(a.r - b.r) <= tol && Math.abs(a.b - b.b) <= tol && Math.abs(a.h - b.h) <= tol
const sameTopRight = (a, b, tol = 2) => a && b && Math.abs(a.r - b.r) <= tol && Math.abs(a.y - b.y) <= tol && a.w === b.w && a.h === b.h
for (const [dev, opts] of [['pixel7', devices['Pixel 7']], ['iphone13', devices['iPhone 13']], ['desk', { viewport: { width: 1440, height: 900 } }]]) {
  console.log(`\n${dev} Close and Next on every screen`)
  const ctx = await browser.newContext(opts)
  const page = await ctx.newPage()
  await page.goto(`${base}/stories/data-centers?state=TX`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-testid="story-close"]', { timeout: 120_000 })
  await page.waitForSelector('[data-testid="story-next"]', { timeout: 120_000 })
  await settle(page, 4000)
  const header = await page.evaluate(() => ({
    crumb: [...document.querySelectorAll('.stance-top a')].some((a) => /Data stories/.test(a.textContent)),
    showing: Boolean(document.querySelector('[data-testid="stance-scope"]')),
    pair: Boolean(document.querySelector('[data-cover] .home-story-next, [data-cover] .home-story-start')),
  }))
  check(!header.crumb && !header.showing && !header.pair, `header: no "← Data stories", no Showing row, no cover button pair ${JSON.stringify(header)}`)
  const close0 = await boxOf(page, '[data-testid="story-close"]')
  const next0 = await boxOf(page, '[data-testid="story-next"]')
  check(close0 && close0.w >= 44 && close0.h >= 44 && close0.r <= 32, `Close top right, 44px: ${JSON.stringify(close0)}`)
  check(next0 && next0.h >= 44 && next0.r <= 40 && next0.b <= 40 && /^Next/.test(next0.text), `Next bottom right on the cover: ${JSON.stringify(next0)}`)
  await shot(page, `${dev}-close-next-cover`)
  const n = await page.locator('section[data-panel]').count()
  // The sticky bar sits under the site header, which is taller at the top of the page (the cover): Close keeps its right
  // edge and size there, and its exact box on every screen after.
  let closeRef = null
  for (let i = 0; i < n; i++) {
    await page.locator('[data-testid="story-next"]').click()
    await settle(page, 2200)
    const c = await boxOf(page, '[data-testid="story-close"]')
    const x = await boxOf(page, '[data-testid="story-next"]')
    const label = (await state(page)).label
    const last = i === n - 1
    closeRef ??= c
    const coverLike = c && close0 && Math.abs(c.r - close0.r) <= 2 && c.w === close0.w && c.h === close0.h
    if (!last) {
      check(coverLike && sameTopRight(c, closeRef) && near(x, next0) && /^Next/.test(x?.text ?? ''), `screen ${i + 1} ${label}: Close ${JSON.stringify(c)} Next ${JSON.stringify(x)}`)
    } else {
      check(coverLike && sameTopRight(c, closeRef) && x && /^Done/.test(x.text) && x.r <= 40 && x.b <= 40, `last screen ${label}: quiet Done ${JSON.stringify(x)}`)
      await shot(page, `${dev}-last-screen`)
      break
    }
  }
  await page.locator('[data-testid="story-close"]').click()
  await settle(page, 2500)
  const url = await page.evaluate(() => location.pathname + location.search + location.hash)
  check(/^\/\?state=TX#data-stories$/.test(url), `Close goes home with the place: ${url}`)
  await page.goto(`${base}/stories/data-centers?state=AL&city=Tuscaloosa&screen=overview`, { waitUntil: 'networkidle', timeout: 120_000 })
  await settle(page, 3000)
  await page.keyboard.press('Escape')
  await settle(page, 2500)
  const url2 = await page.evaluate(() => location.pathname + location.search + location.hash)
  check(/^\/\?state=AL&city=Tuscaloosa#data-stories$/.test(url2), `Escape closes, place kept: ${url2}`)
  await ctx.close()
}

await browser.close()
if (failures) {
  console.error(`\n${failures} check(s) failed.`)
  process.exit(1)
}
console.log('\nAll story flow checks pass.')
