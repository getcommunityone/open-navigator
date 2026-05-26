/** Parse ISO / Postgres timestamptz strings from APIs. */
export function parseApiDateTime(value: string | null | undefined): Date | null {
  if (!value?.trim() || value === '—') return null
  const d = new Date(value.trim())
  return Number.isNaN(d.getTime()) ? null : d
}

const absoluteFormatter = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

/** Local calendar + clock, e.g. "May 25, 2026, 8:55 PM". */
export function formatDateTimeAbsolute(value: string | null | undefined): string {
  const d = parseApiDateTime(value)
  if (!d) return value?.trim() || '—'
  return absoluteFormatter.format(d)
}

function formatRelativeToNow(date: Date): string {
  const diffMs = date.getTime() - Date.now()
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  const absSec = Math.abs(Math.round(diffMs / 1000))
  if (absSec < 45) return rtf.format(Math.round(diffMs / 1000), 'second')
  if (absSec < 45 * 60) return rtf.format(Math.round(diffMs / 60_000), 'minute')
  if (absSec < 22 * 3_600) return rtf.format(Math.round(diffMs / 3_600_000), 'hour')
  if (absSec < 6 * 86_400) return rtf.format(Math.round(diffMs / 86_400_000), 'day')
  return absoluteFormatter.format(date)
}

/** "Updated" line: relative when within a week, otherwise absolute. */
export function formatUpdatedAt(value: string | null | undefined): {
  display: string
  title: string
} {
  const d = parseApiDateTime(value)
  if (!d) {
    const fallback = value?.trim() || '—'
    return { display: fallback, title: fallback }
  }
  const absolute = formatDateTimeAbsolute(value)
  const ageDays = Math.abs(d.getTime() - Date.now()) / 86_400_000
  return {
    display: ageDays < 7 ? formatRelativeToNow(d) : absolute,
    title: absolute,
  }
}
