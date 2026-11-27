import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import type { TopicDecision } from '../../api/topics'
import { DecisionPanel } from './TopicRecordCards'

// Test stand-ins, not warehouse figures.
const dec = (id: string): TopicDecision => ({
  event_decision_id: id,
  title: `Decision ${id}`,
  excerpt: 'the <mark>firearms</mark> ordinance',
  decision_url: `/decisions/${id}`,
  meeting_url: '/meetings/7',
  video_url: 'https://www.youtube.com/watch?v=abcdefghijk',
  meeting_name: 'City Council',
  meeting_date: '2026-04-08',
  relevance: 'on_topic',
  relevance_basis: 'test',
})

const html = (total: number, n: number) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <DecisionPanel heading="Decisions on gun control" total={total} items={Array.from({ length: n }, (_, i) => dec(String(i)))} testId="t" lead="N decisions." />
    </MemoryRouter>,
  )

describe('DecisionPanel follows the shared display rule (#1289)', () => {
  it('lists a handful of decisions as cards, each linking its decision and meeting', () => {
    const out = html(3, 3)
    expect(out).toContain('data-display="list"')
    expect(out).not.toContain('<details')
    expect(out).toContain('href="/decisions/0"')
    expect(out).toContain('City Council · Apr 8, 2026')
    expect(out).toMatch(/<mark[^>]*>firearms<\/mark>/)
  })
  it('keeps one category under 20 items as a list (the rule, not this panel, decides)', () => {
    expect(html(9, 6)).toContain('data-display="list"')
  })
  it('folds above the list range', () => {
    const out = html(40, 6)
    expect(out).toContain('data-display="units"')
    expect(out).toContain('<details')
    expect(out).toContain('Show the newest 6')
  })
  it('draws nothing for 0', () => {
    expect(html(0, 0)).toBe('')
  })
})
