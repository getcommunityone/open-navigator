// Pure helpers for the Where towns stand gauge (#1438).
import type { BandFilter, RankingPlace, SizeBand } from '../api/rankings'

export const BAND_LABEL: Record<SizeBand, string> = {
  large: 'large places (250,000+)',
  mid: 'mid-size places (50,000 to 250,000)',
  small: 'small places (under 50,000)',
  unknown: 'places of unknown size',
}
export const BAND_SHORT: Record<SizeBand, string> = { large: 'large', mid: 'mid-size', small: 'small', unknown: 'unknown-size' }
export const BANDS: BandFilter[] = ['large', 'mid', 'small']

/** Topic names read mid-sentence in lower case ("data centers"), unless they carry their own capitals ("ICE"). */
export function topicPhrase(name: string): string {
  return /[A-Z]/.test(name.slice(1)) ? name : name.toLowerCase()
}

export interface Summary {
  ranked: number
  against: number
  for: number
  medianShrunk: number | null
}

/** Counts from the places actually drawn, so the title always matches the active filter. */
export function summarize(places: RankingPlace[]): Summary {
  const ranked = places.filter((p) => p.is_ranked)
  const sorted = ranked.map((p) => p.shrunk_against_share).sort((a, b) => a - b)
  const mid = sorted.length >> 1
  const median = sorted.length === 0 ? null : sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
  return {
    ranked: ranked.length,
    against: ranked.filter((p) => p.shrunk_against_share > 0.5).length,
    for: ranked.filter((p) => p.shrunk_against_share < 0.5).length,
    medianShrunk: median,
  }
}

/** The gauge title: the takeaway in words, from real counts. */
export function takeaway(name: string, ranked: number, against: number, forCount: number): string {
  const t = topicPhrase(name)
  if (ranked <= 0) return `Too few speakers to rank any place yet on ${t}`
  if (against > forCount) return `Most places that discussed ${t} leaned against: ${against} of ${ranked}`
  if (forCount > against) return `Most places that discussed ${t} leaned for: ${forCount} of ${ranked}`
  return `Places were split on ${t}: ${against} leaned against and ${forCount} leaned for, of ${ranked}`
}

/** 0 = all against (left), 1 = all for (right). Ranked places use the shrunk share, unranked the raw share. */
export function gaugeX(p: Pick<RankingPlace, 'is_ranked' | 'shrunk_against_share' | 'against_share'>): number {
  const a = p.is_ranked ? p.shrunk_against_share : p.against_share
  return Math.min(1, Math.max(0, 1 - a))
}

export function sided(p: Pick<RankingPlace, 'speakers_for' | 'speakers_against'>): number {
  return p.speakers_for + p.speakers_against
}

export function placeAria(p: RankingPlace): string {
  const n = sided(p)
  return `${p.jurisdiction_name}, ${p.state_code}: ${p.speakers_against} of ${n} speakers against${p.is_ranked ? '' : ' (too few speakers to rank)'}`
}

/** Beeswarm-lite: dots closer than `minGap` (fraction of track) are pushed to different lanes. Returns a lane per input index. */
export function assignLanes(xs: number[], minGap = 0.045, maxLanes = 7): number[] {
  const order = xs.map((_x, i) => i).sort((a, b) => xs[a] - xs[b])
  const laneLast: number[] = []
  const lanes = new Array<number>(xs.length).fill(0)
  for (const i of order) {
    let lane = laneLast.findIndex((last) => xs[i] - last >= minGap)
    if (lane < 0) lane = laneLast.length < maxLanes ? laneLast.length : laneLast.indexOf(Math.min(...laneLast))
    laneLast[lane] = xs[i]
    lanes[i] = lane
  }
  return lanes
}

/** Where a place's evidence lives: Browse Topics on the topic, scoped to the place (BrowseTopics reads topic_id, state, city). */
export function evidenceHref(topicId: number, p: Pick<RankingPlace, 'jurisdiction_name' | 'state_code'>): string {
  const q = new URLSearchParams({ topic_id: String(topicId), state: p.state_code, city: p.jurisdiction_name })
  return `/browse-topics?${q.toString()}`
}

export function dateLabel(iso: string | null): string {
  if (!iso) return 'not on record'
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}
