// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { floatingLabel, toGoLabel } from './floatingNext'

const el = (html: string) => {
  const d = document.createElement('div')
  d.innerHTML = html
  return d.firstElementChild!
}

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
    expect(floatingLabel(el('<button>Next: Sites <span aria-hidden="true">→</span></button>'))).toBe('Next: Sites')
    expect(floatingLabel(el('<button>Ask me <span aria-hidden="true">→</span>\n<kbd aria-hidden="true">Space</kbd></button>'))).toBe('Ask me')
    expect(floatingLabel(el('<button><span>Pause for now</span><kbd>N</kbd></button>'))).toBe('Pause for now')
    expect(floatingLabel(el('<a href="/x">  Take the\n  Data Center Challenge </a>'))).toBe('Take the Data Center Challenge')
  })
})
