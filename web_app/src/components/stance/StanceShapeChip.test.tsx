import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { StanceShapeChip, shapeChipLabel } from './StanceShapeChip'

describe('StanceShapeChip', () => {
  it('labels the shapes that say more than a side', () => {
    expect(shapeChipLabel('conditional')).toBe('Conditional')
    expect(shapeChipLabel('for_concept_against_project')).toBe('Supports the idea, opposes this project')
    expect(shapeChipLabel('concerns_only')).toBe('Concerns raised')
  })

  it('has no chip for a plain side, unclear, or nothing', () => {
    expect(shapeChipLabel('clear_for')).toBeNull()
    expect(shapeChipLabel('clear_against')).toBeNull()
    expect(shapeChipLabel('unclear')).toBeNull()
    expect(shapeChipLabel(null)).toBeNull()
  })

  it('shows the cue phrase verbatim, marked', () => {
    const html = renderToStaticMarkup(<StanceShapeChip shape="conditional" cue="only if they pay their share of water" />)
    expect(html).toContain('Conditional')
    expect(html).toContain('<mark>only if they pay their share of water</mark>')
  })

  it('renders nothing for a plain side', () => {
    expect(renderToStaticMarkup(<StanceShapeChip shape="clear_for" cue="we support" />)).toBe('')
  })
})
