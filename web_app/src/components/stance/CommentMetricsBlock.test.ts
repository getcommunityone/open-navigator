import { describe, expect, it } from 'vitest'
import { commentMetricsLine } from './CommentMetricsBlock'
import type { DataCenterCommentMetrics } from '../../api/dataCenters'

const metrics = (comments: number, governments: number) => ({ comments, governments }) as unknown as DataCenterCommentMetrics

describe('commentMetricsLine', () => {
  it('names comments and governments for the national scope', () => {
    expect(commentMetricsLine(metrics(1234, 210), { stateName: null, city: null }, 2026)).toBe(
      '1,234 public comments at 210 local governments in 2026',
    )
  })
  it('names the scope when a state is chosen', () => {
    const line = commentMetricsLine(metrics(1, 1), { stateCode: 'IL', stateName: 'Illinois', city: null }, 2026)
    expect(line).toBe('1 public comment at 1 local government in Illinois in 2026')
  })
  it('is null when there are no comments or no data (never a stand-in 0)', () => {
    expect(commentMetricsLine(metrics(0, 0), { stateName: null, city: null }, 2026)).toBeNull()
    expect(commentMetricsLine(undefined, { stateName: null, city: null }, 2026)).toBeNull()
  })
})
