// Where towns stand check (#1438). Mocks /api/rankings/topics and /api/rankings with a small test-only fixture, then at
// Pixel 7 and 1440x900 checks the gauges show, nothing scrolls sideways on the phone, and tapping a dot opens the place panel.
//
//   node e2e/where-towns-stand.check.mjs [--base http://localhost:5173] [--shots <dir>]
//
// Exits 1 on any failure.
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

// Test-only fixture; never served by the app.
const place = (id, name, f, a, ranked, extra = {}) => ({
  jurisdiction_id: id, jurisdiction_name: name, state_code: 'AL', size_band: 'mid', population: 90000,
  speakers_for: f, speakers_against: a, meetings: 3, against_share: a / (f + a),
  shrunk_against_share: (a + 5) / (f + a + 10), is_ranked: ranked, band_rank: ranked ? id : null,
  band_ranked_count: ranked ? 3 : null, officials_side: null, last_meeting_date: '2026-04-02', ...extra,
})
const places = [place(1, 'Alpha', 2, 16, true), place(2, 'Bravo', 9, 3, true), place(3, 'Charlie', 1, 12, true), place(4, 'Delta', 2, 1, false), place(5, 'Echo', 1, 2, false)]
const topics = [
  { topic_id: 11, slug: 'data-centers', name: 'Data centers', places_ranked: 3, places_unranked: 2, places_leaning_against: 2, places_leaning_for: 1, national_against_share: 0.6, median_shrunk_against_share: 0.62 },
  { topic_id: 12, slug: 'license-plate-readers', name: 'License plate readers', places_ranked: 3, places_unranked: 2, places_leaning_against: 2, places_leaning_for: 1, national_against_share: 0.6, median_shrunk_against_share: 0.62 },
]
const mock = async (page) => {
  await page.route('**/api/rankings/topics', (r) => r.fulfill({ json: topics }))
  await page.route(/\/api\/rankings\?/, (r) => {
    const slug = new URL(r.request().url()).searchParams.get('topic')
    const t = topics.find((x) => x.slug === slug) ?? topics[0]
    r.fulfill({ json: { topic: { topic_id: t.topic_id, slug: t.slug, name: t.name }, national: { against_share: 0.6, median_shrunk_against_share: 0.62, places_ranked: 3, places_unranked: 2, places_leaning_against: 2, places_leaning_for: 1, speakers_for: 15, speakers_against: 34 }, places } })
  })
}

const browser = await chromium.launch({ args: ['--disable-gpu', '--disable-software-rasterizer', '--use-gl=swiftshader'] })
const { defaultBrowserType: _e, ...pixel } = devices['Pixel 7']
for (const [label, opts, phone] of [
  ['Desktop 1440x900', { viewport: { width: 1440, height: 900 } }, false],
  ['Pixel 7', pixel, true],
]) {
  const ctx = await browser.newContext(opts)
  const page = await ctx.newPage()
  await mock(page)
  console.log(`\n${label} /where-towns-stand`)
  page.on('pageerror', (e) => console.log('PE', e.message.slice(0, 200)))
  await page.goto(`${base}/where-towns-stand`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('[data-testid=stance-gauge]', { timeout: 60_000 })
  ok((await page.locator('[data-testid=stance-gauge]').count()) === 2, 'one gauge per topic')
  ok(await page.getByText('Most places that discussed data centers leaned against: 2 of 3').isVisible(), 'takeaway title from the counts')
  ok(await page.getByText('National · all sizes').first().isVisible(), 'scope label says National · all sizes')
  ok(await page.getByText('How these rankings work').isVisible(), 'method section present')
  if (phone) {
    const w = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }))
    ok(w.sw <= w.cw, `no horizontal scroll (${w.sw} <= ${w.cw})`)
  }
  await page.locator('[data-testid=stance-gauge]').first().getByRole('button', { name: /Alpha, AL: 16 of 18 speakers against/ }).click()
  await page.waitForSelector('[data-testid=place-panel]')
  const panel = page.locator('[data-testid=place-panel]').first()
  ok(await panel.getByText(/Ranked #1 of 3 mid-size places/).isVisible(), 'panel shows the rank')
  ok((await panel.getByRole('link').getAttribute('href')) === '/browse-topics?topic_id=11&state=AL&city=Alpha', 'panel links to the place-scoped evidence')
  await page.goto(`${base}/where-towns-stand?topic=data-centers&band=mid&state=AL`, { waitUntil: 'networkidle' })
  await page.waitForSelector('[data-testid=stance-gauge]')
  ok(await page.getByText('Alabama · mid-size places').first().isVisible(), 'scope label matches ?state=AL&band=mid')
  if (phone) {
    const w = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)
    ok(w, 'no horizontal scroll on the single-topic page')
  }
  if (shots) await page.screenshot({ path: `${shots}/wts-${label.replace(/\W+/g, '_')}.png`, fullPage: true })
  await ctx.close()
}
await browser.close()
process.exit(failures ? 1 : 0)
