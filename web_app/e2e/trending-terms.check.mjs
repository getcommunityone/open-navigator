// Trending in meetings check (#1399). At Pixel 7 (412x915, touch) and 1440x900, on /browse-topics/all, national and
// ?state=<ST>: the chip row loads from the real API; the label names the scope; the page never scrolls sideways while the
// chip row scrolls on its own on a phone; tapping a chip opens verbatim quotes with the term in <mark>, the speaker as
// "First L." or "Speaker not identified"; "Most heated" shows flame chips.
//
//   node e2e/trending-terms.check.mjs [--base http://localhost:5173] [--state GA] [--shots /path/to/dir]
//
// Needs the app and its API running against a warehouse with the trending marts built. Exits 1 on any failure.
import { chromium, devices } from 'playwright'

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`)
  return i > 0 ? process.argv[i + 1] : dflt
}
const base = arg('base', 'http://localhost:5173')
const st = arg('state', 'GA')
const shots = arg('shots', '')
let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}

const VIEWS = [
  { name: 'Pixel 7', ctx: { ...devices['Pixel 7'], reducedMotion: 'reduce' }, phone: true },
  { name: '1440', ctx: { viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }, phone: false },
]

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--disable-gpu', '--disable-software-rasterizer'] })
for (const v of VIEWS) {
  for (const [path, label] of [['/browse-topics/all', 'National'], [`/browse-topics/all?state=${st}`, null]]) {
    console.log(`\n${v.name} ${path}`)
    const ctx = await browser.newContext(v.ctx)
    const page = await ctx.newPage()
    const errors = []
    page.on('pageerror', (e) => errors.push(String(e)))
    await page.goto(base + path, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await page.waitForSelector('[data-testid="trending-terms-chips"] button', { timeout: 90_000 })
    const title = await page.textContent('#trending-terms-title')
    ok(label ? title.includes(`· ${label}`) : !title.includes('National'), `scope label: "${title.trim()}"`)
    const m = await page.evaluate(() => {
      const ul = document.querySelector('[data-testid="trending-terms-chips"]')
      return {
        pageScroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        chips: ul.querySelectorAll('button').length,
        rowScrolls: ul.scrollWidth > ul.clientWidth,
        overflowX: getComputedStyle(ul).overflowX,
        arrows: [...ul.querySelectorAll('button')].filter((b) => b.textContent.includes('↑')).length,
      }
    })
    ok(m.pageScroll <= 0, `no sideways page scroll (${m.pageScroll}px)`)
    ok(m.chips > 0 && m.arrows === m.chips, `${m.chips} rising chips, each with an up arrow`)
    ok(m.overflowX === 'auto', 'chip row scrolls horizontally')
    if (v.phone) ok(m.rowScrolls, 'on the phone the chips overflow into a horizontal scroll')
    if (shots) await page.screenshot({ path: `${shots}/trend-${v.phone ? 'pixel7' : '1440'}-${label ? 'us' : st}.png` })

    const first = page.locator('[data-testid="trending-terms-chips"] button').first()
    await first.click()
    await page.waitForSelector('#trending-term-evidence', { timeout: 30_000 })
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="trending-term-evidence-list"] li') ||
        /No quoted meetings|could not be loaded/.test(document.querySelector('#trending-term-evidence')?.textContent ?? ''),
      null,
      { timeout: 60_000 },
    )
    const ev = await page.evaluate(() => {
      const items = [...document.querySelectorAll('[data-testid="trending-term-evidence-list"] li')]
      return {
        n: items.length,
        marked: items.filter((li) => li.querySelector('mark')).length,
        speakers: items.map((li) => li.querySelector('p')?.textContent?.split(' · ')[0] ?? ''),
      }
    })
    ok(ev.n > 0 && ev.marked === ev.n, `${ev.n} quotes, each with the term highlighted`)
    ok(
      ev.speakers.every((s) => s === 'Speaker not identified' || /^[A-Z][a-z]+( [A-Z]\.)?$/.test(s)),
      `speakers shown as "First L." or not identified (${[...new Set(ev.speakers)].join(', ')})`,
    )
    if (shots) await page.screenshot({ path: `${shots}/trend-${v.phone ? 'pixel7' : '1440'}-${label ? 'us' : st}-evidence.png` })

    await page.getByRole('button', { name: /Most heated/ }).click()
    await page.waitForFunction(
      () => [...document.querySelectorAll('[data-testid="trending-terms-chips"] button')].some((b) => b.textContent.includes('🔥')) ||
        document.querySelector('#trending-terms-title')?.parentElement?.parentElement?.textContent?.includes('No heated'),
      null,
      { timeout: 30_000 },
    )
    ok(page.url().includes('trend=hot'), 'sort carried in the URL (?trend=hot)')
    ok(errors.length === 0, `no page errors${errors.length ? `: ${errors[0]}` : ''}`)
    await ctx.close()
  }
}
await browser.close()
console.log(failures ? `\n${failures} failure(s)` : '\nall checks passed')
process.exit(failures ? 1 : 0)
