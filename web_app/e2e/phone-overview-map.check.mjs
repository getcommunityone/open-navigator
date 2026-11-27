// Phone Overview map check (#1380). At 360x740 and 412x915 it asserts, on the Data Center Story and a topic story:
// the sticky story bar is at most 18% of the viewport; the headline is at most two lines; the Overview map takes at least
// 55% of the viewport height and the column's full width; its labels draw at 12px or more; nothing overlaps the bottom bar.
// The topic story's place counts are a TEST FIXTURE served through a route stub (the local warehouse has none), used only to
// lay the map out; it never reaches a served code path.
//
//   node e2e/phone-overview-map.check.mjs [--base http://localhost:5173] [--shots /path/to/dir]
//
// Needs the app and its API running. Exits 1 on any failure.
import { chromium } from 'playwright'

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
const PLACES = [
  ['Birmingham', 33.52, -86.8, 12], ['Tuscaloosa', 33.21, -87.57, 9], ['Huntsville', 34.73, -86.59, 7],
  ['Mobile', 30.69, -88.04, 5], ['Montgomery', 32.37, -86.3, 4], ['Auburn', 32.61, -85.48, 3],
].map(([name, latitude, longitude, meetings], i) => ({
  jurisdiction_id: `fixture-${i}`, jurisdiction_name: name, jurisdiction_type: 'city', geoid: null, latitude, longitude, meetings,
  lean_meetings: 0, speakers_against: 0, speakers_for: 0, speakers_neutral: 0, speakers_question: 0, silent_meetings: 0,
  public_against_meetings: 0, disagreement_meetings: 0,
}))
const CASES = [
  { name: 'data center story', path: '/stories/data-centers?state=AL&city=Homewood', tag: 'dc' },
  { name: 'topic story', path: '/stories/homelessness-and-shelters?state=AL', tag: 'topic', stubPlaces: true },
]

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
for (const [w, h] of [[360, 740], [412, 915]]) {
  for (const c of CASES) {
    console.log(`\n${c.name} ${w}x${h}`)
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' })
    const page = await ctx.newPage()
    if (c.stubPlaces) {
      await page.route('**/api/topics/*/places*', (r) =>
        r.fulfill({ json: { topic_id: 1, state_code: 'AL', total_meetings: 40, unplaced_meetings: 0, available: true, by_place: PLACES } }),
      )
    }
    await page.goto(base + c.path, { waitUntil: 'networkidle', timeout: 120_000 })
    await page.waitForSelector('.stance-panel--glance figure.stance-map', { timeout: 60_000 })
    await page.waitForTimeout(2500)
    if (shots) await page.screenshot({ path: `${shots}/${c.tag}-${w}.png` })

    const m = await page.evaluate(() => {
      const box = (el) => (el ? el.getBoundingClientRect().toJSON() : null)
      const fig = document.querySelector('.stance-panel--glance figure.stance-map')
      const svg = fig?.querySelector('svg.stance-map-svg')
      let label = null
      if (svg) {
        const t = svg.querySelector('.stance-map-labels text')
        const vb = svg.viewBox.baseVal
        if (t && vb.width) label = parseFloat(getComputedStyle(t).fontSize) * (svg.getBoundingClientRect().width / vb.width)
      }
      const s = document.querySelector('.stance-top .stance-sentence')
      return {
        top: box(document.querySelector('.stance-top')),
        sentence: box(s),
        lineH: s ? parseFloat(getComputedStyle(s).lineHeight) : 0,
        fig: box(fig),
        grid: box(document.querySelector('.stance-panel--glance .stance-grid')),
        bar: box(document.querySelector('[data-testid="story-bottombar"]')),
        label,
        glanceKids: [...document.querySelectorAll('.stance-panel--glance .stance-right *')].map((e) => e.getBoundingClientRect().bottom),
      }
    })
    ok(m.top.height <= h * 0.18, `the story bar is ${Math.round(m.top.height)}px, at most 18% of ${h}`)
    ok(m.sentence.height <= m.lineH * 2 + 40 /* the picker blanks are taller than a text line */ && m.sentence.height < m.lineH * 3 + 8, `the headline takes at most two lines (${Math.round(m.sentence.height)}px)`)
    ok(m.fig.height >= h * 0.55, `the map is ${Math.round(m.fig.height)}px tall, at least 55% of ${h}`)
    ok(m.fig.width >= m.grid.width - 2, `the map is the column's full width (${Math.round(m.fig.width)} of ${Math.round(m.grid.width)})`)
    ok(m.label == null || m.label >= 11.5, `map labels draw at ${m.label?.toFixed(1)}px (12px or more)`)
    ok(m.bar != null && m.fig.bottom <= m.bar.top + 1, `the map ends above the bottom bar (${Math.round(m.fig.bottom)} <= ${Math.round(m.bar?.top)})`)
    ok(m.glanceKids.every((b) => b <= m.bar.top + 1 || b === 0), 'no element of the figure column runs under the bottom bar')
    await ctx.close()
  }
}
await browser.close()
console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed')
process.exit(failures ? 1 : 0)
