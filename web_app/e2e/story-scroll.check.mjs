// Story scroll check (#1325): scrolling inside a screen, and opening or closing a drill sheet, never changes the
// story's screen (`?screen=`). On a Pixel 7 sized phone it (1) scrolls a long screen's own scroller to the bottom by wheel
// and by touch, and (2) opens a KPI drill sheet, wheels and pages inside it, and closes it, asserting `?screen=` is the same
// throughout. The screen only changes on Next/Back, a sideways swipe, a key or a progress segment.
//
//   node e2e/story-scroll.check.mjs [--base http://localhost:5173] [--long /stories/guns?state=AL&screen=decided] [--sheet /stories/data-centers?state=AL&screen=voices]
//
// Needs the app (and its API) running; it reads the page, it changes nothing. Exits 1 on a mismatch.
import { chromium } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const longPath = arg('long', '/stories/guns?state=AL&screen=decided')
const sheetPath = arg('sheet', '/stories/data-centers?state=AL&screen=voices')

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
const context = await browser.newContext({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2.6, isMobile: true, hasTouch: true })
let failures = 0
const fail = (m) => {
  failures += 1
  console.log(`FAIL ${m}`)
}

async function open(path) {
  const page = await context.newPage()
  await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-panel]', { state: 'attached', timeout: 60_000 })
  await page.waitForTimeout(5000)
  const screen = () => new URL(page.url()).searchParams.get('screen')
  return { page, screen }
}

// 1. A long screen scrolls within itself.
{
  const { page, screen } = await open(longPath)
  const want = screen()
  const idx = await page.evaluate(() => {
    const top = document.querySelector('.stance-top')?.getBoundingClientRect().bottom ?? 0
    const ps = [...document.querySelectorAll('[data-panel]')]
    return ps.findIndex((p) => Math.abs(p.getBoundingClientRect().top - top) < 40)
  })
  const grid = () => page.locator('[data-panel] .stance-grid').nth(idx)
  const info = await grid().evaluate((g) => ({ sh: g.scrollHeight, ch: g.clientHeight }))
  if (idx < 0 || info.sh <= info.ch + 50) fail(`${longPath}: the screen has no long scroller to check (${JSON.stringify(info)})`)
  const bb = await grid().boundingBox()
  await page.mouse.move(bb.x + bb.width / 2, bb.y + 200)
  for (let i = 0; i < 16; i++) {
    await page.mouse.wheel(0, 300)
    await page.waitForTimeout(250)
  }
  const cdp = await context.newCDPSession(page)
  for (let i = 0; i < 6; i++) {
    await cdp.send('Input.synthesizeScrollGesture', { x: 200, y: 600, yDistance: -300, gestureSourceType: 'touch', speed: 900 })
    await page.waitForTimeout(400)
  }
  await page.waitForTimeout(800)
  const atEnd = await grid().evaluate((g) => g.scrollTop + g.clientHeight >= g.scrollHeight - 2)
  if (!atEnd) fail('the long screen did not scroll to its bottom')
  if (screen() !== want) fail(`scrolling to the bottom of "${want}" changed ?screen= to "${screen()}"`)
  else console.log(`ok   scrolled "${want}" to its bottom; ?screen= unchanged`)
  await page.close()
}

// 2. A drill sheet opens and closes without a screen change.
{
  const { page, screen } = await open(sheetPath)
  await page.waitForSelector('.kpi-drill-value', { state: 'attached', timeout: 60_000 })
  await page.waitForTimeout(2000)
  const want = screen()
  const value = page.locator('.kpi-drill-value').first()
  await value.scrollIntoViewIfNeeded()
  await page.waitForTimeout(600)
  if (screen() !== want) fail(`bringing the number into view changed ?screen= to "${screen()}"`)
  await value.tap()
  await page.waitForSelector('[data-testid="kpi-drill"]')
  await page.waitForTimeout(1200)
  const box = await page.locator('[data-testid="kpi-drill"]').boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  for (let i = 0; i < 12; i++) {
    await page.mouse.wheel(0, 400)
    await page.waitForTimeout(200)
  }
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('PageDown')
  await page.waitForTimeout(800)
  if (screen() !== want) fail(`opening and scrolling the sheet changed ?screen= to "${screen()}"`)
  await page.locator('.kpi-drill-close').tap()
  await page.waitForTimeout(1200)
  if (screen() !== want) fail(`closing the sheet changed ?screen= to "${screen()}"`)
  else console.log(`ok   opened, scrolled and closed a sheet on "${want}"; ?screen= unchanged`)
  await page.close()
}

// 3. Drilling into a place lands on Overview (#1325), from the map and from another screen, on a laptop.
{
  const desk = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await desk.newPage()
  const screen = () => new URL(page.url()).searchParams.get('screen')
  const label = () => page.evaluate(() => document.querySelector('.stance-top [aria-current]')?.getAttribute('aria-label') ?? '')
  await page.goto(base + '/stories/data-centers', { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForTimeout(5000)
  await page.locator('select[aria-label="Show one state"]').first().selectOption('AL')
  await page.waitForTimeout(4000)
  if (screen() !== 'overview' || !/Overview/.test(await label())) fail(`picking Alabama on the map landed on "${screen()}" / "${await label()}", not Overview`)
  else console.log('ok   picking Alabama on the map lands on Overview')
  // From another screen (a stale ?screen=), "National" in the header returns to Overview too.
  await page.goto(base + '/stories/data-centers?state=AL&screen=sites', { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForTimeout(5000)
  if (!/Sites/.test(await label())) fail(`?screen=sites did not open on Sites ("${await label()}")`)
  const national = page.getByRole('button', { name: /National/ }).first()
  if (await national.count()) {
    await national.click()
    await page.waitForTimeout(4000)
    if (screen() !== 'overview' || !/Overview/.test(await label())) fail(`broadening to National landed on "${screen()}" / "${await label()}", not Overview`)
    else console.log('ok   broadening to National from Sites lands on Overview')
  } else console.log('skip no National button found')
  await desk.close()
}

await browser.close()
if (failures) process.exit(1)
