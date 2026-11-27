import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { GENERIC_POSITIONS, MISSING_LEGEND, TOPIC_POSITIONS, dataCenterQuoteNote, missingLegend, positionVerdict, quoteStanceNote, topicPositions } from './topicPositions'

// The Jev question definitions: the one source of which way "for" points per topic.
const TOPIC_LEAN = readFileSync(resolve(__dirname, '../../../packages/llm/src/llm/typesafe/topic_lean.py'), 'utf8')
const TOPIC_SLUGS = [...TOPIC_LEAN.matchAll(/^ {4}"([a-z-]+)": TopicDef\(/gm)].map((m) => m[1]!)
/** One topic's `TopicDef(...)` block of topic_lean.py, up to the next topic. */
const blockOf = (slug: string) => {
  const start = TOPIC_LEAN.indexOf(`"${slug}": TopicDef(`)
  const next = TOPIC_LEAN.slice(start + 1).search(/^ {4}"[a-z-]+": TopicDef\(/m)
  return next < 0 ? TOPIC_LEAN.slice(start) : TOPIC_LEAN.slice(start, start + 1 + next)
}
/** A string field of one topic's `TopicDef(...)` (`subject`, `sides`, ...): the Python string literal(s) joined. */
const fieldOf = (slug: string, field: string) => {
  const block = blockOf(slug)
  const start = block.indexOf(`${field}=`)
  if (start < 0) return ''
  const rest = block.slice(start + field.length + 1)
  const end = rest.search(/^ {8}[a-z_]+=/m)
  return [...(end < 0 ? rest : rest.slice(0, end)).matchAll(/"([^"]*)"/g)].map((m) => m[1]).join('')
}

describe('topic position vocabulary', () => {
  it('has words for every topic Jev reads (topic_lean.TOPICS) and for data centers', () => {
    expect(TOPIC_SLUGS.length).toBeGreaterThanOrEqual(5)
    for (const slug of [...TOPIC_SLUGS, 'data-centers']) {
      const w = TOPIC_POSITIONS[slug]
      expect(w, slug).toBeDefined()
      expect(new Set([w!.for, w!.against, w!.split, w!.silent, w!.unread]).size, slug).toBe(5)
    }
  })

  it('keeps split (neutral) and missing distinct, and the legend names both kinds of missing', () => {
    const w = topicPositions('pickleball')
    expect(w.split).toBe('Both sides spoke')
    expect(w.silent).toBe("Public didn't speak on it")
    expect(w.unread).toBe('Not read yet')
    expect(MISSING_LEGEND).toBe("Not read yet, or the public didn't speak on it")
  })

  // The stored guns readings (question_version 48468cc5296e) were written by the gun-control question: mostly_supportive =
  // asking for a limit on firearms, mostly_opposed = defending gun rights or backing a Second Amendment sanctuary
  // resolution. The words name both sides (#1237), never "the gun proposal".
  it('guns name both sides of the gun-control question: Favor gun limits / Favor gun rights', () => {
    const g = topicPositions('guns')
    expect(g.for).toBe('Favor gun limits')
    expect(g.against).toBe('Favor gun rights')
    expect(g.split).toBe('Both sides spoke')
    expect(missingLegend(g)).toBe("No reading yet, or the public didn't speak on it")
    expect(g.forMeans).toMatch(/^Gun limits = a local measure restricting firearms/)
    expect(g.forMeans).toMatch(/Gun rights = opposing such limits or backing a Second Amendment sanctuary/)
    expect(g.forMeans).toMatch(/Not counted: police service weapons, ShotSpotter, tools called guns$/)
    for (const v of Object.values(g)) expect(v).not.toMatch(/proposal|proposed/i)
  })

  // The stored guns readings came from the gun-control question (#1239), now on main: gun limits are "for", gun rights
  // "against". Fails if the question is reworded so that the words above no longer say which side is which.
  it("guns words match topic_lean's gun-control sides", () => {
    const b = blockOf('guns')
    expect(b).not.toMatch(/proposal before the body/)
    expect(fieldOf('guns', 'subject')).toMatch(/^a local gun-control measure/)
    expect(fieldOf('guns', 'sides')).toMatch(/asking for limits on guns.*are for it/)
    expect(fieldOf('guns', 'sides')).toMatch(/defending gun rights.*against it/)
  })

  it('short-term rentals follow topic_lean: for = allowing them, against = banning or restricting them', () => {
    expect(fieldOf('short-term-rentals', 'subject')).toMatch(/^allowing short-term rentals/)
    expect(fieldOf('short-term-rentals', 'sides')).toMatch(/asking for a ban, a cap or a moratorium, are against them/)
    const s = topicPositions('short-term-rentals')
    expect(s.for).toBe('Want to allow short-term rentals')
    expect(s.against).toBe('Want limits on short-term rentals')
  })

  it('the other topics point "for" at the thing topic_lean names', () => {
    expect(fieldOf('pickleball', 'subject')).toMatch(/^pickleball courts/)
    expect(fieldOf('pickleball', 'sides')).toMatch(/asking for more courts, lights or hours are for/)
    expect(topicPositions('pickleball').for).toBe('For the courts')
    expect(fieldOf('license-plate-readers', 'subject')).toMatch(/automated license plate readers/)
    expect(fieldOf('license-plate-readers', 'advanced')).toMatch(/approved a contract, purchase, installation, renewal or expansion/)
    expect(topicPositions('flock').for).toBe('For the cameras')
    // Fluoridation's leans are five positions; the mart rolls support_* up to "for" (keep or start it).
    expect(fieldOf('water-fluoridation', 'advanced')).toMatch(/^The body voted to keep, start, restore or fund fluoridating/)
    expect(topicPositions('water-fluoridation').for).toBe('Keep fluoride in the water')
  })

  it('falls back to generic words for a topic with no question of its own', () => {
    expect(topicPositions('insurance')).toBe(GENERIC_POSITIONS)
  })
})

describe('positionVerdict', () => {
  const c = (against: number, pro: number, split: number, silent = 0) => ({ read: against + pro + split + silent, against, for: pro, split, silent })
  it('a side with more than half of the meetings where the public spoke leads', () => {
    expect(positionVerdict(c(41, 10, 12, 500), 10)).toEqual({ kind: 'majority', side: 'against', count: 41, of: 63 })
    expect(positionVerdict(c(3, 8, 2), 10)).toEqual({ kind: 'majority', side: 'for', count: 8, of: 13 })
  })
  it('half or less on every side is split; silent meetings are not in the denominator', () => {
    expect(positionVerdict(c(5, 5, 0, 900), 10)).toEqual({ kind: 'split', of: 10 })
  })
  it('below the floor there is no conclusion', () => {
    expect(positionVerdict(c(9, 0, 0, 900), 10)).toEqual({ kind: 'too_few', of: 9 })
  })
})

describe('map quote stance line (#1230)', () => {
  it("names the public side in the topic's own words, or says the passage only mentions the topic", () => {
    // The words come from TOPIC_POSITIONS, never hard-coded here: a topic can be reworded without touching this line.
    const w = topicPositions('guns')
    expect(quoteStanceNote('guns', 'guns', 'against')).toBe(`Public: ${w.against}`)
    expect(quoteStanceNote('guns', 'guns', 'for')).toBe(`Public: ${w.for}`)
    expect(quoteStanceNote('guns', 'guns', 'split')).toBe(`At this meeting: ${w.split.toLowerCase()}`)
    expect(quoteStanceNote('guns', 'guns', 'silent')).toBe('Mentions guns; no public stance in this meeting')
    expect(quoteStanceNote('guns', 'guns', null)).toBe('Mentions guns')
  })
  it('never says "AI reading" in the line', () => {
    for (const s of ['against', 'for', 'split', 'silent', null] as const) expect(quoteStanceNote('guns', 'guns', s)).not.toMatch(/AI reading/)
  })
  it('data centers: only the served readings get a line', () => {
    expect(dataCenterQuoteNote('mostly_opposed')).toBe(`Public: ${TOPIC_POSITIONS['data-centers']!.against}`)
    expect(dataCenterQuoteNote('no_public_comment_on_data_center')).toBe('Mentions data centers; no public stance in this meeting')
    expect(dataCenterQuoteNote('mostly_supported')).toBeNull()
    expect(dataCenterQuoteNote('mixed')).toBeNull()
    expect(dataCenterQuoteNote(null)).toBeNull()
  })
})
