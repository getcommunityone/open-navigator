import { describe, expect, it } from 'vitest'
import {
  SEARCH_CATEGORIES,
  SEARCH_CATEGORY_TYPES,
  categoryFromParams,
  countForCategory,
  orgTypesLabel,
  parseOrgTypes,
} from './searchCategories'

describe('search categories (#1221)', () => {
  it('labels the org scope Organizations, never Nonprofits-for-everything', () => {
    const org = SEARCH_CATEGORIES.find((c) => c.id === 'organizations')
    expect(org?.label).toBe('Organizations')
    expect(org?.orgType).toBeUndefined()
    const np = SEARCH_CATEGORIES.find((c) => c.orgType === 'nonprofit')
    expect(np?.types).toBe('organizations')
    expect(np?.child).toBe(true)
  })

  it('offers places and grant opportunities, and every type once in the counts list', () => {
    expect(SEARCH_CATEGORY_TYPES).toContain('jurisdictions')
    expect(SEARCH_CATEGORY_TYPES).toContain('grant_opportunities')
    expect(new Set(SEARCH_CATEGORY_TYPES).size).toBe(SEARCH_CATEGORY_TYPES.length)
  })

  it('parses ?org_type= and drops unknown values', () => {
    expect(parseOrgTypes('church, other ,church,company')).toEqual(['church', 'company'])
    expect(parseOrgTypes(null)).toEqual([])
    expect(orgTypesLabel(['foundation', 'nonprofit'])).toBe('Nonprofits, Foundations')
  })

  it('round-trips the URL to a picker row', () => {
    expect(categoryFromParams('organizations', 'government').label).toBe('Government bodies')
    expect(categoryFromParams('organizations', null).id).toBe('organizations')
    expect(categoryFromParams('jurisdictions', null).label).toBe('Places')
    expect(categoryFromParams(null, null).id).toBe('all')
  })

  it('reads counts from type_totals and org_type_totals, never invents one', () => {
    const tt = { organizations: 38381, bills: 5 }
    const ot = { nonprofit: 37194, church: 168 }
    const by = (id: string) => SEARCH_CATEGORIES.find((c) => c.id === id)!
    expect(countForCategory(by('organizations'), tt, ot)).toBe(38381)
    expect(countForCategory(by('org:church'), tt, ot)).toBe(168)
    expect(countForCategory(by('org:political'), tt, ot)).toBeUndefined()
    expect(countForCategory(by('all'), tt, ot)).toBeUndefined()
    expect(countForCategory(by('org:church'), tt, undefined)).toBeUndefined()
  })
})
