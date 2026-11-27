// Map taps check (#1229): on a phone, tapping states on the story maps, any number of times in any order, always shows the
// tapped state's card (or opens its story on a second tap of the shown state, #1223), and nothing depends on hover: a card a
// tap opened closes on its Close button or on a tap outside the map. Before, the map's svg took focus on the first tap, the
// keyboard hook (#1146) picked the page's own state, and that card stayed pinned: every later tap went unseen ("Once I click
// on one dot I can't click on a different one"). Also checks the desktop keyboard path still works.
//
//   node e2e/map-taps.check.mjs [--base http://localhost:5173] [--shots <dir>] [--only box,dot,desktop]
//
// Surfaces: a topic story's state box map (/stories/guns?state=AL), the home page map (/), and the Data Center story's
// overview dot map and its county map after the drill-down (/stories/data-centers). Devices: Pixel 7, iPhone 13 (on
// chromium) and a 1440x900 desktop. It reads the page and changes nothing. Exits 1 on any failure.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', null)
// --only box|dot|desktop: run one surface (all by default).
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

const STATE_NAMES = {
  OR: 'Oregon', TX: 'Texas', NY: 'New York', UT: 'Utah', GA: 'Georgia', CA: 'California', OH: 'Ohio', VA: 'Virginia',
  AZ: 'Arizona', WA: 'Washington', FL: 'Florida', PA: 'Pennsylvania', IL: 'Illinois', NC: 'North Carolina', MI: 'Michigan',
  CO: 'Colorado', MN: 'Minnesota', AL: 'Alabama',
}

// In the page: the map svg on screen for a selector (a story keeps other screens' maps in the DOM, hidden).
const VISIBLE = `(sel) => [...document.querySelectorAll(sel)].find((v) => v.getClientRects().length > 0 && v.getBoundingClientRect().width > 50) ?? null`

/** A tap point (the box nearest the state's middle) for every state on the visible map. */
async function statePoints(page, sel) {
  // Scrolled by the page, not Playwright's stability wait: a story's map may keep a gentle motion going.
  await page.evaluate(([sel, visible]) => eval(visible)(sel)?.scrollIntoView({ block: 'center' }), [sel, VISIBLE])
  // Wait until the map stops moving (a screen arriving or a smooth scroll), so the tap lands where it was aimed.
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

/** What the visible map shows: the readout line, the card's place, the outlined box's state. */
function mapState(page, sel, readoutSel, cardSel) {
  return page.evaluate(
    ([sel, readoutSel, cardSel, visible]) => {
      const svg = eval(visible)(sel)
      const scope = svg?.closest('figure') ?? svg?.parentElement?.parentElement ?? document
      const stage = svg?.parentElement
      const card = stage?.querySelector(cardSel)
      return {
        readout: scope.querySelector(readoutSel)?.textContent ?? '',
        card: card ? card.querySelector('.qcard-where')?.textContent ?? '(card)' : null,
        outlined: svg?.querySelector('rect[stroke="#1c1917"]')?.getAttribute('data-state') ?? null,
        close: !!stage?.querySelector('.map-card-close'),
      }
    },
    [sel, readoutSel, cardSel, VISIBLE],
  )
}

/** Tap somewhere plain outside the map: the page's first heading (text, not a link or control). */
async function tapOutside(page) {
  const b = await page.evaluate(() => {
    // A plain spot on screen: the point's own element is text, not a link, control, map or card.
    const plain = (x, y) => {
      const el = document.elementFromPoint(x, y)
      return el && !el.closest('a, button, input, select, label, summary, svg, figure, [role="button"], .home-map-card, .stance-map-stage, .stance-map-card')
    }
    for (const el of document.querySelectorAll('h1, h2, h3, p')) {
      const r = el.getBoundingClientRect()
      if (r.width < 40 || r.top < 80 || r.bottom > innerHeight - 80) continue
      for (const fx of [0.5, 0.25, 0.75, 0.1]) {
        const x = r.left + r.width * fx
        const y = r.top + Math.min(10, r.height / 2)
        if (plain(x, y)) return { x, y }
      }
    }
    return null
  })
  if (!b) return ok(false, 'found a plain spot outside the map to tap')
  await page.touchscreen.tap(b.x, b.y)
  await page.waitForTimeout(500)
}

/** Box map (StoryStatesMap): A, B, C, B, A, D each show their own card; Close and a tap outside close it; a second tap on
 *  the shown state opens its story; after that, taps keep switching. */
async function boxMap(ctx, label, path, storyHref) {
  const page = await ctx.newPage()
  await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
  const sel = 'svg[data-map-keys]'
  await page.waitForSelector(`${sel} rect[data-state]`, { timeout: 60_000 })
  await page.waitForTimeout(800)
  console.log(`\n${label} ${path} (state box map)`)
  const look = () => mapState(page, sel, 'p.mt-1', '.home-map-card')
  const startUrl = here(page)
  const order = ['OR', 'TX', 'NY', 'UT', 'GA', 'CA', 'OH', 'VA', 'AZ', 'WA', 'FL', 'PA', 'IL', 'NC', 'MI', 'CO', 'MN']
  const present = order.filter((c) => c in STATE_NAMES)
  const tap = async (code) => {
    const pts = await statePoints(page, sel)
    if (!pts[code]) return null
    await page.touchscreen.tap(pts[code].x, pts[code].y)
    await page.waitForTimeout(600)
    return look()
  }
  const [a, b, c, d, e, f] = present
  for (const code of [a, b, c, b, a, d]) {
    const r = await tap(code)
    const shows = r && r.readout.startsWith(`${STATE_NAMES[code]}:`)
    const opened = here(page) !== startUrl
    ok(shows && !opened, `tap ${code}: ${shows ? `card ${r.card}, outline on ${r.outlined}` : `STUCK or left: readout "${r?.readout.slice(0, 40)}", url ${here(page)}`}`)
    if (shows) ok(r.outlined === code, `  outline is on the tapped state (${r.outlined})`)
    if (opened) return page.close()
  }
  await shot(page, `${label}-${path}-card`)
  let r = await look()
  ok(r.close, 'the card has a Close button')
  await page.locator(`${sel}:visible`).first().locator('xpath=..').locator('.map-card-close').click()
  await page.waitForTimeout(400)
  r = await look()
  ok(!r.card && !r.outlined, `Close closes the card (${r.card ?? 'no card'})`)
  await tap(e)
  await tapOutside(page)
  r = await look()
  ok(!r.card && !r.outlined && here(page) === startUrl, `a tap outside the map closes the card (${r.card ?? 'no card'})`)
  await tap(d)
  r = await tap(d)
  ok(here(page).startsWith(storyHref(d)), `second tap on ${d} opens its story (${here(page)})`)
  if (path.startsWith('/stories/') && here(page).startsWith('/stories/')) {
    await page.waitForTimeout(1200)
    const now = here(page)
    for (const code of [e, f, e]) {
      const r2 = await tap(code)
      ok(r2 && r2.readout.startsWith(`${STATE_NAMES[code]}:`) && here(page) === now, `after opening ${d}, tap ${code}: ${r2?.card ?? r2?.readout.slice(0, 40)}`)
    }
  }
  await page.close()
}

/** Data Center story overview (StoryDotMap in MapDrill): a tap shows the state's card (or, with no passage, narrows), taps
 *  switch, Close and a tap outside close it, a second tap narrows; then the county map's taps switch and close the same. */
async function dotMap(ctx, label) {
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
  const ready = await page.waitForSelector(`${sel}:visible`, { timeout: 60_000 }).then(() => true, () => false)
  if (!ready) {
    ok(false, 'overview dot map shows')
    return page.close()
  }
  const look = () => mapState(page, sel, '.stance-map-readout', '.stance-map-card')
  const startUrl = here(page)
  const tap = async (code) => {
    const pts = await statePoints(page, sel)
    if (!pts[code]) return null
    await page.touchscreen.tap(pts[code].x, pts[code].y)
    await page.waitForTimeout(700)
    return look()
  }
  for (const code of ['TX', 'OR', 'NY', 'OR', 'VA']) {
    const r = await tap(code)
    if (here(page) !== startUrl) {
      // A state with no passage in scope narrows at once (#1120). The rest of this sequence needs states with passages,
      // so this is a failure, not a quiet pass: pick other states if the data changed.
      ok(false, `tap ${code}: no passage, story narrowed at once (${here(page)}); the Close, outside-tap and county checks did not run`)
      return page.close()
    }
    ok(r && r.readout.startsWith(`${STATE_NAMES[code]}:`), `tap ${code}: shows ${r?.readout.slice(0, 40)} · card ${r?.card}`)
  }
  await shot(page, `${label}-dotmap-card`)
  let r = await look()
  ok(r.card && r.close, 'the card has a Close button')
  if (r.close) {
    await page.locator(`${sel}:visible`).first().locator('xpath=..').locator('.stance-map-card .map-card-close').click()
    await page.waitForTimeout(400)
    r = await look()
    ok(!r.card, 'Close closes the card')
  }
  await tap('TX')
  await tapOutside(page)
  r = await look()
  ok(!r.card && here(page) === startUrl, `a tap outside the map closes the card (${r.card ?? 'no card'})`)
  await tap('TX')
  await tap('TX')
  ok(here(page).includes('state=TX'), `second tap on TX narrows the story (${here(page)})`)
  // A new scope may show the cover again (#1182): Start goes on to the overview, now the state's county map (the drill).
  await start()
  const county = 'svg[data-map="county"]'
  const cready = await page.waitForSelector(`${county}:visible circle[data-box]`, { timeout: 30_000 }).then(() => true, () => false)
  if (!cready) {
    ok(false, 'county map shows after narrowing')
    return page.close()
  }
  await page.evaluate(([county, visible]) => eval(visible)(county)?.scrollIntoView({ block: 'center' }), [county, VISIBLE])
  await page.waitForTimeout(400)
  const lit = () =>
    page.evaluate(
      ([county, visible]) => {
        const svg = eval(visible)(county)
        const dots = [...svg.querySelectorAll('circle[data-box]')]
        return { bright: dots.filter((c) => c.getAttribute('opacity') === '1').length, all: dots.length }
      },
      [county, VISIBLE],
    )
  for (const [fx, fy] of [[0.25, 0.3], [0.75, 0.7], [0.5, 0.5], [0.25, 0.3]]) {
    // The drill canvas may still run: a tap during it jumps to the end and must still reach the map.
    const p = await page.evaluate(
      ([county, visible, fx, fy]) => {
        const svg = eval(visible)(county)
        const box = svg.getBoundingClientRect()
        const tx = box.left + box.width * fx
        const ty = box.top + box.height * fy
        let best = null
        let bd = Infinity
        ;[...svg.querySelectorAll('circle[data-box]')].forEach((c, i) => {
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
      ([county, visible, i]) => eval(visible)(county).querySelectorAll('circle[data-box]')[i].getAttribute('opacity'),
      [county, VISIBLE, p.i],
    )
    const l = await lit()
    ok(tapped === '1' && l.bright < l.all, `  county tap at ${fx},${fy}: its county lit (${l.bright}/${l.all} dots bright)`)
  }
  await shot(page, `${label}-countymap`)
  await tapOutside(page)
  const l = await lit()
  ok(l.bright === l.all, `a tap outside the county map closes it (${l.bright}/${l.all} bright)`)
  await page.close()
}

/** Desktop (#1146): Tab focus starts on the page's state, arrows move, Enter opens; a click opens; hover still shows. */
async function desktop(ctx) {
  const page = await ctx.newPage()
  await page.goto(base + '/stories/guns?state=AL', { waitUntil: 'networkidle', timeout: 120_000 })
  const sel = 'svg[data-map-keys]'
  await page.waitForSelector(`${sel} rect[data-state]`, { timeout: 60_000 })
  console.log('\nDesktop 1440x900 /stories/guns?state=AL')
  const caption = async () => (await mapState(page, sel, 'p.mt-1', '.home-map-card')).readout
  await page.locator(sel).first().focus()
  await page.waitForTimeout(300)
  const first = await caption()
  ok(first.startsWith('Alabama:'), `keyboard focus starts on the page's state (${first.slice(0, 30)})`)
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(300)
  const moved = await caption()
  ok(moved && moved !== first, `ArrowRight moves to the next state (${moved.slice(0, 30)})`)
  await page.keyboard.press('ArrowLeft')
  await page.waitForTimeout(300)
  ok((await caption()).startsWith('Alabama:'), 'ArrowLeft moves back')
  await page.keyboard.press('Escape')
  await page.waitForTimeout(300)
  ok(!(await mapState(page, sel, 'p.mt-1', '.home-map-card')).card, 'Escape hides the card')
  // A click outside closes a card the keyboard opened, as a tap does on a phone.
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(300)
  await page.mouse.click(8, 300)
  await page.waitForTimeout(300)
  ok(!(await mapState(page, sel, 'p.mt-1', '.home-map-card')).card, 'a click outside the map closes the card')
  await page.locator(sel).first().focus()
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(300)
  const target = (await caption()).split(':')[0]
  const code = Object.entries(STATE_NAMES).find(([, n]) => n === target)?.[0]
  await page.keyboard.press('Enter')
  await page.waitForTimeout(1500)
  ok(code ? here(page).includes(`state=${code}`) : /state=(?!AL)/.test(here(page)), `Enter opens ${target}'s story (${here(page)})`)
  let pts = await statePoints(page, sel)
  await page.mouse.move(pts.TX.x, pts.TX.y)
  await page.waitForTimeout(400)
  ok((await caption()).startsWith('Texas:'), 'hovering Texas shows its card')
  const s = await mapState(page, sel, 'p.mt-1', '.home-map-card')
  ok(!s.close, 'no Close button on desktop (the mouse leaving closes it)')
  pts = await statePoints(page, sel)
  await page.mouse.click(pts.OR.x, pts.OR.y)
  await page.waitForTimeout(1000)
  ok(here(page).includes('state=OR'), `a click on Oregon opens its story (${here(page)})`)
  await page.close()
}

for (const [label, desc] of [
  ['Pixel 7', devices['Pixel 7']],
  ['iPhone 13', devices['iPhone 13']],
]) {
  // Both on chromium (the only engine installed); the descriptors give the viewport, touch and no-hover media.
  const { defaultBrowserType: _engine, ...opts } = desc
  const ctx = await browser.newContext(opts)
  if (run('box')) await boxMap(ctx, label, '/stories/guns?state=AL', (c) => `/stories/guns?state=${c}`)
  if (run('box')) await boxMap(ctx, label, '/', (c) => `/stories/data-centers?state=${c}`)
  if (run('dot')) await dotMap(ctx, label)
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
console.log('\nEvery tap showed its own state, and every card closed on a tap.')
