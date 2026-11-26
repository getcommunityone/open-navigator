import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs'

/**
 * Accessibility checks (#1146). Run against a dev server that is up:
 *   A11Y_BASE_URL=http://localhost:5173 npx playwright test
 * A11Y_REPORT=<file> writes each page's violations (id, impact, node count) as JSON.
 */

const PAGES = [
  { name: 'home', path: '/' },
  { name: 'data-centers story', path: '/stories/data-centers' },
  { name: 'topic story (guns)', path: '/stories/guns' },
  { name: 'search', path: '/search?q=fluoride' },
]

const report: Record<string, { id: string; impact: string | null | undefined; nodes: number }[]> = {}

test.afterAll(() => {
  if (process.env.A11Y_REPORT) fs.writeFileSync(process.env.A11Y_REPORT, JSON.stringify(report, null, 2))
})

async function settle(page: Page) {
  await page.waitForLoadState('domcontentloaded')
  // Data arrives after load; give the page a moment to draw its maps and tiles.
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
  await page.waitForTimeout(1500)
}

for (const p of PAGES) {
  test(`axe: ${p.name} has no serious or critical violations (WCAG 2.2 AA)`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto(p.path)
    await settle(page)
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze()
    report[p.name] = results.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }))
    const blocking = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
    expect(
      blocking.map((v) => `${v.impact} ${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`),
    ).toEqual([])
  })
}

/** Presses Tab (or Shift+Tab) until `matches` holds for the focused element, up to `max` presses. */
async function tabUntil(page: Page, matches: string, max = 150, back = false): Promise<void> {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press(back ? 'Shift+Tab' : 'Tab')
    if (await page.evaluate((sel) => document.activeElement?.matches(sel) ?? false, matches)) return
  }
  throw new Error(`Tab never reached ${matches}`)
}

const focusedText = (page: Page) => page.evaluate(() => (document.activeElement as HTMLElement | null)?.innerText ?? '')

test('keyboard: skip link is the first tab stop and moves focus to main', async ({ page }) => {
  await page.goto('/')
  await settle(page)
  await page.keyboard.press('Tab')
  await expect(page.locator(':focus')).toHaveText('Skip to main content')
  await page.keyboard.press('Enter')
  await expect(page.locator('main#main-content')).toBeFocused()
})

test('keyboard: tab into the topic strip, arrow to Guns, Enter shows its story', async ({ page }) => {
  await page.goto('/')
  await settle(page)
  await expect(page.locator('[data-topic-tile]').first()).toBeVisible()
  // One tab stop: only one tile is in the tab order.
  await expect(page.locator('[data-topic-tile][tabindex="0"]')).toHaveCount(1)
  await tabUntil(page, '[data-topic-tile]')
  const headline = page.locator('.home-story-headline').first()
  const before = (await headline.innerText().catch(() => '')) ?? ''
  const tiles = await page.locator('[data-topic-tile]').count()
  let onGuns = false
  for (let i = 0; i < tiles; i++) {
    if ((await focusedText(page)).startsWith('Guns')) {
      onGuns = true
      break
    }
    await page.keyboard.press('ArrowRight')
  }
  expect(onGuns, 'the arrows reach the Guns tile').toBe(true)
  // The focused tile is scrolled into the strip's view.
  const inView = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement
    const list = el.closest('ul')!.getBoundingClientRect()
    const r = el.getBoundingClientRect()
    return r.left >= list.left - 2 && r.right <= list.right + 2
  })
  expect(inView).toBe(true)
  await page.keyboard.press('Enter')
  const guns = page.locator('[data-topic-tile]', { hasText: /^Guns/ })
  await expect(guns).toHaveAttribute('aria-pressed', 'true')
  await expect(headline).not.toHaveText(before)
  // Home/End jump to the ends, and Tab leaves the strip in one press.
  await page.keyboard.press('End')
  expect(await page.evaluate(() => document.activeElement?.closest('li')?.nextElementSibling == null)).toBe(true)
  await page.keyboard.press('Home')
  expect(await page.evaluate(() => document.activeElement?.closest('li')?.previousElementSibling == null)).toBe(true)
  await page.keyboard.press('Tab')
  expect(await page.evaluate(() => document.activeElement?.hasAttribute('data-topic-tile'))).toBe(false)
})

test('keyboard: the home map is one tab stop, arrows show a state, Enter opens its story', async ({ page }) => {
  await page.goto('/')
  await settle(page)
  const map = page.locator('[data-map-keys]').first()
  await expect(map).toBeVisible()
  await tabUntil(page, '[data-map-keys]')
  await page.keyboard.press('ArrowRight')
  await expect(page.locator('[aria-live="polite"]', { hasText: /meeting/ }).first()).toBeAttached()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/stories\/.*state=/)
})

test('keyboard: a story pages with the arrow keys and focus lands on the new heading', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/stories/data-centers')
  await settle(page)
  await page.locator('h2').first().waitFor()
  const screenOf = () => new URL(page.url()).searchParams.get('screen')
  const first = screenOf()
  await page.keyboard.press('ArrowRight')
  await expect.poll(screenOf, { timeout: 10_000 }).not.toBe(first)
  const second = screenOf()
  await expect.poll(() => page.evaluate(() => document.activeElement?.tagName ?? ''), { timeout: 10_000 }).toMatch(/^H[12]$/)
  await page.keyboard.press('ArrowRight')
  await expect.poll(screenOf, { timeout: 10_000 }).not.toBe(second)
  await page.keyboard.press('ArrowLeft')
  await expect.poll(screenOf, { timeout: 10_000 }).toBe(second)
  // No trap: Tab leaves the heading for the screen's controls.
  await page.keyboard.press('Tab')
  expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe('BODY')
})
