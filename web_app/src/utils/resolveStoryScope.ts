// Which place a story speaks for (owner, 27 Nov 2026): a place gets its own conclusion only with enough meetings on record.
// Otherwise the story steps up one level at a time, city → county → state → national, to the first level with enough, and
// says why in plain words. The headline, the map's zoom, the counts and the quotes then all use that level, while the URL
// keeps the reader's choice (CLAUDE.md, "Scope label must match the active filter"). Pure, so every step is tested.

/** Meetings a place needs on record for its own conclusion. */
export const MIN_SCOPE_MEETINGS = 5

export type ScopeLevel = 'city' | 'county' | 'state' | 'national'

export interface ScopeCounts {
  /** "data centers": the topic as the explanation names it. */
  topic: string
  stateCode?: string | null
  stateName?: string | null
  city?: string | null
  /** Meetings on record for the city (null while unknown). */
  cityMeetings?: number | null
  /**
   * The county holding the city and its meetings. `'unavailable'` (or undefined) when the topic has no county grain: the
   * county step is skipped and the explanation says so. `'unplaced'`: the topic has a county grain but the city's county
   * isn't on record (#1321).
   */
  county?: { name: string; meetings: number } | 'unavailable' | 'unplaced' | null
  /** Meetings on record for the state (null while unknown). */
  stateMeetings?: number | null
}

export interface ResolvedScope {
  /** The level asked for (from the URL / the chosen place). */
  asked: ScopeLevel
  /** The level the story speaks for. */
  level: ScopeLevel
  stateCode: string | null
  stateName: string | null
  /** Set only at city level. */
  city: string | null
  /** Set only at county level. */
  county: string | null
  /** Meetings at the level used, when known. */
  meetings: number | null
  /** Why the story stepped up, in plain words; null when it speaks for the place asked. */
  reason: string | null
}

const plural = (n: number) => `${n.toLocaleString('en-US')} ${n === 1 ? 'meeting' : 'meetings'}`
const enough = (n: number | null | undefined): n is number => n != null && n >= MIN_SCOPE_MEETINGS

/**
 * The level the story speaks for. While a count is still unknown (null) the place asked is kept, so nothing jumps to a
 * wider place before the numbers arrive.
 */
export function resolveStoryScope(c: ScopeCounts): ResolvedScope {
  const stateCode = c.stateCode ?? null
  const stateName = stateCode ? (c.stateName ?? stateCode) : null
  const city = stateCode ? (c.city?.trim() || null) : null
  const asked: ScopeLevel = city ? 'city' : stateCode ? 'state' : 'national'
  const base = { asked, stateCode, stateName, city: null, county: null }
  const national = (why: string): ResolvedScope => ({ ...base, stateCode: null, stateName: null, level: 'national', meetings: null, reason: why })
  const stateLevel = (why: string | null): ResolvedScope => ({ ...base, level: 'state', meetings: c.stateMeetings ?? null, reason: why })
  const stateOr = (lead: string): ResolvedScope => {
    if (c.stateMeetings == null || enough(c.stateMeetings)) {
      return stateLevel(`${lead}, so this shows ${stateName}${c.stateMeetings != null ? ` (${plural(c.stateMeetings)})` : ''}.`)
    }
    return national(`${lead}, and ${stateName} has only ${plural(c.stateMeetings)}, so this shows the whole country.`)
  }

  if (asked === 'national') return { ...base, level: 'national', meetings: null, reason: null }

  if (asked === 'state') {
    if (c.stateMeetings == null || enough(c.stateMeetings)) return stateLevel(null)
    return national(`${stateName} has only ${plural(c.stateMeetings)} on ${c.topic}, too few to call, so this shows the whole country.`)
  }

  // City asked.
  if (c.cityMeetings == null || enough(c.cityMeetings)) {
    return { ...base, level: 'city', city, meetings: c.cityMeetings ?? null, reason: null }
  }
  const lead = `${city} has ${c.cityMeetings === 0 ? 'no meetings' : `only ${plural(c.cityMeetings)}`} on ${c.topic}, too few to call`
  const county = c.county
  if (county && typeof county === 'object') {
    if (enough(county.meetings)) {
      return {
        ...base,
        level: 'county',
        county: county.name,
        meetings: county.meetings,
        // The county's own figures aren't served yet (#1321 follow-up): the page draws the county at its state, so the
        // reason says the state is what is shown, never that the county's data is (CLAUDE.md: label matches the data).
        reason: `${lead}. ${county.name} has ${plural(county.meetings)}, but figures aren't broken out by county yet, so this shows ${stateName}.`,
      }
    }
    return stateOr(`${lead} (${county.name} has ${plural(county.meetings)})`)
  }
  if (county === 'unplaced') return stateOr(`${lead}. Its county isn't on record`)
  return stateOr(`${lead}. County counts aren't on record for this topic`)
}

/** The scope a story's queries and label use for a resolved level (county is drawn at its state, named in the reason). */
export function scopeForLevel(r: ResolvedScope): { stateCode?: string; stateName: string | null; city: string | null } {
  if (r.level === 'national') return { stateCode: undefined, stateName: null, city: null }
  return { stateCode: r.stateCode ?? undefined, stateName: r.stateName, city: r.level === 'city' ? r.city : null }
}
