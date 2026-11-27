import { describe, expect, it } from 'vitest'
import { isCurrentPage } from './currentPage'

describe('isCurrentPage (the map card’s button)', () => {
  it('is the page when the path and the state match', () => {
    expect(isCurrentPage('/stories/water-fluoridation?state=AL', '/stories/water-fluoridation', '?state=AL')).toBe(true)
  })
  it('ignores extra query values on the page', () => {
    expect(isCurrentPage('/stories/water-fluoridation?state=AL', '/stories/water-fluoridation', '?state=AL&x=1')).toBe(true)
  })
  it('is another page for another state, another story, or a national page', () => {
    expect(isCurrentPage('/stories/water-fluoridation?state=TX', '/stories/water-fluoridation', '?state=AL')).toBe(false)
    expect(isCurrentPage('/stories/data-centers?state=AL', '/', '')).toBe(false)
    expect(isCurrentPage('/stories/water-fluoridation?state=AL', '/stories/water-fluoridation', '')).toBe(false)
  })
})
