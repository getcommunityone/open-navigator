import type { ReactNode } from 'react'

/** How a speaker states a position (#1383). Counted on its own, never as both sides. */
export const SHAPE_CHIP_LABELS: Record<string, string> = {
  conditional: 'Conditional',
  for_concept_against_project: 'Supports the idea, opposes this project',
  against_concept_open_to_terms: 'Opposes, open to terms',
  concerns_only: 'Concerns raised',
}

/** The plain sides and "unclear" get no chip: only the shapes that say something more than a side do. */
export function shapeChipLabel(shape: string | null | undefined): string | null {
  return shape ? (SHAPE_CHIP_LABELS[shape] ?? null) : null
}

/**
 * The cue phrase in quotes with the matched words marked. The phrase is a verbatim excerpt from the record
 * (never reworded); React escapes it, so no HTML is injected.
 */
export function CueQuote({ cue }: { cue: string | null | undefined }): ReactNode {
  const text = (cue ?? '').trim()
  if (!text) return null
  return (
    <q className="kpi-drill-cue">
      <mark>{text}</mark>
    </q>
  )
}

export function StanceShapeChip({ shape, cue }: { shape: string | null | undefined; cue?: string | null }) {
  const label = shapeChipLabel(shape)
  if (!label) return null
  return (
    <p className="kpi-drill-meta kpi-drill-shape" data-shape={shape ?? undefined}>
      <span className="kpi-drill-chip">{label}</span> <CueQuote cue={cue} />
    </p>
  )
}
