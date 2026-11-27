import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { GENERIC_POSITIONS, MISSING_LEGEND, TOPIC_POSITIONS, missingLegend, positionVerdict, topicPositions } from './topicPositions'

// The Jev question definitions: the one source of which way "for" points per topic.
const TOPIC_LEAN = readFileSync(resolve(__dirname, '../../../packages/llm/src/llm/typesafe/topic_lean.py'), 'utf8')
const TOPIC_SLUGS = [...TOPIC_LEAN.matchAll(/^ {4}"([a-z-]+)": TopicDef\(/gm)].map((m) => m[1]!)
/** One topic's `TopicDef(...)` block of topic_lean.py, up to the next topic. */
const blockOf = (slug: string) => {
  const start = TOPIC_LEAN.indexOf(`"${slug}": TopicDef(`)
  const next = TOPIC_LEAN.slice(start + 1).search(/^ {4}"[a-z-]+": TopicDef\(/m)
  return next < 0 ? TOPIC_LEAN.slice(start) : TOPIC_LEAN.slice(start, start + 1 + next)
}
const stanceOf = (slug: string) => {
  const start = TOPIC_LEAN.indexOf(`"${slug}": TopicDef(`)
  const block = TOPIC_LEAN.slice(start, TOPIC_LEAN.indexOf('item=', start))
  const stance = block.slice(block.indexOf('stance=') + 'stance='.length)
  // The Python string literal(s) joined: "a" "b" -> ab.
  return [...stance.matchAll(/"([^"]*)"/g)].map((m) => m[1]).join('')
}

describe('topic position vocabulary', () => {
  it('has words for every topic Jev reads (topic_lean.TOPICS) and for data centers', () => {
    expect(TOPIC_SLUGS.length).toBeGreaterThanOrEqual(6)
    for (const slug of [...TOPIC_SLUGS, 'data-centers']) {
      const w = TOPIC_POSITIONS[slug]
      expect(w, slug).toBeDefined()
      expect(new Set([w!.for, w!.against, w!.split, w!.silent, w!.unread]).size, slug).toBe(5)
    }
  })

  it('keeps split (neutral) and missing distinct, and the legend names both kinds of missing', () => {
    const w = topicPositions('pickleball')
    expect(w.split).toBe('Split')
    expect(w.silent).toBe("Public didn't speak on it")
    expect(w.unread).toBe('No AI reading yet')
    expect(MISSING_LEGEND).toBe("No AI reading yet, or the public didn't speak on it")
  })

  // The stored guns readings (question_version 48468cc5296e) were written by the gun-control question: mostly_supportive =
  // asking for a limit on firearms, mostly_opposed = defending gun rights or backing a Second Amendment sanctuary
  // resolution. The words name both sides (#1237), never "the gun proposal".
  it('guns name both sides of the gun-control question: Favor gun limits / Favor gun rights', () => {
    const g = topicPositions('guns')
    expect(g.for).toBe('Favor gun limits')
    expect(g.against).toBe('Favor gun rights')
    expect(g.split).toBe('Split')
    expect(missingLegend(g)).toBe("No reading yet, or the public didn't speak on it")
    expect(g.forMeans).toMatch(/^Gun limits = a local measure restricting firearms/)
    expect(g.forMeans).toMatch(/Gun rights = opposing such limits or backing a Second Amendment sanctuary/)
    expect(g.forMeans).toMatch(/Not counted: police service weapons, ShotSpotter, tools called guns$/)
    for (const v of Object.values(g)) expect(v).not.toMatch(/proposal|proposed/i)
  })

  // Once the gun-control question is in topic_lean.py on main (#1239), its sides must still match the words.
  it.skipIf(!blockOf('guns').includes('sides='))('guns words match topic_lean\'s gun-control sides', () => {
    const b = blockOf('guns')
    expect(b).toMatch(/gun-control measure/)
    expect(b).toMatch(/asking for limits on guns[\s\S]*are for it/)
    expect(b).toMatch(/defending gun rights[\s\S]*against it/)
  })

  it('short-term rentals follow topic_lean: for = allowing them, against = banning or restricting them', () => {
    expect(stanceOf('short-term-rentals')).toMatch(/^allowing short-term rentals.*against means banning or restricting/)
    const s = topicPositions('short-term-rentals')
    expect(s.for).toBe('Want to allow short-term rentals')
    expect(s.against).toBe('Want limits on short-term rentals')
  })

  it('the other topics point "for" at the thing topic_lean names', () => {
    expect(stanceOf('pickleball')).toMatch(/pickleball courts/)
    expect(topicPositions('pickleball').for).toBe('For the courts')
    expect(stanceOf('license-plate-readers')).toMatch(/license plate reader cameras/)
    expect(topicPositions('flock').for).toBe('For the cameras')
    expect(stanceOf('water-fluoridation')).toMatch(/^keeping or adding fluoride/)
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
