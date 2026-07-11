import { test, expect } from '@playwright/test'
import { parseLinkifiedParts } from '../linkifiedText'

test.describe('LinkifiedText String Parsing Engine', () => {
  const MOCK_PAYLOADS = [
    {
      name: 'standard url',
      text: 'Check this out https://example.com',
      expectedUrl: 'https://example.com',
      expectedTrailingText: undefined,
    },
    {
      name: 'url with trailing period',
      text: 'Read the docs at https://example.com.',
      expectedUrl: 'https://example.com',
      expectedTrailingText: '.',
    },
    {
      name: 'url with trailing comma',
      text: 'Here is the link https://example.com, hope it helps.',
      expectedUrl: 'https://example.com',
      expectedTrailingText: ', hope it helps.',
    },
    {
      name: 'url enclosed in parentheses',
      text: 'See the policy (https://example.com) for details.',
      expectedUrl: 'https://example.com',
      expectedTrailingText: ') for details.',
    },
    {
      name: 'url enclosed in single quotes',
      text: "See 'https://example.com' for details.",
      expectedUrl: 'https://example.com',
      expectedTrailingText: "' for details.",
    },
    {
      name: 'url containing balanced parentheses',
      text: 'A good read: https://en.wikipedia.org/wiki/E-bike_(policy)',
      expectedUrl: 'https://en.wikipedia.org/wiki/E-bike_(policy)',
      expectedTrailingText: undefined,
    },
    {
      name: 'url containing balanced single quotes (Legistar edge-case)',
      text: "Legistar link: https://seattle.legistar.com/LegislationDetail.aspx?Search='e-bike'",
      expectedUrl: "https://seattle.legistar.com/LegislationDetail.aspx?Search='e-bike'",
      expectedTrailingText: undefined,
    },
    {
      name: 'url with balanced quotes and a trailing comma',
      text: "Check out https://seattle.legistar.com/?Search='e-bike', it is cool.",
      expectedUrl: "https://seattle.legistar.com/?Search='e-bike'",
      expectedTrailingText: ', it is cool.',
    }
  ]

  for (const payload of MOCK_PAYLOADS) {
    test(`correctly parses ${payload.name}`, () => {
      const parts = parseLinkifiedParts(payload.text)
      
      // 1. Verify a URL part exists and exactly matches the cleaned expected payload
      const urlPart = parts.find(p => p.type === 'url')
      expect(urlPart).toBeDefined()
      expect(urlPart?.value).toBe(payload.expectedUrl)
      
      // 2. Data Loss Prevention: Verify all extracted parts reconstruct the original text flawlessly
      const reconstructedText = parts.map(p => p.value).join('')
      expect(reconstructedText).toBe(payload.text)
      
      // 3. Boundary precision: Verify the trailing text immediately following the URL 
      if (payload.expectedTrailingText) {
        const urlIndex = parts.findIndex(p => p.type === 'url')
        const followingPart = parts[urlIndex + 1]
        
        expect(followingPart).toBeDefined()
        expect(followingPart?.type).toBe('text')
        
        // Use startsWith since the trailing part node will absorb the rest of the sentence
        expect(followingPart.value.startsWith(payload.expectedTrailingText)).toBeTruthy()
      }
    })
  }
})
