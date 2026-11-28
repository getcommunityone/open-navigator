// Every chart has a visible title and colour legend (#1409). On the home page (national, Florida, Alabama; data centers and
// short-term rentals) and on story screens, at Pixel 7 and 1440 wide, every chart <svg>/<canvas> must sit inside a
// `[data-chart-frame]` whose `[data-chart-title]` and `[data-chart-legend]` are visible and non-empty, and the legend must
// fit the viewport width (no horizontal overflow).
//
//   node e2e/chart-legends.check.mjs [--base http://localhost:5173] [--shots /path/to/dir]
//
// Needs the app and its API running. Exits 1 on any failure.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const shots = arg('shots', '')
let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}

const PAGES = [
  ['home national', '/'],
  ['home FL data centers', '/?state=FL'],
  ['home AL data centers', '/?state=AL'],
  ['home national short-term rentals', '/?topic=short-term-rentals'],
  ['home FL short-term rentals', '/?topic=short-term-rentals&state=FL'],
  ['home AL short-term rentals', '/?topic=short-term-rentals&state=AL'],
  ['story data centers overview', '/stories/data-centers?state=AL&screen=overview'],
  ['story data centers FL', '/stories/data-centers?state=FL'],
  ['story short-term rentals FL', '/stories/short-term-rentals?state=FL&screen=overview'],
  ['story short-term rentals national', '/stories/short-term-rentals'],
  ...['voices', 'sites', 'over-time', 'projects', 'jobs', 'concerns', 'meetings', 'agendas', 'decisions', 'gatherings'].map((sc) => [
    `story data centers ${sc}`,
    `/stories/data-centers?state=AL&screen=${sc}`,
  ]),
  ...['voices', 'over-time', 'meetings', 'decisions'].map((sc) => [`story short-term rentals ${sc}`, `/stories/short-term-rentals?state=FL&screen=${sc}`]),
  ['data explorer map', '/data-explorer/map'],
]
const VIEWPORTS = [
  ['pixel7', { ...devices['Pixel 7'] }],
  ['1440', { viewport: { width: 1440, height: 900 } }],
]

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
for (const [vname, vopts] of VIEWPORTS) {
  for (const [name, path] of PAGES) {
    console.log(`\n${name} @ ${vname}`)
    const ctx = await browser.newContext({ ...vopts, reducedMotion: 'reduce' })
    const page = await ctx.newPage()
    await page.goto(base + path, { waitUntil: 'networkidle', timeout: 120_000 }).catch(() => {})
    await page.waitForTimeout(3500)
    const probe = () => page.evaluate(() => {
      const vis = (el) => {
        const b = el.getBoundingClientRect()
        const cs = getComputedStyle(el)
        return b.width > 0 && b.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
      }
      // A chart region: a drawn <svg>/<canvas> at least 120x80 that isn't an icon or decoration.
      const regions = [...document.querySelectorAll('svg, canvas')].filter((el) => {
        const b = el.getBoundingClientRect()
        return b.width >= 120 && b.height >= 80 && vis(el) && !el.closest('[aria-hidden="true"]') && !el.closest('header, footer, nav')
      })
      return {
        total: regions.length,
        bad: regions
          .map((el) => {
            const f = el.closest('[data-chart-frame]')
            const t = f?.querySelector('[data-chart-title]')
            const l = f?.querySelector('[data-chart-legend]')
            const lb = l?.getBoundingClientRect()
            return {
              what: el.getAttribute('aria-label')?.slice(0, 60) || el.getAttribute('class') || el.tagName,
              frame: Boolean(f),
              title: Boolean(t && vis(t) && (t.textContent ?? '').trim().length > 3),
              legend: Boolean(l && vis(l) && (l.textContent ?? '').trim().length > 2),
              fits: !lb || (lb.left >= -1 && lb.right <= window.innerWidth + 1),
              legendH: lb ? Math.round(lb.height) : 0,
            }
          })
          .filter((x) => !x.frame || !x.title || !x.legend || !x.fits),
      }
    })
    let r = await probe()
    for (let k = 0; k < 3 && r.total === 0; k++) {
      await page.waitForTimeout(3000)
      r = await probe()
    }
    ok(r.total >= 1, `${r.total} chart region(s) found`)
    for (const b of r.bad) ok(false, `chart "${b.what}": frame=${b.frame} title=${b.title} legend=${b.legend} fits=${b.fits}`)
    if (r.bad.length === 0) ok(true, 'every chart region has a visible title and legend that fit')
    if (shots) await page.screenshot({ path: `${shots}/${name.replace(/\W+/g, '-')}-${vname}.png` })
    await ctx.close()
  }
}
await browser.close()
console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed')
process.exit(failures ? 1 : 0)
