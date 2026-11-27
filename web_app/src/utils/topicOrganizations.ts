// Words for the nonprofits working on a topic (#1345), shared by the story screen and its headline.
import type { OrgMatchMethod, TopicOrganizationItem, TopicOrganizationsResponse } from '../api/topicOrganizations'
import type { CategoryCount } from './displayFit'

const fmt = (n: number) => n.toLocaleString('en-US')

/** Strongest evidence first: the order the list is ranked in and the counts are told in. */
export const METHOD_ORDER: OrgMatchMethod[] = ['named_in_meeting', 'keyword_in_mission', 'keyword_in_name', 'ntee_code', 'cause_tag']

const METHOD_LABEL: Record<OrgMatchMethod, string> = {
  named_in_meeting: 'Named in a meeting',
  keyword_in_mission: 'Mission names it',
  keyword_in_name: 'Name names it',
  ntee_code: 'IRS category in the field',
  cause_tag: 'Cause tag',
}

export function methodLabel(m: OrgMatchMethod): string {
  return METHOD_LABEL[m] ?? m
}

/** The counts per method, for the shared display rule (pickDisplay). */
export function methodCounts(d: TopicOrganizationsResponse | undefined): CategoryCount[] {
  if (!d) return []
  return METHOD_ORDER.map((m) => ({ label: methodLabel(m), count: d.counts?.[m] ?? 0 })).filter((r) => r.count > 0)
}

/** "No nonprofits on record for Georgia." */
export function noNonprofits(label: string): string {
  return label === 'National' ? 'No nonprofits on record yet.' : `No nonprofits on record for ${label}.`
}

/** The screen's headline. */
export function nonprofitsHeadline(d: TopicOrganizationsResponse | undefined, topic: string, label: string): string {
  if (!d) return `Who's working on ${topic}.`
  if (d.total === 0) return noNonprofits(label)
  const where = label === 'National' ? '' : ` in ${label}`
  const named = d.counts?.named_in_meeting ?? 0
  const n = d.total
  const lead = `${fmt(n)} ${n === 1 ? 'nonprofit' : 'nonprofits'}${where} on record working on ${topic}`
  return named > 0 ? `${lead}; ${fmt(named)} named in a meeting on it.` : `${lead}.`
}

const shortDate = (iso: string | null) =>
  iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : null

/** Why the organization is listed, in a sentence (the evidence follows it). */
export function whyListed(o: TopicOrganizationItem, topic: string): string {
  switch (o.match_method) {
    case 'named_in_meeting': {
      const when = shortDate(o.match_date)
      const where = o.match_place ? ` in ${o.match_place}` : ''
      return `Named in a meeting on ${topic}${where}${when ? ` on ${when}` : ''}:`
    }
    case 'keyword_in_mission':
      return 'Its 990 mission names the topic:'
    case 'keyword_in_name':
      return 'Its name names the topic.'
    case 'ntee_code':
      return `IRS category: ${o.match_text ?? o.ntee_code ?? 'a related field'}.`
    default:
      return ''
  }
}

/** "$1.2M revenue (2023)", or null when we have no figure. */
export function revenueLine(o: Pick<TopicOrganizationItem, 'revenue' | 'revenue_tax_year'>): string | null {
  if (o.revenue == null) return null
  const v = o.revenue
  const abs = Math.abs(v)
  const money =
    abs >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : abs >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : abs >= 1e3 ? `$${Math.round(v / 1e3)}K` : `$${fmt(v)}`
  return `${money} revenue${o.revenue_tax_year ? ` (${o.revenue_tax_year})` : ''}`
}

/** 990 missions are often ALL CAPS: read them in sentence case. */
export function sentenceCase(text: string | null | undefined): string | null {
  if (!text) return null
  const letters = text.replace(/[^A-Za-z]/g, '')
  if (letters.length < 8 || letters !== letters.toUpperCase()) return text
  const lower = text.toLowerCase()
  return lower.charAt(0).toUpperCase() + lower.slice(1)
}

/** The mission cut to one line's worth at a word boundary. */
export function oneLine(text: string | null | undefined, max = 140): string | null {
  if (!text) return null
  const t = text.replace(/\s+/g, ' ').trim()
  if (t.length <= max) return t
  const cut = t.slice(0, max)
  const sp = cut.lastIndexOf(' ')
  return `${cut.slice(0, sp > max - 30 ? sp : max)}…`
}

/** "Savannah, GA". */
export function placeOf(o: Pick<TopicOrganizationItem, 'city' | 'state_code'>): string {
  return [o.city, o.state_code].filter(Boolean).join(', ')
}

/** "Gun rights" from "gun rights": the side as a label. */
export function sideLabel(side: string | null | undefined): string | null {
  if (!side) return null
  return side.charAt(0).toUpperCase() + side.slice(1)
}
