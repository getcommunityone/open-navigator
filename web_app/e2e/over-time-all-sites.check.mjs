// Over time: every data center site on the map (#1428, owner phone feedback: "Our map is missing those data centers").
// At Pixel 7 and 1440x900, national and FL, it opens /stories/data-centers?screen=over-time with reduced motion (no
// autoplay, so the map rests at today's frame) and checks against GET /api/data-centers/sites-timeline:
//   - the legend's phase counts sum to its data-mapped, and the shapes drawn equal it;
//   - mapped plus the "Not mapped" line equals the API's `total` (every site in scope), and "Not mapped" is the API's
//     `not_mapped` plus only the sites in territories off the US map (PR, GU, MP, VI, ...);
//   - the squares ("start date not on record") equal the legend's undated line and the undated sites drawn;
//   - the headline names the API's total; the last (projected) frame still shows every mapped site.
//
//   node e2e/over-time-all-sites.check.mjs [--base http://localhost:5173] [--shots <dir>]
//
// Exits 1 on a mismatch. Needs the app (and its API) running; it reads the page, it changes nothing.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', null)
const SIZES = [
  { name: 'pixel7', opts: { ...devices['Pixel 7'] } },
  { name: '1440', opts: { viewport: { width: 1440, height: 900 } } },
]
const SCOPES = [
  { name: 'national', path: '/stories/data-centers', api: '' },
  { name: 'FL', path: '/stories/data-centers?state=FL', api: '?state=FL' },
]
const fmt = (n) => n.toLocaleString('en-US')

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
let failures = 0
const check = (ok, m) => {
  if (!ok) failures++
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${m}`)
}

for (const size of SIZES) {
  const context = await browser.newContext({ ...size.opts, reducedMotion: 'reduce' })
  for (const scope of SCOPES) {
    const page = await context.newPage()
    const api = await (await page.request.get(`${base}/api/data-centers/sites-timeline${scope.api}`, { timeout: 120_000 })).json()
    const OFF_MAP = new Set(['PR', 'GU', 'MP', 'VI', 'AS'])
    const drawable = (s) => s.latitude != null && s.longitude != null && !OFF_MAP.has(s.state_code)
    const expectMapped = api.sites.filter(drawable).length
    const undatedMapped = api.sites.filter((s) => drawable(s) && ['listed_by', 'none'].includes(s.appear_basis)).length
    console.log(`\n${size.name} ${scope.name}: total ${api.total}, mapped ${api.mapped}, not mapped ${api.not_mapped}, undated ${api.undated}`)
    const sep = scope.path.includes('?') ? '&' : '?'
    await page.goto(`${base}${scope.path}${sep}screen=over-time`, { waitUntil: 'networkidle', timeout: 120_000 })
    await page.waitForSelector('section[data-screen="over-time"] .dc-tl-counts', { timeout: 60_000 })
    await page.evaluate(() => document.querySelector('section[data-screen="over-time"]')?.scrollIntoView({ block: 'start', behavior: 'instant' }))
    await page.waitForTimeout(1500)
    const read = () =>
      page.evaluate(() => {
        const root = document.querySelector('section[data-screen="over-time"]')
        const ul = root.querySelector('.dc-tl-counts')
        const n = (sel) => [...ul.querySelectorAll(sel)].reduce((t, li) => t + Number(li.getAttribute('data-count') ?? 0), 0)
        return {
          mapped: Number(ul.getAttribute('data-mapped')),
          phaseSum: n('li[data-phase]'),
          notMapped: n('li[data-key="not-mapped"]'),
          squaresKey: n('li[data-key="undated"]'),
          shapes: root.querySelectorAll('.dc-tl-map .dc-tl-dot').length,
          squares: root.querySelectorAll('.dc-tl-map .dc-tl-sq').length,
          year: root.querySelector('.dc-tl-range')?.value,
          headline: root.textContent ?? '',
        }
      })
    let m = await read()
    check(m.year === api.current_year, `rests at today (${m.year})`)
    check(m.phaseSum === m.mapped, `legend phases sum to mapped (${fmt(m.phaseSum)} = ${fmt(m.mapped)})`)
    check(m.mapped === expectMapped, `legend mapped equals the API's drawable sites (${fmt(m.mapped)} of ${fmt(api.mapped)} with coordinates)`)
    check(m.mapped + m.notMapped === api.total, `mapped + not mapped = every site (${fmt(m.mapped)} + ${m.notMapped} = ${fmt(api.total)})`)
    check(m.notMapped === api.not_mapped + (api.mapped - expectMapped), `not mapped = no coordinates ${api.not_mapped} + off-map territories ${api.mapped - expectMapped}`)
    check(m.shapes === m.mapped, `shapes drawn equal mapped (${fmt(m.shapes)})`)
    check(m.squares === undatedMapped && m.squaresKey === undatedMapped, `squares equal mapped undated sites (${fmt(m.squares)})`)
    check(m.headline.includes(`${fmt(api.total)} data center site`), `headline names the total (${fmt(api.total)})`)
    if (shots) await page.screenshot({ path: `${shots}/over-time-${size.name}-${scope.name}-today.png` })
    // the last frame (projected when Epoch projects one) keeps every mapped site
    await page.evaluate((y) => {
      const r = document.querySelector('section[data-screen="over-time"] .dc-tl-range')
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
      set.call(r, y)
      r.dispatchEvent(new Event('input', { bubbles: true }))
    }, api.last_year)
    await page.waitForTimeout(600)
    m = await read()
    check(m.year === api.last_year && m.mapped === expectMapped && m.shapes === expectMapped, `last frame ${m.year} still shows every mapped site (${fmt(m.shapes)})`)
    if (shots) await page.screenshot({ path: `${shots}/over-time-${size.name}-${scope.name}-last.png` })
    await page.close()
  }
  await context.close()
}
await browser.close()
console.log(failures ? `\n${failures} failure(s)` : '\nall checks passed')
process.exit(failures ? 1 : 0)
