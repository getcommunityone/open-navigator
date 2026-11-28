// Story map check (#1277; replaces the #1229 tap-card check). The owner, 27 Nov 2026: "Change to not have popup — nothing
// on mobile. On desktop make the video start playing automatically with the card in the bottom left and no play button.
// Make it more obvious to click to drill down on the chart for that state using the box."
//
//   Phones (Pixel 7, iPhone 13): no card ever; the hint "Tap a state to open its story" shows under the map; a tap on a
//   state opens its story (the Overview narrows); on the county map a tap only lights that county.
//   Desktop (1440x900): hovering a state outlines it and shows ONE card beside the map (never over it: the home page's
//   text column, else under the legend), its recording an iframe
//   whose src has autoplay=1&mute=1; another state swaps it; leaving the map removes it; keyboard focus shows the card with
//   no autoplay; Enter and a click open the state's story.
//
//   node e2e/map-taps.check.mjs [--base http://localhost:5173] [--shots <dir>] [--only box,dot,desktop]
//
// Surfaces: a topic story's state box map (/stories/guns?state=AL), the home page map (/), and the Data Center story's
// Overview dot map and its county map (/stories/data-centers). It reads the page and changes nothing. Exits 1 on any failure.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', null)
const only = arg('only', null)
const run = (name) => !only || only.split(',').includes(name)
let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}
const shot = async (page, name) => {
  if (shots) await page.screenshot({ path: `${shots}/${name.replace(/[^a-z0-9-]+/gi, '_')}.png` })
}
// Software GL: on WSL the headless shell's GPU path can stop producing frames (no requestAnimationFrame, screenshots hang).
const browser = await chromium.launch({ args: ['--disable-gpu', '--disable-software-rasterizer', '--use-gl=swiftshader'] })
const here = (page) => page.url().replace(base, '')

// In the page: the map svg on screen for a selector (a story keeps other screens' maps in the DOM, hidden).
const VISIBLE = `(sel) => [...document.querySelectorAll(sel)].find((v) => v.getClientRects().length > 0 && v.getBoundingClientRect().width > 50) ?? null`

/** A point (the shape nearest the state's middle) for every state on the visible map. */
async function statePoints(page, sel) {
  await page.evaluate(([sel, visible]) => eval(visible)(sel)?.scrollIntoView({ block: 'center' }), [sel, VISIBLE])
  let last = null
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(200)
    const top = await page.evaluate(([sel, visible]) => Math.round(eval(visible)(sel)?.getBoundingClientRect().top ?? 0), [sel, VISIBLE])
    if (top === last) break
    last = top
  }
  return page.evaluate(
    ([sel, visible]) => {
      const svg = eval(visible)(sel)
      const pts = {}
      for (const el of svg?.querySelectorAll('[data-state]') ?? []) {
        const b = el.getBoundingClientRect()
        if (b.width < 1) continue
        ;(pts[el.getAttribute('data-state')] ??= []).push({ x: b.left + b.width / 2, y: b.top + b.height / 2 })
      }
      return Object.fromEntries(
        Object.entries(pts).map(([k, list]) => {
          const cx = list.reduce((a, p) => a + p.x, 0) / list.length
          const cy = list.reduce((a, p) => a + p.y, 0) / list.length
          list.sort((a, b) => (a.x - cx) ** 2 + (a.y - cy) ** 2 - ((b.x - cx) ** 2 + (b.y - cy) ** 2))
          return [k, list[0]]
        }),
      )
    },
    [sel, VISIBLE],
  )
}

/** What the visible map shows: the card (place, iframe src, where it sits), the lit state, the text under the map. */
function mapState(page, sel, readoutSel) {
  return page.evaluate(
    ([sel, readoutSel, visible]) => {
      const svg = eval(visible)(sel)
      const stage = svg?.parentElement
      const scope = svg?.closest('figure') ?? stage?.parentElement ?? document
      const cards = [...document.querySelectorAll('.map-hover-card')].filter((c) => c.getClientRects().length > 0)
      const card = cards[0] ?? null
      const svgBox = svg?.getBoundingClientRect()
      const cb = card?.getBoundingClientRect()
      const lit = [...(svg?.querySelectorAll('[data-active]') ?? [])]
      return {
        cards: cards.length,
        place: card?.querySelector('.qcard-where')?.textContent ?? null,
        quote: card?.querySelector('.qcard-quote')?.textContent?.trim() ?? null,
        iframes: document.querySelectorAll('.map-hover-card iframe').length,
        src: card?.querySelector('iframe')?.getAttribute('src') ?? null,
        playBtn: !!card?.querySelector('.qcard-play-btn'),
        open: card?.querySelector('.map-hover-open, .map-hover-here')?.textContent ?? null,
        // The card never covers the map (#1277): its box and the map's do not overlap.
        offMap: cb && svgBox ? cb.bottom <= svgBox.top + 1 || cb.top >= svgBox.bottom - 1 || cb.right <= svgBox.left + 1 || cb.left >= svgBox.right - 1 : null,
        lit: [...new Set(lit.map((e) => e.getAttribute('data-state')).filter(Boolean))],
        litCount: lit.length,
        outline: !!svg?.querySelector('[data-active-outline]'),
        drillCue: svg?.querySelector('[data-hover-drill-cue]')?.textContent ?? null,
        readout: scope.querySelector(readoutSel)?.textContent ?? '',
        close: !!document.querySelector('.map-card-close'),
      }
    },
    [sel, readoutSel, VISIBLE],
  )
}

/** Phone box map: the hint shows, no card ever, and each tap opens the tapped state's story. */
async function boxMapPhone(ctx, label, path, storyHref, codes) {
  const page = await ctx.newPage()
  await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
  const sel = 'svg[data-map-keys]'
  await page.waitForSelector(`${sel} rect[data-state]`, { timeout: 60_000 })
  await page.waitForTimeout(800)
  console.log(`\n${label} ${path} (state box map)`)
  let r = await mapState(page, sel, 'p.mt-1')
  ok(r.readout.includes('Tap a state to open its story'), `the hint shows under the map ("${r.readout.slice(-40)}")`)
  await shot(page, `${label}-${path}-hint`)
  for (const code of codes) {
    const pts = await statePoints(page, sel)
    if (!pts[code]) {
      ok(false, `${code} is on the map`)
      continue
    }
    await page.touchscreen.tap(pts[code].x, pts[code].y)
    await page.waitForTimeout(250)
    r = await mapState(page, sel, 'p.mt-1')
    ok(r.cards === 0 && r.iframes === 0 && !r.close, `tap ${code}: no card, no player, no Close (${r.cards} cards)`)
    await page.waitForURL((u) => u.toString().replace(base, '').startsWith(storyHref(code)), { timeout: 8000 }).catch(() => {})
    ok(here(page).startsWith(storyHref(code)), `tap ${code} opens its story at once (${here(page)})`)
    await page.waitForTimeout(1500)
    await page.waitForSelector(`${sel} rect[data-state]`, { timeout: 30_000 }).catch(() => {})
  }
  r = await mapState(page, sel, 'p.mt-1')
  ok(r.cards === 0, 'still no card after the story opened')
  await shot(page, `${label}-${path}-after-tap`)
  await page.close()
}

/** Data Center story Overview on a phone: a tap narrows to the state with no card; on the county map a tap lights a county. */
async function dotMapPhone(ctx, label) {
  const page = await ctx.newPage()
  await page.goto(base + '/stories/data-centers', { waitUntil: 'networkidle', timeout: 120_000 })
  console.log(`\n${label} /stories/data-centers (overview dot map and county map)`)
  const start = async () => {
    const s = page.locator('[data-cover] .home-story-start:visible')
    if (await s.count()) {
      await s.first().click()
      await page.waitForTimeout(1200)
    }
  }
  await start()
  const sel = 'svg[data-map="national"]'
  if (!(await page.waitForSelector(`${sel}:visible`, { timeout: 60_000 }).then(() => true, () => false))) {
    ok(false, 'overview dot map shows')
    return page.close()
  }
  let r = await mapState(page, sel, '.stance-map-readout')
  ok(r.readout.includes('Tap a state to open its story'), `the hint shows under the map ("${r.readout}")`)
  await shot(page, `${label}-dotmap-hint`)
  const pts = await statePoints(page, sel)
  await page.touchscreen.tap(pts.TX.x, pts.TX.y)
  await page.waitForTimeout(300)
  r = await mapState(page, sel, '.stance-map-readout')
  ok(r.cards === 0 && r.iframes === 0, `tap TX: no card (${r.cards})`)
  await page.waitForTimeout(800)
  ok(here(page).includes('state=TX'), `tap TX narrows the story at once (${here(page)})`)
  await start()
  const county = 'svg[data-map="county"]'
  if (!(await page.waitForSelector(`${county}:visible [data-box]`, { timeout: 30_000 }).then(() => true, () => false))) {
    ok(false, 'county map shows after narrowing')
    return page.close()
  }
  await page.evaluate(([county, visible]) => eval(visible)(county)?.scrollIntoView({ block: 'center' }), [county, VISIBLE])
  await page.waitForTimeout(1500)
  for (const [fx, fy] of [[0.3, 0.3], [0.7, 0.7], [0.5, 0.5]]) {
    const p = await page.evaluate(
      ([county, visible, fx, fy]) => {
        const svg = eval(visible)(county)
        const box = svg.getBoundingClientRect()
        const tx = box.left + box.width * fx
        const ty = box.top + box.height * fy
        let best = null
        let bd = Infinity
        ;[...svg.querySelectorAll('[data-box]')].forEach((c, i) => {
          const b = c.getBoundingClientRect()
          const dd = (b.left + b.width / 2 - tx) ** 2 + (b.top + b.height / 2 - ty) ** 2
          if (b.width > 0 && dd < bd) {
            bd = dd
            best = { i, x: b.left + b.width / 2, y: b.top + b.height / 2 }
          }
        })
        return best
      },
      [county, VISIBLE, fx, fy],
    )
    await page.touchscreen.tap(p.x, p.y)
    await page.waitForTimeout(500)
    const tapped = await page.evaluate(
      ([county, visible, i]) => eval(visible)(county).querySelectorAll('[data-box]')[i].hasAttribute('data-active'),
      [county, VISIBLE, p.i],
    )
    r = await mapState(page, county, '.stance-map-readout')
    ok(tapped && r.outline && r.cards === 0, `county tap at ${fx},${fy}: that county lit and outlined, no card (${r.readout.slice(0, 50)})`)
  }
  await shot(page, `${label}-countymap`)
  await page.close()
}

/** Desktop hover on any of the maps: bottom-left card with an autoplaying muted iframe, lit state, swap, leave. */
async function hoverChecks(page, sel, readoutSel, a, b, name) {
  let pts = await statePoints(page, sel)
  await page.mouse.move(pts[a].x, pts[a].y)
  await page.waitForTimeout(600)
  let r = await mapState(page, sel, readoutSel)
  ok(r.lit.length === 1 && r.lit[0] === a && r.litCount > 1 && r.outline, `hover ${a}: the whole state is lit and outlined (${r.litCount} shapes)`)
  ok(Boolean(r.drillCue && r.drillCue.includes('Click')), `  on-map drill-down pill shows ("${r.drillCue}")`)
  ok(r.cards === 1, `hover ${a}: one card (${r.cards}) · ${r.place}`)
  ok(r.offMap === true, '  the card is beside the map, not over it')
  if (r.src) {
    ok(r.src.includes('youtube-nocookie.com') && r.src.includes('autoplay=1&mute=1') && !r.playBtn, `  its recording autoplays muted, no play button (${r.src.slice(0, 90)})`)
  } else ok(!r.playBtn, '  this passage has no video id: quote only, no play button')
  ok(/^Click .+ to open|^Click to show|^You’re reading/.test(r.open ?? ''), `  it says how to drill in ("${r.open}")`)
  await shot(page, `desktop-${name}-hover-${a}`)
  const firstSrc = r.src
  pts = await statePoints(page, sel)
  await page.mouse.move(pts[b].x, pts[b].y)
  await page.waitForTimeout(600)
  r = await mapState(page, sel, readoutSel)
  ok(r.cards === 1 && r.iframes <= 1 && r.lit[0] === b, `hover ${b}: the card moves to ${b}, one player (${r.iframes}) · ${r.place}`)
  if (firstSrc && r.src) ok(r.src !== firstSrc, '  the video swapped')
  await shot(page, `desktop-${name}-hover-${b}`)
  await page.mouse.move(5, 5)
  // The card stays a moment so the mouse can reach its link, then goes.
  await page.waitForTimeout(900)
  r = await mapState(page, sel, readoutSel)
  ok(r.cards === 0 && r.iframes === 0 && !r.drillCue, 'leaving the map removes the card, its player and the drill-down pill')
}

async function desktop(ctx) {
  const page = await ctx.newPage()
  await page.goto(base + '/stories/guns?state=AL', { waitUntil: 'networkidle', timeout: 120_000 })
  const sel = 'svg[data-map-keys]'
  await page.waitForSelector(`${sel} rect[data-state]`, { timeout: 60_000 })
  console.log('\nDesktop 1440x900 /stories/guns?state=AL')
  await hoverChecks(page, sel, 'p.mt-1', 'TX', 'AZ', 'guns')
  // Keyboard: same card and highlight, but never autoplay from focus.
  await page.locator(sel).first().focus()
  await page.waitForTimeout(400)
  let r = await mapState(page, sel, 'p.mt-1')
  ok(r.readout.startsWith('Alabama:') && r.lit[0] === 'AL', `keyboard focus starts on the page's state (${r.readout.slice(0, 30)})`)
  ok(r.iframes === 0, `  no autoplay from keyboard focus (${r.playBtn ? 'still image with a play button' : 'no player'})`)
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(300)
  r = await mapState(page, sel, 'p.mt-1')
  ok(!r.readout.startsWith('Alabama:') && r.iframes === 0, `ArrowRight moves on, still no autoplay (${r.readout.slice(0, 30)})`)
  await shot(page, 'desktop-guns-keyboard')
  await page.keyboard.press('Escape')
  await page.waitForTimeout(300)
  ok((await mapState(page, sel, 'p.mt-1')).cards === 0, 'Escape hides the card')
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(300)
  const target = (await mapState(page, sel, 'p.mt-1')).lit[0]
  await page.keyboard.press('Enter')
  await page.waitForTimeout(1500)
  ok(here(page).includes(`state=${target}`), `Enter opens ${target}'s story (${here(page)})`)
  const pts = await statePoints(page, sel)
  await page.mouse.click(pts.OR.x, pts.OR.y)
  await page.waitForTimeout(1200)
  ok(here(page).includes('state=OR'), `a click on Oregon opens its story (${here(page)})`)
  await page.close()

  const home = await ctx.newPage()
  await home.goto(base + '/', { waitUntil: 'networkidle', timeout: 120_000 })
  await home.waitForSelector(`${sel} rect[data-state]`, { timeout: 60_000 })
  console.log('\nDesktop 1440x900 / (home)')
  await hoverChecks(home, sel, 'p.mt-1', 'TX', 'VA', 'home')
  // Moving across different bands/boxes within Texas switches the meeting card (#1357).
  const txSpread = await home.evaluate(
    ([sel, visible]) => {
      const svg = eval(visible)(sel)
      const list = [...(svg?.querySelectorAll('rect[data-state="TX"]') ?? [])]
        .map((el) => {
          const b = el.getBoundingClientRect()
          return { x: b.left + b.width / 2, y: b.top + b.height / 2, w: b.width }
        })
        .filter((p) => p.w >= 1)
        .sort((a, b) => a.x - b.x || a.y - b.y)
      if (list.length < 3) return null
      return [list[0], list[Math.floor(list.length / 2)], list[list.length - 1]]
    },
    [sel, VISIBLE],
  )
  if (txSpread) {
    const seenCards = new Set()
    for (const pt of txSpread) {
      await home.mouse.move(pt.x, pt.y)
      await home.waitForTimeout(350)
      const st = await mapState(home, sel, 'p.mt-1')
      seenCards.add(`${st.place ?? ''}|${st.quote ?? ''}|${st.src ?? ''}`)
    }
    ok(seenCards.size > 1, `hovering across TX boxes switches the meeting panel (${seenCards.size} distinct cards)`)
  } else ok(false, 'TX has multiple boxes on the home map')
  // A click on Alabama opens the Alabama story (the owner's report: it didn't).
  let hp = await statePoints(home, sel)
  await home.mouse.move(hp.AL.x - 40, hp.AL.y, { steps: 4 })
  await home.mouse.move(hp.AL.x, hp.AL.y, { steps: 4 })
  await home.waitForTimeout(600)
  await home.mouse.click(hp.AL.x, hp.AL.y)
  await home.waitForTimeout(1200)
  ok(here(home).startsWith('/stories/data-centers?state=AL'), `a click on Alabama on / opens its story (${here(home)})`)
  // #1367: the drill must open Overview, not a mid-story screen left from a prior visit / scroll race.
  {
    const u = new URL(home.url())
    ok(u.searchParams.get('screen') === 'overview', `Alabama drill carries screen=overview (${here(home)})`)
    await home.waitForSelector('.stance-pip-btn, [data-panel]', { timeout: 60_000 })
    await home.waitForTimeout(2500)
    const land = await home.evaluate(() => {
      const pip = [...document.querySelectorAll('.stance-pip-btn')].findIndex((b) => b.getAttribute('aria-current'))
      const eye = document.querySelector('.stance-eyebrow')?.textContent?.trim() ?? ''
      return { pip, eye, screen: new URLSearchParams(location.search).get('screen') }
    })
    ok(land.pip === 0 || land.eye === 'Overview' || land.screen === 'overview', `Alabama drill lands on Overview (pip=${land.pip}, eye=${land.eye}, screen=${land.screen})`)
  }
  // The card's link (in the text column) reaches the same story: hover Texas, cross to the card, click its link.
  await home.goto(base + '/', { waitUntil: 'networkidle', timeout: 120_000 })
  await home.waitForSelector(`${sel} rect[data-state]`, { timeout: 60_000 })
  hp = await statePoints(home, sel)
  await home.mouse.move(hp.TX.x, hp.TX.y)
  await home.waitForTimeout(600)
  const link = home.locator('.map-hover-card a.map-hover-open')
  if (await link.count()) {
    const lb = await link.boundingBox()
    await home.mouse.move(lb.x + 10, lb.y + lb.height / 2, { steps: 8 })
    await home.mouse.click(lb.x + 10, lb.y + lb.height / 2)
    await home.waitForTimeout(1200)
    ok(here(home).startsWith('/stories/data-centers?state=TX'), `the card's "Click Texas" link opens its story (${here(home)})`)
  } else ok(false, 'the card has a "Click Texas to open its story" link')
  await home.close()

  const dc = await ctx.newPage()
  await dc.goto(base + '/stories/data-centers', { waitUntil: 'networkidle', timeout: 120_000 })
  console.log('\nDesktop 1440x900 /stories/data-centers (Overview)')
  const s = dc.locator('[data-cover] .home-story-start:visible')
  if (await s.count()) {
    await s.first().click()
    await dc.waitForTimeout(1200)
  }
  const nat = 'svg[data-map="national"]'
  if (await dc.waitForSelector(`${nat}:visible`, { timeout: 60_000 }).then(() => true, () => false)) {
    await hoverChecks(dc, nat, '.stance-map-readout', 'TX', 'VA', 'datacenters')
    const p2 = await statePoints(dc, nat)
    await dc.mouse.click(p2.TX.x, p2.TX.y)
    await dc.waitForTimeout(1200)
    ok(here(dc).includes('state=TX'), `a click on Texas narrows the story (${here(dc)})`)
  } else ok(false, 'overview dot map shows')
  await dc.close()
}

for (const [label, desc] of [
  ['Pixel 7', devices['Pixel 7']],
  ['iPhone 13', devices['iPhone 13']],
]) {
  // Both on chromium; the descriptors give the viewport, touch and the no-hover / coarse-pointer media.
  const { defaultBrowserType: _engine, ...opts } = desc
  const ctx = await browser.newContext(opts)
  if (run('box')) await boxMapPhone(ctx, label, '/stories/guns?state=AL', (c) => `/stories/guns?state=${c}`, ['TX', 'OR'])
  if (run('box')) await boxMapPhone(ctx, label, '/', (c) => `/stories/data-centers?state=${c}`, ['TX'])
  if (run('dot')) await dotMapPhone(ctx, label)
  await ctx.close()
}
if (run('desktop')) {
  const desk = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await desktop(desk)
  await desk.close()
}
await browser.close()
if (failures) {
  console.error(`\n${failures} check(s) failed.`)
  process.exit(1)
}
console.log('\nPhones drill on a tap with no card; desktop hover shows the card beside the map playing the recording.')
