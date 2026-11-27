// Explorer phone layout check (#1291): the census map top sits in the first viewport at 360x740 and 412x915.
// node e2e/explorer-compact.check.mjs <base-url> <tag>; shots go to the scratchpad dir named in 'out'.
import { chromium } from 'playwright'
const [base, tag, vint = '2023'] = process.argv.slice(2)
const out = process.env.SHOTS_DIR ?? '/tmp'
const browser = await chromium.launch({ args: ['--disable-gpu', '--disable-software-rasterizer', '--use-gl=swiftshader'] })
let fails = 0
const ok = (c, m) => { console.log(`${c ? 'ok  ' : 'FAIL'} ${m}`); if (!c) fails++ }
for (const [name, vp, mobile] of [['360', { width: 360, height: 740 }, true], ['412', { width: 412, height: 915 }, true], ['1440', { width: 1440, height: 900 }, false]]) {
  const ctx = await browser.newContext({ viewport: vp, hasTouch: mobile, isMobile: mobile, deviceScaleFactor: 2 })
  const page = await ctx.newPage()
  await page.goto(`${base}/data-explorer/map/us/${vint}/median_household_income`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-fips]', { timeout: 60000 })
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${out}/${tag}-${name}-0-nation.png` })
  const click = async (sel) => { const el = page.locator(sel).first(); await el.scrollIntoViewIfNeeded(); mobile ? await el.tap({ force: true }) : await el.click({ force: true }) }
  const twice = async (sel) => { await click(sel); await page.waitForTimeout(500); if (mobile) { await page.locator('[data-testid=census-map-preview-drill]').tap().catch(() => click(sel)) } await page.waitForTimeout(2500) }
  await twice('[data-fips="01"]')
  await page.screenshot({ path: `${out}/${tag}-${name}-1-state.png` })
  await page.waitForSelector("[data-geoid]", {timeout:20000}).catch(()=>console.log("no geoid", name)); await twice("[data-geoid=\"01125\"]")
  await page.screenshot({ path: `${out}/${tag}-${name}-2-county.png` })
  // towns
  const towns = page.getByText(/cities & towns|Cities & towns|Drill down to (cities|towns)/i).first()
  const btn = page.getByRole('button', { name: /cities|towns/i }).first()
  if (await btn.count()) { await btn.click({ force: true }).catch(() => {}); await page.waitForTimeout(3000) }
  await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(500)
  await page.screenshot({ path: `${out}/${tag}-${name}-3-towns.png` })
  const card = page.locator('[data-testid=census-map-card], svg[aria-label="Census drill-down map"]').first()
  const top = await page.locator('svg[aria-label="Census drill-down map"]').boundingBox().then((b) => b?.y)
  const h = await page.locator('svg[aria-label="Census drill-down map"]').boundingBox().then((b) => b?.height)
  console.log(name, 'svg top', top, 'height', h, 'viewport', vp.height, 'url', page.url().replace(base, ''))
  if (mobile) { ok(top != null && top < vp.height * 0.4, `${name}: map top within first viewport (${top})`); ok(h > 380, `${name}: map height ${h}`) }
  await ctx.close()
}
await browser.close()
process.exit(fails ? 1 : 0)
