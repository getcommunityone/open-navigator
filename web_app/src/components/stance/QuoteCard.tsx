import type { CSSProperties, ReactNode } from 'react'
import { highlightSnippet } from '../../lib/highlight'
import { clockTime } from '../../lib/youtubeEmbed'
import type { Stance } from '../../utils/boxSplit'
import { BOX_COLORS, STANCE_LABEL } from '../home/storyColors'
import { aiSummary, initialsOf, playLabel, quoteDate, recordedRole } from './quoteCardUtils'
import './QuoteCard.css'

export interface QuoteCardProps {
  /** "De Soto, MO", from the record. */
  place: string
  /** ISO date of the meeting, or null when the record has none. */
  date?: string | null
  /** The verbatim passage; matched words in <mark> (rendered with highlightSnippet, React-escaped). */
  quote: string
  /** The speaker's recorded side; absent for a meeting passage. */
  side?: Stance | null
  /** The name as served ("Rob D."), never more than the record gives. */
  speakerName?: string | null
  /** The real role on record ("Resident"). */
  role?: string | null
  /** The item the comment is on (decision headline): shown as "On: …". */
  item?: string | null
  /** The meeting's title, for a meeting passage with no speaker. */
  meeting?: string | null
  /** A short line on where the public stood at this meeting (#1230), e.g. "Public: Favor gun rights" or
   *  "Mentions gun control; no public stance in this meeting"; none → nothing shown. */
  stanceNote?: string | null
  /** The recording's YouTube id: its real thumbnail is shown. None → no image block. */
  videoId?: string | null
  /** Seconds into the recording where the passage starts. */
  startSeconds?: number | null
  /** The recording at that moment, opened by the image when there is no onPlay. */
  url?: string | null
  /** Play in place (the caller's video popup) instead of opening `url`. */
  onPlay?: () => void
  /** The meeting's AI summary from the record (#1124), clamped to about 3 lines and labelled; none → nothing shown. */
  summary?: string | null
  /** The meeting page in the app, with the scope already in its query (#1124); none → no link. */
  analysisUrl?: string | null
  /** `card`: with the recording image; `header`: no image (the meeting video popup, which plays the video itself). */
  variant?: 'card' | 'header'
  className?: string
  style?: CSSProperties
  /** Extra lines under the card's text (counts, links), from the caller. */
  children?: ReactNode
}

/** Text colours for the side label: the box colour, darkened only where the box colour is too light to read as text. */
// A question is drawn as No side on the maps (#1110), so its label takes the same colour.
const SIDE_TEXT: Record<Stance, string> = { ...BOX_COLORS }

function PlayGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
      <path d="M8 5.5v13l11-6.5z" fill="currentColor" />
    </svg>
  )
}

/**
 * A quoted moment from a meeting, in the owner's card format (#1108): the meeting's real recording thumbnail with a play
 * button, where and when, the verbatim quote large, and a speaker row (an initials circle, the name as served, the side and
 * the real role or item). Only what the record holds is shown: no photo of anyone, no invented line; a missing field is left
 * out. Wide cards (560px and up) put the image on the left; narrower ones stack.
 */
export default function QuoteCard({
  place,
  date,
  quote,
  side,
  speakerName,
  role,
  item,
  meeting,
  stanceNote,
  videoId,
  startSeconds,
  url,
  onPlay,
  summary,
  analysisUrl,
  variant = 'card',
  className,
  style,
  children,
}: QuoteCardProps) {
  const when = quoteDate(date)
  const from = variant === 'header' && startSeconds != null && startSeconds > 0 ? `from ${clockTime(startSeconds)}` : null
  const where = [place, when, from].filter(Boolean).join(' · ')
  const initials = initialsOf(speakerName)
  const roleShown = recordedRole(role)
  const hasSpeaker = Boolean(speakerName || side || roleShown)
  const line = [roleShown, item ? `On: ${item}` : null].filter(Boolean).join(' · ')
  const showImage = variant === 'card' && Boolean(videoId)
  const label = playLabel(startSeconds)
  const summaryShown = aiSummary(summary)
  const media = showImage ? (
    <>
      <img src={`https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`} alt={`Recording of the ${place} meeting`} loading="lazy" />
      <span className="qcard-play">
        <span className="qcard-play-btn">
          <PlayGlyph />
        </span>
        <span className="qcard-play-label">{label}</span>
      </span>
    </>
  ) : null

  return (
    <figure className={`qcard qcard--${variant}${className ? ` ${className}` : ''}`} style={style}>
      <div className={`qcard-in${showImage ? ' has-media' : ''}`}>
        {showImage &&
          (onPlay ? (
            <button type="button" className="qcard-media" onClick={onPlay} aria-label={`${label}: recording of the ${place} meeting`}>
              {media}
            </button>
          ) : url ? (
            <a className="qcard-media" href={url} target="_blank" rel="noopener noreferrer" aria-label={`${label}: recording of the ${place} meeting (opens YouTube)`}>
              {media}
            </a>
          ) : (
            <div className="qcard-media">{media}</div>
          ))}
        <div className="qcard-text">
          <p className="qcard-where">{where}</p>
          {!hasSpeaker && <p className="qcard-meeting">{meeting ? `In the meeting · ${meeting}` : 'In the meeting'}</p>}
          {stanceNote && <p className="qcard-stance">{stanceNote}</p>}
          <blockquote className="qcard-quote">
            <span className="qcard-qmark" aria-hidden="true">
              “
            </span>
            {highlightSnippet(quote)}
            <span className="qcard-qmark-end" aria-hidden="true">
              ”
            </span>
          </blockquote>
          {hasSpeaker && (
            <figcaption className="qcard-speaker">
              {initials && (
                <span className="qcard-avatar" aria-hidden="true">
                  {initials}
                </span>
              )}
              <span className="qcard-who">
                <span className="qcard-name-row">
                  {speakerName && <span className="qcard-name">{speakerName}</span>}
                  {side && (
                    <span className="qcard-side" style={{ color: SIDE_TEXT[side] }}>
                      <span className="qcard-side-dot" style={{ background: BOX_COLORS[side] }} aria-hidden="true" />
                      {STANCE_LABEL[side]}
                    </span>
                  )}
                </span>
                {line && <span className="qcard-line">{line}</span>}
              </span>
            </figcaption>
          )}
          {summaryShown && (
            <div className="qcard-summary">
              <span className="qcard-summary-label">AI summary</span>
              <p className="qcard-summary-text">{summaryShown}</p>
            </div>
          )}
          {analysisUrl && (
            <p className="qcard-analysis">
              <a href={analysisUrl}>Open the meeting analysis →</a>
            </p>
          )}
          {children}
        </div>
      </div>
    </figure>
  )
}
