import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { HOUSE_STYLE } from '../../utils/houseTheme'
import { clockTime, youtubeEmbedUrl } from '../../lib/youtubeEmbed'
import { highlightSnippet } from '../../lib/highlight'

export interface MeetingVideo {
  videoId: string
  /** Seconds into the recording where the quoted passage starts; null when untimed. */
  start: number | null
  title: string
  /** "Charlotte, NC · 2026-05-26" */
  sub?: string
  /** The recording on YouTube at that moment, for "Open on YouTube". */
  url: string | null
  /** The verbatim passage that put the meeting on the chart, matched words in <mark> (#1036). */
  quote?: string | null
  /** Who said it, when known ("Audra T. · Resident"). */
  who?: string | null
}

interface Props {
  video: MeetingVideo | null
  onClose: () => void
}

/**
 * The meeting recording in place (#972). Nothing from YouTube is fetched until this opens: the iframe exists only while
 * `video` is set, so closing removes it and stops playback. Escape, the close button and a click on the backdrop close it;
 * focus goes to the close button on open, stays inside while open, and the caller restores it to the dot it came from.
 */
const STORY_KEYS = new Set([' ', 'Spacebar', 'PageDown', 'PageUp', 'ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'Enter'])

export default function MeetingVideoModal({ video, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const backdropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!video) return
    closeRef.current?.focus()
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
        return
      }
      // The story's own keys (window listeners: Space, PageDown, arrows…) must not move the page behind the dialog. Keys
      // inside the dialog keep their default action (a focused button or link still works); nothing reaches the story.
      if (STORY_KEYS.has(e.key)) {
        e.stopPropagation()
        if (!boxRef.current?.contains(document.activeElement)) e.preventDefault()
      }
      if (e.key !== 'Tab' || !boxRef.current) return
      // Keep focus inside the dialog (the iframe takes its own focus; Tab around the controls).
      const f = [...boxRef.current.querySelectorAll<HTMLElement>('button, a[href], iframe')]
      if (!f.length) return
      const first = f[0]!
      const last = f[f.length - 1]!
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey, true)
    // Lock the page under the dialog: the story scrolls on <html> (and smooth-scrolls with Lenis), so locking <body>
    // alone isn't enough; wheel and touch over the backdrop are stopped outright (the player's iframe gets its own).
    const html = document.documentElement
    const prev = { html: html.style.overflow, body: document.body.style.overflow }
    html.style.overflow = 'hidden'
    document.body.style.overflow = 'hidden'
    // Only the backdrop itself is blocked: the dialog may be taller than a short window and must still scroll
    // (its overscroll-behavior: contain keeps that scroll from chaining to the page).
    const block = (e: Event) => {
      if (e.cancelable && !boxRef.current?.contains(e.target as Node)) e.preventDefault()
    }
    const bd = backdropRef.current
    bd?.addEventListener('wheel', block, { passive: false })
    bd?.addEventListener('touchmove', block, { passive: false })
    return () => {
      document.removeEventListener('keydown', onKey, true)
      bd?.removeEventListener('wheel', block)
      bd?.removeEventListener('touchmove', block)
      html.style.overflow = prev.html
      document.body.style.overflow = prev.body
    }
  }, [video, onClose])

  if (!video || typeof document === 'undefined') return null
  return createPortal(
    <div className="folio" style={HOUSE_STYLE}>
      {/* data-lenis-prevent: the story's smooth scroller must not scroll the page under the dialog. */}
      <div ref={backdropRef} className="stance-video-backdrop" onClick={onClose} data-keys-own data-lenis-prevent>
        <div
          ref={boxRef}
          className="stance-video-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="stance-video-title"
          // Focusable, so a click on its text keeps focus inside the dialog rather than on the page body.
          tabIndex={-1}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          <div className="stance-video-head">
            <div>
              <p className="stance-video-title" id="stance-video-title">
                {video.title}
              </p>
              <p className="stance-video-sub">
                {[video.sub, video.start != null && video.start > 0 ? `from ${clockTime(video.start)}, where the passage starts` : null]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            </div>
            <button ref={closeRef} type="button" className="folio-btn stance-video-close" onClick={onClose} aria-label="Close video">
              Close <span aria-hidden="true">×</span>
            </button>
          </div>
          {video.quote && (
            <blockquote className="stance-video-quote">
              “{highlightSnippet(video.quote)}”
              {video.who && <footer>{video.who}</footer>}
            </blockquote>
          )}
          <div className="stance-video-frame">
            <iframe
              src={youtubeEmbedUrl(video.videoId, video.start)}
              title={`Recording: ${video.title}`}
              allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
              allowFullScreen
              referrerPolicy="strict-origin-when-cross-origin"
            />
          </div>
          {video.url && (
            <p className="stance-video-foot">
              <a href={video.url} target="_blank" rel="noopener noreferrer">
                Open on YouTube ↗
              </a>
            </p>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
