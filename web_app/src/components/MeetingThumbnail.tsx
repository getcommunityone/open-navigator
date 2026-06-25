import { useMemo, useState } from 'react'
import { PlayIcon } from '@heroicons/react/24/solid'
import { BuildingLibraryIcon, VideoCameraSlashIcon } from '@heroicons/react/24/outline'
import { youtubeThumbnailCandidates } from '../lib/youtubeThumbnail'

/**
 * MeetingThumbnail — a 16:9 YouTube meeting-video still, addressed purely by
 * video id off the i.ytimg.com CDN (no YouTube Data API, no quota).
 *
 * It walks the ordered candidate URLs (maxresdefault → sddefault → hqdefault),
 * advancing on each <img onError>, so we get the HD still when the uploader
 * provided one and silently fall back to the guaranteed hqdefault when they
 * didn't.
 *
 * Image-absent behaviour:
 *  - While the still is loading, the branded <ThumbnailFallback> sits BEHIND the
 *    <img>, so a slow/lazy load reads as an intentional cover, not a blank block.
 *  - If every candidate 404s (deleted / private upload), we keep the fallback
 *    instead of the still — an attractive, honest "recording preview unavailable"
 *    cover rather than a flat dark rectangle.
 *  - When there is no video id at all, we render NOTHING (returns null), so
 *    recording-less cards stay clean. This honors CLAUDE.md (No Fabricated Data):
 *    the fallback is an explicit unavailable state, never stand-in media or data.
 */
interface MeetingThumbnailProps {
  /** Bare YouTube video id, e.g. "dQw4w9WgXc8". Falsy ⇒ renders nothing. */
  videoId?: string | null
  /** Accessible label for the still (defaults to a generic meeting-video alt). */
  alt?: string
  /** Extra classes on the wrapper (e.g. fixed width in a row layout). */
  className?: string
  /** Short context line shown on the fallback cover (e.g. a jurisdiction). */
  label?: string
}

/**
 * Branded cover shown behind the still while it loads ('loading'), and in its
 * place when every candidate has 404'd ('unavailable'). A civic gradient +
 * watermark — never a flat dark rectangle. The 'unavailable' variant says
 * plainly what happened: the upload is gone from YouTube.
 */
function ThumbnailFallback({
  variant,
  label,
}: {
  variant: 'loading' | 'unavailable'
  label?: string
}) {
  const unavailable = variant === 'unavailable'
  return (
    <div
      aria-hidden
      className="absolute inset-0 bg-gradient-to-br from-[#15433d] via-[#0f2b2b] to-[#08201f]"
    >
      {/* Soft accent glow, top-right */}
      <span className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-[#0891b2]/25 blur-2xl" />
      {/* Civic watermark, bottom-left */}
      <BuildingLibraryIcon className="pointer-events-none absolute -bottom-6 -left-4 h-32 w-32 text-white/[0.06]" />
      {/* Centered emblem + caption */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 ring-1 ring-inset ring-white/25 backdrop-blur-sm">
          {unavailable ? (
            <VideoCameraSlashIcon className="h-6 w-6 text-white/80" />
          ) : (
            <PlayIcon className="ml-0.5 h-6 w-6 text-white/90" />
          )}
        </span>
        <span className="text-[12px] font-semibold leading-snug text-white/85">
          {unavailable ? 'Video no longer available on YouTube' : label || 'Civic recording'}
        </span>
        {unavailable && label && (
          <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-white/55">
            {label}
          </span>
        )}
      </div>
    </div>
  )
}

export default function MeetingThumbnail({ videoId, alt, className = '', label }: MeetingThumbnailProps) {
  const candidates = useMemo(() => youtubeThumbnailCandidates(videoId), [videoId])
  // Index into `candidates`; advanced on each load error. Once it runs past the
  // last candidate we have no usable still and show the branded fallback.
  const [idx, setIdx] = useState(0)
  const [loaded, setLoaded] = useState(false)

  // No video id ⇒ nothing to preview; stay invisible (recording-less card).
  if (candidates.length === 0) return null

  const exhausted = idx >= candidates.length

  return (
    <div className={`group/thumb relative aspect-video w-full overflow-hidden bg-[#0f2b2b] ${className}`}>
      {/* Branded cover — behind the still while it loads, and on its own (with a
          plain "no longer on YouTube" message) once every candidate has 404'd. */}
      {(!loaded || exhausted) && (
        <ThumbnailFallback variant={exhausted ? 'unavailable' : 'loading'} label={label} />
      )}

      {!exhausted && (
        <img
          src={candidates[idx]}
          alt={alt || 'Meeting video'}
          loading="lazy"
          decoding="async"
          draggable={false}
          onLoad={() => setLoaded(true)}
          onError={() => {
            setLoaded(false)
            setIdx((i) => i + 1)
          }}
          className={`relative h-full w-full object-cover transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
        />
      )}

      {/* Lightweight play affordance — purely decorative; the parent handles
          the click, so the overlay never intercepts pointer events. Only over a
          real still (the fallback carries its own emblem). */}
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
