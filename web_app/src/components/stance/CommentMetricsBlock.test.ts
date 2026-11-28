import { describe, expect, it } from 'vitest'
import { commentMetricsLine, heatSummaryLine, shapeCountsLine } from './CommentMetricsBlock'
import type { DataCenterCommentMetrics } from '../../api/dataCenters'

const metrics = (comments: number, governments: number) => ({ comments, governments }) as unknown as DataCenterCommentMetrics

describe('commentMetricsLine', () => {
  it('names comments and governments for the national scope', () => {
    expect(commentMetricsLine(metrics(1234, 210), { stateName: null, city: null }, 2026)).toBe(
      '1,234 speakers at 210 local governments in 2026',
    )
  })
  it('names the scope when a state is chosen', () => {
    const line = commentMetricsLine(metrics(1, 1), { stateCode: 'IL', stateName: 'Illinois', city: null }, 2026)
    expect(line).toBe('1 speaker at 1 local government in Illinois in 2026')
  })
  it('is null when there are no comments or no data (never a stand-in 0)', () => {
    expect(commentMetricsLine(metrics(0, 0), { stateName: null, city: null }, 2026)).toBeNull()
    expect(commentMetricsLine(undefined, { stateName: null, city: null }, 2026)).toBeNull()
  })
})

describe('shapeCountsLine and heatSummaryLine', () => {
  it('counts each shape on its own, leaving plain sides out', () => {
    const line = shapeCountsLine([
      { key: 'clear_for', count: 40 },
      { key: 'conditional', count: 12 },
      { key: 'for_concept_against_project', count: 5 },
      { key: 'unclear', count: 9 },
    ])
    expect(line).toBe('12 conditional · 5 support the idea, oppose this project')
    expect(shapeCountsLine([{ key: 'clear_for', count: 3 }])).toBeNull()
  })
  it('shows heat only when the API sent a summary', () => {
    expect(heatSummaryLine(null)).toBeNull()
    expect(heatSummaryLine({ speakers_rated: 9, mean: 2.33, peak: 4 })).toBe('Heat average 2.3 of 5, peak 4 (9 speakers rated)')
  })
})
