import { useMemo, useState } from 'react'
import { PlayIcon } from '@heroicons/react/24/solid'
import { Banknote, Gavel, LandPlot, Landmark, Server, VideoOff, type LucideIcon } from 'lucide-react'
import {
  INITIAL_THUMBNAIL_STATE,
  onThumbnailError,
  onThumbnailLoad,
  youtubeThumbnailCandidates,
  type ThumbnailKind,
  type ThumbnailState,
} from '../lib/youtubeThumbnail'

/**
 * MeetingThumbnail — the ONE place a YouTube meeting still is rendered. A 16:9
 * image addressed purely by video id off the i.ytimg.com CDN (no YouTube Data
 * API, no quota).
 *
 * It walks the ordered candidate URLs (maxresdefault → sddefault → hqdefault),
 * advancing on each <img onError> AND on a load whose naturalWidth <= 120:
 * for private / removed / processing videos YouTube answers hqdefault with
 * HTTP 200 and a 120x90 grey "…" box, so onError never fires (issue #502).
 *
 * Image-absent behaviour:
 *  - While the still loads, a designed cover sits behind the <img>.
 *  - When every candidate fails, the cover stays and says "No video preview".
 *    It carries only the card's own real facts (government + state, date) and
 *    an icon for the item kind on the card's theme colour — no stock imagery
 *    and no stand-in content (CLAUDE.md No Fabricated Data).
 *  - No video id at all ⇒ renders NOTHING (recording-less cards stay clean).
 */
interface MeetingThumbnailProps {
  /** Bare YouTube video id, e.g. "dQw4w9WgXc8". Falsy ⇒ renders nothing. */
  videoId?: string | null
  /** Accessible label for the still (defaults to a generic meeting-video alt). */
  alt?: string
  /** Extra classes on the wrapper (e.g. fixed width in a row layout). */
  className?: string
  /** Legacy short context line for the cover; used when `place` is absent. */
  label?: string
  /** Government name and state for the cover, e.g. "Bulloch County, GA". */
  place?: string | null
  /** Meeting / decision date: ISO yyyy-mm-dd (formatted) or a display string. */
  date?: string | null
  /** Picks the cover icon (see inferThumbnailKind). Defaults to 'meeting'. */
  kind?: ThumbnailKind
  /** Card theme colour (any CSS colour). Darkened for white-text contrast. */
  accent?: string
}

const KIND_ICON: Record<ThumbnailKind, { icon: LucideIcon; label: string }> = {
  'data-center': { icon: Server, label: 'Data center' },
  zoning: { icon: LandPlot, label: 'Zoning & land use' },
  budget: { icon: Banknote, label: 'Budget & money' },
  decision: { icon: Gavel, label: 'Decision' },
  meeting: { icon: Landmark, label: 'Public meeting' },
}

const DEFAULT_ACCENT = '#1a6b6b'

/** "2026-03-04" → "Mar 4, 2026"; non-ISO strings pass through unchanged. */
function formatThumbnailDate(date?: string | null): string {
  if (!date) return ''
  const iso = /^\d{4}-\d{2}-\d{2}/.exec(date)
  if (!iso) return date
  const d = new Date(`${iso[0]}T00:00:00`)
  if (Number.isNaN(d.getTime())) return date
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/**
 * Designed cover: the theme colour mixed heavily toward near-black, so white
 * text clears WCAG AA even for bright accents (Contested #e0603a mixes to
 * roughly rgb(135,62,40), about 7.9:1 against white).
 */
function ThumbnailCover({
  unavailable,
  place,
  date,
  kind,
  accent,
}: {
  unavailable: boolean
  place: string
  date: string
  kind: ThumbnailKind
  accent: string
}) {
  const { icon: Icon, label: kindLabel } = KIND_ICON[kind]
  return (
    <div
      className="absolute inset-0"
      style={{
        background: `linear-gradient(135deg, color-mix(in srgb, ${accent} 58%, #0b1413) 0%, color-mix(in srgb, ${accent} 32%, #070d0c) 100%)`,
      }}
      {...(unavailable
        ? {
            role: 'img',
            'aria-label': ['No video preview', kindLabel, place, date].filter(Boolean).join(' · '),
          }
        : { 'aria-hidden': true })}
    >
      {/* Kind watermark, bottom-right */}
      <Icon
        aria-hidden
        strokeWidth={1.25}
        className="pointer-events-none absolute -bottom-[18%] -right-[6%] h-[85%] w-auto text-white/[0.09]"
      />
      {unavailable && (
        <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/35 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white/90 ring-1 ring-inset ring-white/20">
          <VideoOff aria-hidden className="h-3 w-3" />
          No video preview
        </span>
      )}
      <div className="absolute inset-x-0 bottom-0 flex items-end gap-2.5 p-2.5 sm:p-3">
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/15 ring-1 ring-inset ring-white/25 sm:h-10 sm:w-10"
          title={kindLabel}
        >
          <Icon aria-hidden className="h-4 w-4 text-white sm:h-5 sm:w-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[12px] font-bold leading-tight text-white sm:text-[13px]">
            {place || kindLabel}
          </span>
          {date && (
            <span className="block truncate text-[11px] font-medium leading-tight text-white/80">{date}</span>
          )}
        </span>
      </div>
    </div>
  )
}

export default function MeetingThumbnail({
  videoId,
  alt,
  className = '',
  label,
  place,
  date,
  kind = 'meeting',
  accent = DEFAULT_ACCENT,
}: MeetingThumbnailProps) {
  const candidates = useMemo(() => youtubeThumbnailCandidates(videoId), [videoId])
  const [walk, setWalk] = useState<ThumbnailState & { id?: string | null }>({
    ...INITIAL_THUMBNAIL_STATE,
    id: videoId,
  })
  // A recycled component (new video id) restarts the candidate walk.
  if (walk.id !== videoId) setWalk({ ...INITIAL_THUMBNAIL_STATE, id: videoId })

  // No video id ⇒ nothing to preview; stay invisible (recording-less card).
  if (candidates.length === 0) return null

  const exhausted = walk.idx >= candidates.length
  const { loaded } = walk

  return (
    <div className={`group/thumb relative aspect-video w-full overflow-hidden bg-[#0f2b2b] ${className}`}>
      {(!loaded || exhausted) && (
        <ThumbnailCover
          unavailable={exhausted}
          place={place || label || ''}
          date={formatThumbnailDate(date)}
          kind={kind}
          accent={accent}
        />
      )}

      {!exhausted && (
        <img
          key={candidates[walk.idx]}
          src={candidates[walk.idx]}
          alt={alt || 'Meeting video'}
          loading="lazy"
          decoding="async"
          draggable={false}
          // YouTube's grey "unavailable" box is a 200, so detect it by size.
          onLoad={(e) => {
            const img = e.currentTarget
            setWalk((s) => ({ ...s, ...onThumbnailLoad(s, img) }))
          }}
          onError={() => setWalk((s) => ({ ...s, ...onThumbnailError(s) }))}
          className={`relative h-full w-full object-cover transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
        />
      )}

      {/* Decorative play affordance over a real still only; the parent handles the click. */}
      {loaded && !exhausted && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover/thumb:bg-black/15"
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/85 opacity-0 shadow-sm transition-opacity duration-150 group-hover/thumb:opacity-100">
            <PlayIcon className="ml-0.5 h-5 w-5 text-[#0f2b2b]" />
          </span>
        </span>
      )}
    </div>
  )
}
