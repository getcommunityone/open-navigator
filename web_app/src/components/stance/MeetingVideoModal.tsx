import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { HOUSE_STYLE } from '../../utils/houseTheme'
import { clockTime, youtubeEmbedUrl } from '../../lib/youtubeEmbed'

export interface MeetingVideo {
  videoId: string
  /** Seconds into the recording where the quoted passage starts; null when untimed. */
  start: number | null
  title: string
  /** "Charlotte, NC · 2026-05-26" */
  sub?: string
  /** The recording on YouTube at that moment, for "Open on YouTube". */
  url: string | null
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
export default function MeetingVideoModal({ video, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)

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
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = overflow
    }
  }, [video, onClose])

  if (!video || typeof document === 'undefined') return null
  return createPortal(
    <div className="folio" style={HOUSE_STYLE}>
      <div className="stance-video-backdrop" onClick={onClose} data-keys-own>
        <div
          ref={boxRef}
          className="stance-video-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="stance-video-title"
          onClick={(e) => e.stopPropagation()}
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
