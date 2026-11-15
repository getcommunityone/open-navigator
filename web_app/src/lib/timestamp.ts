/**
 * Moments in a meeting recording (CORE-2.1, #240): read a `?t=` value, format seconds for display, and build the
 * link that opens a meeting at a moment.
 */

/** Seconds from `754`, `754.9`, `12m34s`, `1h2m3s`, `12:34` or `1:02:03`; null when the value can't be read. */
export function parseTimestamp(value: string | null | undefined): number | null {
  if (value == null) return null
  const v = value.trim().toLowerCase()
  if (!v) return null

  if (/^\d+(\.\d+)?$/.test(v)) return Math.floor(Number(v))

  const units = v.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/)
  if (units && (units[1] || units[2] || units[3])) {
    const [, h, m, s] = units
    return Number(h ?? 0) * 3600 + Number(m ?? 0) * 60 + Number(s ?? 0)
  }

  const clock = v.match(/^(?:(\d+):)?(\d{1,2}):(\d{2})$/)
  if (clock) {
    const [, h, m, s] = clock
    if (Number(s) > 59 || (h !== undefined && Number(m) > 59)) return null
    return Number(h ?? 0) * 3600 + Number(m) * 60 + Number(s)
  }
  return null
}

/** Seconds as H:MM:SS, or M:SS under an hour. */
export function formatTimestamp(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(s / 3600)
  const minutes = Math.floor((s % 3600) / 60)
  const seconds = String(s % 60).padStart(2, '0')
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, '0')}:${seconds}` : `${minutes}:${seconds}`
}

/** The page that opens this meeting's recording at `seconds` (or at the start when unknown). */
export function meetingMomentPath(meetingId: string, seconds: number | null): string {
  const base = `/meetings/${encodeURIComponent(meetingId)}`
  return seconds == null ? base : `${base}?t=${Math.max(0, Math.floor(seconds))}`
}
