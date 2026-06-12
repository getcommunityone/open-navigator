import { useMemo, useState } from 'react'
import { PlayIcon } from '@heroicons/react/24/solid'
import { youtubeThumbnailCandidates } from '../lib/youtubeThumbnail'

/**
 * MeetingThumbnail — a 16:9 YouTube meeting-video still, addressed purely by
 * video id off the i.ytimg.com CDN (no YouTube Data API, no quota).
 *
 * It walks the ordered candidate URLs (maxresdefault → sddefault → hqdefault),
 * advancing on each <img onError>, so we get the HD still when the uploader
 * provided one and silently fall back to the guaranteed hqdefault when they
 * didn't. When there is no video id, OR every candidate has 404'd, it renders
 * NOTHING (returns null) — never a gray "no recording" placeholder. That keeps
 * url-less / recording-less cards looking exactly as they do today, and honors
 * CLAUDE.md (No Fabricated Data): we never stand in fake media.
 */
interface MeetingThumbnailProps {
  /** Bare YouTube video id, e.g. "dQw4w9WgXc8". Falsy ⇒ renders nothing. */
  videoId?: string | null
  /** Accessible label for the still (defaults to a generic meeting-video alt). */
  alt?: string
  /** Extra classes on the wrapper (e.g. fixed width in a row layout). */
  className?: string
}

export default function MeetingThumbnail({ videoId, alt, className = '' }: MeetingThumbnailProps) {
  const candidates = useMemo(() => youtubeThumbnailCandidates(videoId), [videoId])
  // Index into `candidates`; advanced on each load error. Once it runs past the
  // last candidate we have no usable still and render nothing.
  const [idx, setIdx] = useState(0)

  if (candidates.length === 0 || idx >= candidates.length) return null

  return (
    <div className={`group/thumb relative aspect-video w-full overflow-hidden bg-[#0f2b2b] ${className}`}>
      <img
        src={candidates[idx]}
        alt={alt || 'Meeting video'}
        loading="lazy"
        decoding="async"
        draggable={false}
        onError={() => setIdx((i) => i + 1)}
        className="h-full w-full object-cover"
      />
      {/* Lightweight play affordance — purely decorative; the parent handles
          the click, so the overlay never intercepts pointer events. */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover/thumb:bg-black/15"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/85 opacity-0 shadow-sm transition-opacity duration-150 group-hover/thumb:opacity-100">
          <PlayIcon className="ml-0.5 h-5 w-5 text-[#0f2b2b]" />
        </span>
      </span>
    </div>
  )
}
