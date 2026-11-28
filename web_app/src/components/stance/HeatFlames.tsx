/** Comment heat as 1-5 flames (#1386). Nothing when there is no rating (never a guess). */

export const HEAT_METHOD_SENTENCES: Record<string, string> = {
  ai_meeting_analysis: "Rated by the meeting analysis's heat rubric",
  rules: 'Estimated from wording by free rules',
  classifier: 'Rated by a classifier',
}

export function heatLabel(heat: number | null | undefined): string | null {
  return typeof heat === 'number' && heat >= 1 && heat <= 5 ? `Heat ${Math.round(heat)} of 5` : null
}

export function HeatFlames({ heat, method }: { heat: number | null | undefined; method?: string | null }) {
  const label = heatLabel(heat)
  if (!label || heat == null) return null
  const n = Math.round(heat)
  const how = method ? (HEAT_METHOD_SENTENCES[method] ?? method) : null
  return (
    <span className="heat-flames" role="img" aria-label={label} title={how ? `${label}. ${how}.` : label}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} aria-hidden="true" className={i <= n ? 'heat-flame is-on' : 'heat-flame'}>
          {'\u{1F525}'}
        </span>
      ))}
    </span>
  )
}
