// Place scope check (#1285). With Tuscaloosa, AL chosen the home map zooms to Alabama with Tuscaloosa marked, the subtitle
// says why the story steps up (too few meetings), and the header's "× National" puts the page back on the US map, on a
// desktop and on a phone. The Data Center Story notes the step up under its bar while the URL keeps the reader's choice.
//
//   node e2e/place-scope.check.mjs [--base http://localhost:5173] [--shots <dir>]
//
// It reads the page and changes nothing. Exits 1 on any failure. The checks follow the live counts: a city with 5 or more
// meetings would not step up.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', null)
let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}
const browser = await chromium.launch({ args: ['--disable-gpu', '--disable-software-rasterizer', '--use-gl=swiftshader'] })
const look = (page) =>
  page.evaluate(() => ({
    zoom: document.querySelector('svg[data-map-keys]')?.getAttribute('data-zoom') ?? null,
    pin: document.querySelector('[data-pin]')?.getAttribute('data-pin') ?? null,
    sub: document.querySelector('.home-story-subhead, [data-testid=home-story-scope-line]')?.textContent ?? '',
    // Desktop: "× National"; phone: the header toggle's National side (#1301).
    national: [...document.querySelectorAll('.sh-national, .sh-ptoggle-btn[data-side="national"][aria-pressed="false"]')].find((e) => e.getClientRects().length > 0) ? true : false,
  }))

const { defaultBrowserType: _engine, ...pixel } = devices['Pixel 7']
for (const [label, opts] of [
  ['Desktop 1440x900', { viewport: { width: 1440, height: 900 } }],
  ['Pixel 7', pixel],
]) {
  const ctx = await browser.newContext(opts)
  const page = await ctx.newPage()
  console.log(`\n${label} /?state=AL&city=Tuscaloosa`)
  await page.goto(`${base}/?state=AL&city=Tuscaloosa`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('svg[data-map-keys] rect[data-state]', { timeout: 60_000 })
  await page.waitForTimeout(1500)
  let r = await look(page)
  ok(r.zoom === 'AL', `the map zooms to Alabama (${r.zoom})`)
  ok(r.pin === 'Tuscaloosa', `Tuscaloosa is marked (${r.pin})`)
  ok(/Tuscaloosa has (only \d+ meetings?|no meetings) on data centers, too few to call/.test(r.sub), `the subtitle says why ("${r.sub.slice(0, 90)}")`)
  ok(r.national, 'the header shows "× National"')
  if (shots) await page.screenshot({ path: `${shots}/place-${label.replace(/\W+/g, '_')}-tuscaloosa.png` })
  await page.locator('.sh-national, .sh-ptoggle-btn[data-side="national"][aria-pressed="false"]').locator('visible=true').first().click()
  await page.waitForTimeout(1500)
  r = await look(page)
  ok(page.url().includes('scope=national') && r.zoom === null, `× National puts the US map back (${page.url().replace(base, '')})`)
  if (shots) await page.screenshot({ path: `${shots}/place-${label.replace(/\W+/g, '_')}-national.png` })
  await page.goto(`${base}/stories/data-centers?state=AL&city=Tuscaloosa`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForTimeout(2500)
  const note = await page.evaluate(() => document.querySelector('.story-scope-note')?.textContent ?? '')
  ok(/too few to call/.test(note) && page.url().includes('city=Tuscaloosa'), `the story notes the step up and keeps ?city= ("${note.slice(0, 70)}")`)
  await ctx.close()
}
await browser.close()
if (failures) {
  console.error(`\n${failures} check(s) failed.`)
  process.exit(1)
}
console.log('\nThe map, the label and the data follow the place; National is one click away.')
