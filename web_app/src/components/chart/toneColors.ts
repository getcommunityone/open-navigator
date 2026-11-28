/**
 * The colour of a tone-coloured mark (an outcome or a side), shared by the chart that draws it and the key that names it
 * (#1409). Mirrors the `.sc-tone-*` rules in stance/storyCharts.css; both read the same CSS variables.
 */
export const TONE_COLOR: Record<string, string> = {
  approved: 'var(--violet)',
  for: 'var(--violet)',
  denied: 'var(--vermilion)',
  against: 'var(--vermilion)',
  tabled: 'var(--ink-3)',
  moratorium: 'var(--magenta)',
  mixed: 'var(--magenta)',
  no_action: 'var(--neutral-data)',
  no_side: 'var(--neutral-data)',
}
