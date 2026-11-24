import { describe, expect, it } from 'vitest'
import { floatingLabel, toGoLabel } from './floatingNext'

// Minimal stand-ins for DOM nodes, so the test needs no browser environment: floatingLabel only reads nodeType,
// textContent, tagName, getAttribute and childNodes.
type Child = string | FakeEl
interface FakeEl {
  nodeType: 1
  tagName: string
  childNodes: unknown[]
  getAttribute(name: string): string | null
}
const text = (s: string) => ({ nodeType: 3, textContent: s })
const el = (tag: string, attrs: Record<string, string>, ...children: Child[]): FakeEl => ({
  nodeType: 1,
  tagName: tag.toUpperCase(),
  childNodes: children.map((c) => (typeof c === 'string' ? text(c) : c)),
  getAttribute: (name) => attrs[name] ?? null,
})
const label = (e: FakeEl) => floatingLabel(e as unknown as Element)

describe('toGoLabel', () => {
  it('says what is left in words', () => {
    expect(toGoLabel(3)).toBe('Three to go')
    expect(toGoLabel(1)).toBe('One to go')
    expect(toGoLabel(0)).toBe('Last one')
    expect(toGoLabel(-2)).toBe('Last one')
    expect(toGoLabel(10)).toBe('Ten to go')
  })
})

describe('floatingLabel', () => {
  it('is the visible text of the control, without arrows or key hints', () => {
    expect(label(el('button', {}, 'Next: Sites ', el('span', { 'aria-hidden': 'true' }, '→')))).toBe('Next: Sites')
    expect(
      label(el('button', {}, 'Ask me ', el('span', { 'aria-hidden': 'true' }, '→'), '\n', el('kbd', { 'aria-hidden': 'true' }, 'Space'))),
    ).toBe('Ask me')
    expect(label(el('button', {}, el('span', {}, 'Pause for now'), el('kbd', {}, 'N')))).toBe('Pause for now')
    expect(label(el('a', { href: '/x' }, '  Take the\n  Data Center Challenge '))).toBe('Take the Data Center Challenge')
  })
})
