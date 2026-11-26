import { describe, expect, it } from 'vitest'
import { companySearchTerm } from './companySearchTerm'

describe('companySearchTerm', () => {
  it('uses the brand marked in the newest quote', () => {
    expect(companySearchTerm('Expedia Group', 'I have a rental property <mark>VRBO</mark> two houses down')).toBe('VRBO')
  })
  it('falls back to the company name without a quote', () => {
    expect(companySearchTerm('Booking Holdings', null)).toBe('Booking Holdings')
    expect(companySearchTerm('Airbnb', 'no mark here')).toBe('Airbnb')
  })
})
