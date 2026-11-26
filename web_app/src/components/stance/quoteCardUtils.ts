import { clockTime, youtubeVideoId } from '../../lib/youtubeEmbed'

/** The recording's YouTube id: the one given, else the first YouTube URL's (#1108). Null when there is no YouTube recording. */
export function resolveVideoId(videoId: string | null | undefined, ...urls: (string | null | undefined)[]): string | null {
  if (videoId && /^[A-Za-z0-9_-]{11}$/.test(videoId)) return videoId
  for (const u of urls) {
    const id = youtubeVideoId(u)
    if (id) return id
  }
  return null
}

/** Seconds from a YouTube URL's `t=` / `start=` ("7747", "7747s", "2h9m7s"), or null when it has none. */
export function startFromUrl(url: string | null | undefined): number | null {
  if (!url) return null
  let u: URL
  try {
    u = new URL(url)
  } catch {
    return null
  }
  const t = u.searchParams.get('t') ?? u.searchParams.get('start')
  if (!t) return null
  if (/^\d+s?$/.test(t)) return parseInt(t, 10)
  const m = t.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/)
  if (!m || !(m[1] || m[2] || m[3])) return null
  return Number(m[1] ?? 0) * 3600 + Number(m[2] ?? 0) * 60 + Number(m[3] ?? 0)
}

/** The play button's label: "Hear it at 4:07" at a known moment, else "Play recording". */
export function playLabel(startSeconds: number | null | undefined): string {
  return startSeconds != null && Number.isFinite(startSeconds) && startSeconds > 0 ? `Hear it at ${clockTime(startSeconds)}` : 'Play recording'
}

/** Up to two initials from the name as the record gives it ("Rob D." → "RD"); null with no letters. Never a photo (#1108). */
export function initialsOf(name: string | null | undefined): string | null {
  const words = (name ?? '').split(/\s+/).map((w) => w.replace(/[^\p{L}]/gu, '')).filter(Boolean)
  if (!words.length) return null
  const letters = words.length === 1 ? words[0]!.slice(0, 1) : words[0]!.slice(0, 1) + words[words.length - 1]!.slice(0, 1)
  return letters.toUpperCase()
}

/** "May 7, 2026" from an ISO date (or datetime); null when missing or unreadable. */
export function quoteDate(iso: string | null | undefined): string | null {
  if (!iso) return null
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/** The role as recorded, or null when the record's value only says it is missing ("Not stated", "Unknown"). */
export function recordedRole(role: string | null | undefined): string | null {
  const r = (role ?? '').trim()
  return r && !/^(not stated|unknown|n\/?a|none|unspecified)$/i.test(r) ? r : null
}

/** The meeting's AI summary as served, trimmed; null when there is none (#1124). Never a stand-in line. */
export function aiSummary(text: string | null | undefined): string | null {
  const t = (text ?? '').replace(/\s+/g, ' ').trim()
  return t || null
}

/**
 * The meeting page link with the story's scope carried over (#1124; CLAUDE.md, scope travels in the URL): `?state=GA&city=…`
 * appended to the app route the API serves. Only an in-app path ("/meetings/123") is accepted; anything else gives null.
 */
export function scopedMeetingHref(url: string | null | undefined, scope: { state?: string | null; city?: string | null } = {}): string | null {
  if (!url || !url.startsWith('/') || url.startsWith('//')) return null
  const [path, query = ''] = url.split('?', 2)
  const params = new URLSearchParams(query)
  if (scope.state) params.set('state', scope.state)
  if (scope.city) params.set('city', scope.city)
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path!
}
