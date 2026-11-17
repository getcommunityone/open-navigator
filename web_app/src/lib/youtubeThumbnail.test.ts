import { describe, it, expect } from 'vitest'
import {
  INITIAL_THUMBNAIL_STATE,
  inferThumbnailKind,
  isYoutubePlaceholder,
  onThumbnailError,
  onThumbnailLoad,
  youtubeThumbnailCandidates,
  type ThumbnailState,
} from './youtubeThumbnail'

// Mocked <img> load events: only `currentTarget.naturalWidth` is read.
const loadEvent = (naturalWidth: number) => ({ currentTarget: { naturalWidth } })

describe('isYoutubePlaceholder', () => {
  it('flags the 120x90 grey "unavailable" still', () => {
    expect(isYoutubePlaceholder(loadEvent(120).currentTarget)).toBe(true)
  })
  it('flags anything narrower (e.g. a zero-size decode)', () => {
    expect(isYoutubePlaceholder(loadEvent(0).currentTarget)).toBe(true)
  })
  it('accepts real stills (hqdefault 480, sddefault 640, maxres 1280)', () => {
    for (const w of [480, 640, 1280]) {
      expect(isYoutubePlaceholder(loadEvent(w).currentTarget)).toBe(false)
    }
  })
})

describe('thumbnail candidate walk', () => {
  const count = youtubeThumbnailCandidates('abc123XYZ_-').length

  it('keeps a real still on load', () => {
    const s = onThumbnailLoad(INITIAL_THUMBNAIL_STATE, loadEvent(1280).currentTarget)
    expect(s).toEqual({ idx: 0, loaded: true })
  })

  it('advances past a placeholder load like an error', () => {
    const s = onThumbnailLoad({ idx: 2, loaded: false }, loadEvent(120).currentTarget)
    expect(s).toEqual({ idx: 3, loaded: false })
  })

  it('private video: maxres 404, sd 404, hq 200-placeholder ⇒ exhausted (fallback)', () => {
    let s: ThumbnailState = INITIAL_THUMBNAIL_STATE
    s = onThumbnailError(s) // maxresdefault 404
    s = onThumbnailError(s) // sddefault 404
    s = onThumbnailLoad(s, loadEvent(120).currentTarget) // hqdefault grey box
    expect(s.loaded).toBe(false)
    expect(s.idx >= count).toBe(true)
  })

  it('public video without HD: maxres 404, sd loads ⇒ shows sd', () => {
    let s: ThumbnailState = INITIAL_THUMBNAIL_STATE
    s = onThumbnailError(s)
    s = onThumbnailLoad(s, loadEvent(640).currentTarget)
    expect(s).toEqual({ idx: 1, loaded: true })
    expect(s.idx < count).toBe(true)
  })
})

describe('inferThumbnailKind', () => {
  it('picks the data center glyph', () => {
    expect(inferThumbnailKind('Data Center Moratorium and Zoning Amendment Initiated')).toBe('data-center')
    expect(inferThumbnailKind('hyperscale data-centre campus')).toBe('data-center')
  })
  it('picks zoning and budget glyphs', () => {
    expect(inferThumbnailKind('Rezoning of parcel 12 approved')).toBe('zoning')
    expect(inferThumbnailKind('FY2027 budget adopted')).toBe('budget')
  })
  it('falls back to the given kind', () => {
    expect(inferThumbnailKind('Proclamation for Arbor Day', 'decision')).toBe('decision')
    expect(inferThumbnailKind(null)).toBe('meeting')
  })
})
