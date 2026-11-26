import type { ReactNode } from 'react'
import SentenceHeading, { type PickerOption } from '../story/SentenceHeading'
import { lc } from '../../utils/matrixStory'
import { pickRandom } from '../../utils/sentenceHeading'
import { trySuggestions } from '../../utils/matrixSuggest'
import type { Metric } from './types'

/**
 * The page's sentence, in ONE place: "Explore [measure] in [place]". Census figures have no video or transcripts, so the page is
 * analysis (Explore), not a story. Change the wording here only.
 */
export const EXPLORE_SENTENCE = { lead: 'Explore ', between: ' in ' } as const

/** The one place the whole story is told for. Single states work in only some screens, so no choice is offered. */
export const PLACE_OPTIONS: PickerOption[] = [{ value: 'us', label: 'the United States' }]

/**
 * The page's heading: a sentence whose blanks are the place and the measure (the year is a small control beside the
 * orientation line). The measure picker lists the bundle's metrics that have data, each with its real median across the
 * geographies in view as a one-line hint, grouped by the bundle's own category when a metric has one. Under it: a Try row of
 * other real metrics and Surprise me.
 */
export default function QuestionHeading({
  metrics,
  metricSlug,
  hasData,
  hintOf,
  onMetric,
  children,
}: {
  metrics: Array<Metric & { category?: string }>
  metricSlug: string
  hasData: (slug: string) => boolean
  /** A real one-line fact about a metric from the loaded data (e.g. "median 12.8%"), or undefined. */
  hintOf: (slug: string) => string | undefined
  onMetric: (slug: string) => void
  children?: ReactNode
}) {
  const usable = metrics.filter((m) => m.slug === metricSlug || hasData(m.slug))
  const options: PickerOption[] = usable.map((m) => ({ value: m.slug, label: m.label, group: m.category, hint: hintOf(m.slug) }))
  const current = metrics.find((m) => m.slug === metricSlug)
  const tries = trySuggestions(metrics, metricSlug, hasData)
  return (
    <SentenceHeading
      headingId="matrix-top"
      parts={[
        EXPLORE_SENTENCE.lead,
        { id: 'metric', label: 'Measure', value: metricSlug, display: lc(current?.label ?? metricSlug), options, onChange: onMetric, searchable: true },
        EXPLORE_SENTENCE.between,
        { id: 'place', label: 'Place', value: 'us', display: PLACE_OPTIONS[0]!.label, options: PLACE_OPTIONS, onChange: () => undefined },
      ]}
      suggestions={tries.map((m) => ({ label: m.label, onSelect: () => onMetric(m.slug) }))}
      surprise={{
        onSurprise: () => {
          const pick = pickRandom(usable.map((m) => ({ value: m.slug, label: m.label })), metricSlug)
          if (!pick) return null
          onMetric(pick.value)
          return `Now showing ${lc(pick.label)}.`
        },
      }}
    >
      {children}
    </SentenceHeading>
  )
}
