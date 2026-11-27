import { describe, expect, it } from 'vitest'
import { clockTime, youtubeEmbedUrl, youtubeHoverEmbedUrl, youtubeVideoId } from './youtubeEmbed'

describe('youtubeVideoId (#972)', () => {
  it('reads watch, short and embed URLs', () => {
    expect(youtubeVideoId('https://www.youtube.com/watch?v=7VghnjHd_1w&t=7747s')).toBe('7VghnjHd_1w')
    expect(youtubeVideoId('https://youtu.be/7VghnjHd_1w?t=12')).toBe('7VghnjHd_1w')
    expect(youtubeVideoId('https://m.youtube.com/embed/7VghnjHd_1w')).toBe('7VghnjHd_1w')
  })
  it('is null for anything that is not a YouTube recording', () => {
    expect(youtubeVideoId(null)).toBeNull()
    expect(youtubeVideoId('not a url')).toBeNull()
    expect(youtubeVideoId('https://example.gov/agenda.pdf')).toBeNull()
    expect(youtubeVideoId('https://youtube.com.evil.net/watch?v=7VghnjHd_1w')).toBeNull()
    expect(youtubeVideoId('https://www.youtube.com/watch?v=bad')).toBeNull()
  })
})

describe('youtubeEmbedUrl (#972)', () => {
  it('starts at the quoted moment, in whole seconds, on the no-cookie host', () => {
    const u = new URL(youtubeEmbedUrl('7VghnjHd_1w', 7747.466))
    expect(u.origin + u.pathname).toBe('https://www.youtube-nocookie.com/embed/7VghnjHd_1w')
    expect(u.searchParams.get('start')).toBe('7747')
    expect(u.searchParams.get('autoplay')).toBe('1')
  })
  it('starts at the beginning when the passage has no timing', () => {
    expect(new URL(youtubeEmbedUrl('7VghnjHd_1w', null)).searchParams.has('start')).toBe(false)
    expect(new URL(youtubeEmbedUrl('7VghnjHd_1w', -3)).searchParams.has('start')).toBe(false)
  })
})

describe('clockTime', () => {
  it('formats minutes and hours', () => {
    expect(clockTime(247)).toBe('4:07')
    expect(clockTime(7747.4)).toBe('2:09:07')
  })
})

describe('youtubeHoverEmbedUrl (#1277)', () => {
  it('autoplays muted at the quoted second, inline, with controls, on the privacy-enhanced host', () => {
    const u = youtubeHoverEmbedUrl('7VghnjHd_1w', 247.9)
    expect(u).toContain('https://www.youtube-nocookie.com/embed/7VghnjHd_1w?')
    expect(u).toContain('autoplay=1&mute=1&start=247&playsinline=1&controls=1')
  })
  it('leaves out start with no moment', () => {
    expect(youtubeHoverEmbedUrl('7VghnjHd_1w', null)).toContain('autoplay=1&mute=1&playsinline=1&controls=1')
    expect(youtubeHoverEmbedUrl('7VghnjHd_1w', 0)).not.toContain('start=')
  })
})
