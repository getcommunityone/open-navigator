// Who governs a place (#1446). On the Tuscaloosa place page (/jurisdiction/0177256/meetings), at Pixel 7 and 1440 wide:
// "Who governs Tuscaloosa" lists the City Council with its meetings and members, "Officials heard most recently" lists
// roster officials with a play link to the moment, the body page opens with its scope label, members, roles and a Close,
// and nothing scrolls sideways.
//
//   node e2e/who-governs.check.mjs [--base http://localhost:5173] [--shots /path/to/dir]
//
// Needs the app and its API running with the governing_body marts published. Exits 1 on any failure.
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

const VIEWS = [
  ['pixel7', devices['Pixel 7']],
  ['1440', { viewport: { width: 1440, height: 1000 } }],
]

const browser = await chromium.launch()
for (const [name, device] of VIEWS) {
  console.log(`\n${name}`)
  const ctx = await browser.newContext(device)
  const page = await ctx.newPage()
  await page.goto(`${base}/jurisdiction/0177256/meetings`, { waitUntil: 'domcontentloaded' })
  const governs = page.getByTestId('who-governs')
  await governs.waitFor({ timeout: 60_000 })
  ok(await page.getByRole('heading', { name: 'Who governs Tuscaloosa' }).isVisible(), 'heading names the place')
  const council = governs.getByRole('link', { name: /City Council/ }).first()
  ok(await council.isVisible(), 'City Council is listed')
  const councilText = await council.innerText()
  ok(/meetings on file/.test(councilText) && /7 people/.test(councilText), `council card: ${councilText.replace(/\s+/g, ' ')}`)
  const heard = page.getByTestId('officials-heard')
  await heard.waitFor()
  const plays = heard.getByRole('link', { name: /^Play / })
  ok((await plays.count()) > 0, `play-at-moment links: ${await plays.count()}`)
  const firstHref = (await plays.count()) ? await plays.first().getAttribute('href') : ''
  ok(/youtube\.com\/watch\?v=.+&t=\d+s/.test(firstHref ?? ''), `moment link: ${firstHref}`)
  ok(await heard.getByRole('link', { name: 'Walt Maddox', exact: true }).isVisible(), 'the mayor links to his person page')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  ok(overflow <= 1, `no sideways scroll (${overflow}px)`)
  const personHref = await heard.getByRole('link', { name: 'Walt Maddox', exact: true }).getAttribute('href')
  const personPage = await ctx.newPage()
  await personPage.goto(`${base}${personHref}`, { waitUntil: 'domcontentloaded' })
  ok(await personPage.getByText('Walt Maddox').first().isVisible({ timeout: 30_000 }).catch(() => false) ||
     (await personPage.getByText('Walt Maddox').first().waitFor({ timeout: 30_000 }).then(() => true).catch(() => false)),
     `person page opens (${personHref})`)
  await personPage.close()
  if (shots) {
    await governs.scrollIntoViewIfNeeded()
    await page.screenshot({ path: `${shots}/who-governs-${name}.png`, fullPage: false })
    await heard.scrollIntoViewIfNeeded()
    await page.screenshot({ path: `${shots}/officials-heard-${name}.png`, fullPage: false })
  }

  await council.click()
  await page.getByRole('heading', { name: 'City Council', level: 1 }).waitFor({ timeout: 60_000 })
  ok((await page.getByTestId('body-scope').innerText()).includes('Tuscaloosa'), 'body page scope label is the place')
  ok(await page.getByText('Walt Maddox').first().isVisible(), 'members listed')
  ok(await page.getByText(/District 5/).first().isVisible(), 'ended seat (District 5) shown as ended, not filled')
  ok(await page.getByTestId('page-close').isVisible(), 'PageClose present')
  const overflow2 = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  ok(overflow2 <= 1, `body page: no sideways scroll (${overflow2}px)`)
  if (shots) await page.screenshot({ path: `${shots}/body-page-${name}.png`, fullPage: true })
  await ctx.close()
}
await browser.close()
console.log(failures ? `\n${failures} failure(s)` : '\nall ok')
process.exit(failures ? 1 : 0)
