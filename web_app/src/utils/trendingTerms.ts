// Pure helpers for the "Trending in meetings" chip row (#1399).
import type { TrendSort, TrendTerm } from '../api/trendingTerms'

/** The chip row's two sorts (the API also serves `volume`). */
export type TrendChipSort = Extract<TrendSort, 'rising' | 'hot'>

export function parseTrendSort(v: string | null | undefined): TrendChipSort {
  return v === 'hot' ? 'hot' : 'rising'
}

const pct = (v: number) => `${(v * 100).toFixed(v < 0.01 ? 1 : 0)}%`

/** Short change label: "+120%", "new this year" (not said last year), or null when it can't be computed. */
export function riseLabel(t: Pick<TrendTerm, 'rise' | 'meetings_a' | 'share_a' | 'share_b'>): string | null {
  if (t.meetings_a === 0 || !t.share_a) return t.share_b ? 'new this year' : null
  if (t.rise == null) return null
  const ch = Math.round((t.rise - 1) * 100)
  return `${ch >= 0 ? '+' : '−'}${Math.abs(ch).toLocaleString('en-US')}%`
}

/** The chip's screen-reader label, all from the row's real counts. */
export function chipAriaLabel(t: TrendTerm, sort: TrendChipSort, yearA: string, yearB: string): string {
  const shares =
    t.share_a != null && t.share_b != null
      ? `said in ${pct(t.share_a)} of recorded meetings in ${yearA} and ${pct(t.share_b)} in ${yearB}`
      : `said in ${t.meetings_b.toLocaleString('en-US')} meetings in ${yearB}`
  const lead = sort === 'hot' ? 'heated in public comment' : 'rising'
  return `${t.term}: ${lead}, ${shares}, ${t.n_jurisdictions.toLocaleString('en-US')} governments. Show the meetings.`
}

/** Scope label for the row: the API's normalised scope (state or national); a requested city is answered by its state. */
export function trendScopeLabel(stateName: string | null, requestedCity: string | null): string {
  if (!stateName) return 'National'
  return requestedCity ? `${stateName} (counted per state, not per city)` : stateName
}

/** "1:02:03" for a start offset, so a quote links to its moment in the recording. */
export function clockLabel(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

/** Link to the moment in the recording when we know it (YouTube `t=`), else the recording. */
export function momentUrl(videoUrl: string | null, startSeconds: number | null): string | null {
  if (!videoUrl) return null
  if (startSeconds == null || !/youtu\.?be/.test(videoUrl)) return videoUrl
  const sep = videoUrl.includes('?') ? '&' : '?'
  return `${videoUrl}${sep}t=${Math.floor(startSeconds)}s`
}
