import { useEffect, useMemo, useRef, useState } from 'react'
import ReactPlayer from 'react-player/youtube'
import { useQuery } from '@tanstack/react-query'
import {
  VideoCameraIcon,
  MagnifyingGlassIcon,
  PlayIcon,
  MapPinIcon,
} from '@heroicons/react/24/outline'
import api from '../lib/api'
import { extractKeywords, findBestMatch } from '../lib/transcriptMatch'

/**
 * Embedded meeting recording (react-player) plus a timed, clickable transcript.
 *
 * The transcript cues come from /meeting/{videoId}/transcript. Clicking a cue
 * seeks the player to that second ("jump to points in the meeting"); the cue
 * under the playhead is highlighted and auto-scrolled into view as the video
 * plays. If no transcript exists the player still embeds, sans cues.
 *
 * Reused on the decision and legislation drilldowns — anywhere a meeting has a
 * `meeting_video_id`.
 */

interface TranscriptCue {
  start: number
  text: string
}

interface MeetingTranscript {
  video_id: string
  has_transcript: boolean
  language?: string | null
  segment_count: number
  segments: TranscriptCue[]
}

interface MeetingPlayerProps {
  videoId: string
  /** Optional caption shown under the player (e.g. the meeting name + date). */
  caption?: string
  /**
   * Optional text describing the specific decision/bill on this page (headline +
   * statement). When supplied, the player tries to locate where it was discussed
   * in the transcript and offers a "jump to this moment" seek + cue highlighting.
   */
  targetText?: string
}

/** Seconds -> H:MM:SS (or M:SS for sub-hour) for the cue timestamp chips. */
function formatTimestamp(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(s / 3600)
  const minutes = Math.floor((s % 3600) / 60)
  const seconds = s % 60
  const mm = hours > 0 ? String(minutes).padStart(2, '0') : String(minutes)
  const ss = String(seconds).padStart(2, '0')
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`
}

export default function MeetingPlayer({ videoId, caption, targetText }: MeetingPlayerProps) {
  const playerRef = useRef<ReactPlayer>(null)
  const activeCueRef = useRef<HTMLButtonElement>(null)
  const [playedSeconds, setPlayedSeconds] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [query, setQuery] = useState('')

  const { data, isLoading } = useQuery<MeetingTranscript>({
    queryKey: ['meeting-transcript', videoId],
    queryFn: async () => {
      const response = await api.get(`/meeting/${videoId}/transcript`)
      return response.data
    },
    enabled: !!videoId,
    staleTime: 5 * 60 * 1000,
  })

  const cues = data?.segments ?? []

  // Best-guess location of *this* decision/bill within the transcript, derived
  // by IDF-weighted keyword matching against the page's target text.
  const match = useMemo(() => {
    if (!targetText || cues.length === 0) return null
    return findBestMatch(cues, extractKeywords(targetText))
  }, [cues, targetText])

  const highlightSet = useMemo(
    () => new Set(match?.windowIndices ?? []),
    [match],
  )

  // Index of the cue currently under the playhead: the last cue whose start is
  // <= the current time. Recomputed only when time or cues change.
  const activeIndex = useMemo(() => {
    if (cues.length === 0) return -1
    let lo = 0
    let hi = cues.length - 1
    let found = -1
    while (lo <= hi) {
      const mid = (lo + hi) >> 1
      if (cues[mid].start <= playedSeconds + 0.25) {
        found = mid
        lo = mid + 1
      } else {
        hi = mid - 1
      }
    }
    return found
  }, [cues, playedSeconds])

  // Filtered view of the transcript (case-insensitive substring on cue text).
  const visibleCues = useMemo(() => {
    if (!query.trim()) return cues.map((cue, idx) => ({ cue, idx }))
    const q = query.trim().toLowerCase()
    return cues
      .map((cue, idx) => ({ cue, idx }))
      .filter(({ cue }) => cue.text.toLowerCase().includes(q))
  }, [cues, query])

  // Keep the active cue scrolled into view while playing (but not while the user
  // is filtering, since the active cue may be hidden).
  useEffect(() => {
    if (!query.trim() && playing && activeCueRef.current) {
      activeCueRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [activeIndex, playing, query])

  const seekTo = (seconds: number) => {
    playerRef.current?.seekTo(seconds, 'seconds')
    setPlaying(true)
  }

  return (
    <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
        <VideoCameraIcon className="h-5 w-5" />
        Meeting recording
      </h2>

      {/* Player */}
      <div className="relative w-full overflow-hidden rounded-lg bg-black" style={{ aspectRatio: '16 / 9' }}>
        <ReactPlayer
          ref={playerRef}
          url={`https://www.youtube.com/watch?v=${videoId}`}
          width="100%"
          height="100%"
          controls
          playing={playing}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          progressInterval={500}
          onProgress={({ playedSeconds }) => setPlayedSeconds(playedSeconds)}
          config={{ playerVars: { modestbranding: 1, rel: 0 } }}
        />
      </div>

      {caption && <p className="mt-3 text-sm text-gray-600">{caption}</p>}

      {/* Auto-located moment for this specific decision/bill */}
      {match && (
        <button
          onClick={() => {
            setQuery('')
            seekTo(match.startSeconds)
          }}
          className="mt-3 inline-flex items-center gap-2 rounded-md bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 ring-1 ring-inset ring-amber-200 transition-colors hover:bg-amber-100"
        >
          <MapPinIcon className="h-4 w-4" />
          Jump to where this was discussed
          <span className="font-mono text-xs tabular-nums text-amber-600">
            {formatTimestamp(match.startSeconds)}
          </span>
        </button>
      )}

      {/* Transcript */}
      {isLoading ? (
        <div className="mt-4 text-sm text-gray-500">Loading transcript…</div>
      ) : cues.length > 0 ? (
        <div className="mt-5">
          <div className="flex items-center justify-between gap-3 mb-2">
            <h3 className="text-sm font-semibold text-gray-900">
              Transcript
              <span className="ml-2 font-normal text-gray-400">
                {cues.length.toLocaleString()} cues · click to jump
              </span>
            </h3>
          </div>

          <div className="relative mb-2">
            <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search the transcript…"
              className="w-full rounded-md border border-gray-200 py-2 pl-9 pr-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          <div className="max-h-96 overflow-y-auto rounded-md border border-gray-100 divide-y divide-gray-50">
            {visibleCues.length === 0 ? (
              <div className="p-4 text-sm text-gray-500">No cues match “{query}”.</div>
            ) : (
              visibleCues.map(({ cue, idx }) => {
                const isActive = idx === activeIndex
                const isMatch = highlightSet.has(idx)
                return (
                  <button
                    key={idx}
                    ref={isActive ? activeCueRef : undefined}
                    onClick={() => seekTo(cue.start)}
                    className={`group flex w-full items-start gap-3 px-3 py-2 text-left transition-colors ${
                      isActive
                        ? 'bg-blue-50'
                        : isMatch
                          ? 'bg-amber-50/60 hover:bg-amber-50'
                          : 'hover:bg-gray-50'
                    } ${isMatch ? 'border-l-2 border-amber-400' : 'border-l-2 border-transparent'}`}
                  >
                    <span
                      className={`mt-0.5 inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 font-mono text-xs tabular-nums ${
                        isActive
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-100 text-gray-600 group-hover:bg-blue-100 group-hover:text-blue-700'
                      }`}
                    >
                      <PlayIcon className="h-3 w-3" />
                      {formatTimestamp(cue.start)}
                    </span>
                    <span
                      className={`text-sm leading-relaxed ${
                        isActive ? 'text-gray-900' : 'text-gray-700'
                      }`}
                    >
                      {cue.text}
                    </span>
                  </button>
                )
              })
            )}
          </div>
        </div>
      ) : (
        <a
          href={`https://www.youtube.com/watch?v=${videoId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 hover:underline"
        >
          <VideoCameraIcon className="h-4 w-4" />
          Open on YouTube →
        </a>
      )}
    </div>
  )
}
