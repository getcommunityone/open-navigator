import { cap, roundWord } from './stanceGame'

/** How many screens are left, in words: "Three to go", "One to go", then "Last one". Never a bare number. */
export function toGoLabel(left: number): string {
  if (left <= 0) return 'Last one'
  return `${cap(roundWord(left))} to go`
}

// The floating "next" bar (#915) repeats a control that is already in the page. Its label is that control's own visible text,
// so the two can never say different things.

/** The visible text of a control: decorative children (`aria-hidden`, key hints) are left out and spaces collapse. */
export function floatingLabel(el: Element): string {
  const walk = (node: Node): string => {
    if (node.nodeType === 3) return node.textContent ?? ''
    if (node.nodeType !== 1) return ''
    const e = node as Element
    if (e.getAttribute('aria-hidden') === 'true' || e.tagName === 'KBD') return ''
    return Array.from(e.childNodes).map(walk).join('')
  }
  return Array.from(el.childNodes).map(walk).join('').replace(/\s+/g, ' ').trim()
}
