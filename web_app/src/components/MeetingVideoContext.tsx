import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import ReactPlayer from 'react-player/youtube'
import { useQuery } from '@tanstack/react-query'
import { PlayIcon } from '@heroicons/react/24/solid'
import { XMarkIcon, FilmIcon } from '@heroicons/react/24/outline'
import api from '../lib/api'
import { extractKeywords, findBestMatch, type Cue } from '../lib/transcriptMatch'

/**
 * MeetingVideoContext — "evidence links" model for the decision page.
 *
 * Any <EvidenceLink text="…the claim…" /> dropped next to an assertion resolves
 * that text against the meeting's timestamped transcript cues (the SAME IDF
 * matcher MeetingPlayer uses) and, on click, opens ONE persistent floating
 * player docked bottom-right (full-width bottom sheet on mobile), seeked to that
 * moment, with the matched cue quoted underneath.
 *
 * HONESTY: timestamps are DERIVED from the real transcript, never fabricated. If
 * a claim has no confident cue match (or the meeting has no transcript), the
 * pill renders nothing rather than inventing a moment.
 */

interface Resolved {
  seconds: number
  label: string
  cueText: string
}

interface MeetingVideoCtx {
  /** A video exists (popout can play it, even with no transcript to match). */
  hasVideoId: boolean
  resolve: (text: string) => Resolved | null
  playClip: (text: string) => void
}

const Ctx = createContext<MeetingVideoCtx | null>(null)

// Minimum IDF score for a match to count as real evidence. Below this the
// keyword overlap is too thin to trust, so we show no pill.
const MIN_MATCH_SCORE = 1.5

function fmt(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`
}

export function MeetingVideoProvider({
  videoId,
  caption,
  children,
}: {
  videoId?: string | null
  caption?: string
  children: ReactNode
}) {
  const playerRef = useRef<ReactPlayer>(null)
  const [mounted, setMounted] = useState(false) // player mounted after first open
  const [open, setOpen] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [ready, setReady] = useState(false)
  const pendingRef = useRef<number | null>(null) // seek queued until player ready
  const [active, setActive] = useState<Resolved | null>(null)

  const { data } = useQuery({
    queryKey: ['meeting-transcript', videoId],
    enabled: !!videoId,
    staleTime: 10 * 60 * 1000,
    queryFn: async () => (await api.get(`/meeting/${videoId}/transcript`)).data,
  })
  const cues: Cue[] = data?.segments ?? []

  const matchText = useCallback(
    (text: string): Resolved | null => {
      if (!videoId || cues.length === 0 || !text?.trim()) return null
      const m = findBestMatch(cues, extractKeywords(text))
      if (!m || m.score < MIN_MATCH_SCORE) return null
      const idxs = m.windowIndices.length ? m.windowIndices : [0]
      const cueText = idxs
        .map((i) => cues[i]?.text)
        .filter(Boolean)
        .join(' ')
      return { seconds: m.startSeconds, label: fmt(m.startSeconds), cueText }
    },
    [videoId, cues],
  )

  const seek = useCallback((seconds: number) => {
    const p = playerRef.current
    if (p && ready) {
      p.seekTo(seconds, 'seconds')
      setPlaying(true)
    } else {
      pendingRef.current = seconds
    }
  }, [ready])

  const playClip = useCallback(
    (text: string) => {
      const resolved = matchText(text)
      const seconds = resolved?.seconds ?? 0
      setActive(resolved ?? { seconds: 0, label: fmt(0), cueText: '' })
      setMounted(true)
      setOpen(true)
      seek(seconds)
    },
    [matchText, seek],
  )

  const onReady = () => {
    setReady(true)
    if (pendingRef.current != null) {
      playerRef.current?.seekTo(pendingRef.current, 'seconds')
      setPlaying(true)
      pendingRef.current = null
    }
  }

  const ctx = useMemo<MeetingVideoCtx>(
    () => ({ hasVideoId: !!videoId, resolve: matchText, playClip }),
    [videoId, matchText, playClip],
  )

  return (
    <Ctx.Provider value={ctx}>
      {children}

      {mounted && videoId && (
        <div
          className={`fixed z-50 transition-all ${open ? 'opacity-100' : 'pointer-events-none opacity-0'} bottom-2 left-2 right-2 sm:bottom-4 sm:left-auto sm:right-4 sm:w-[26rem]`}
        >
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl ring-1 ring-slate-900/5">
            <div className="flex items-center justify-between bg-slate-900 px-3 py-2">
              <span className="flex items-center gap-2 font-mono text-[11px] text-slate-300">
                <FilmIcon className="h-3.5 w-3.5 text-teal-400" />
                {caption || 'Meeting recording'}
              </span>
              <button
                onClick={() => {
                  setOpen(false)
                  setPlaying(false)
                }}
                aria-label="Close video"
                className="rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-white"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>
            <div className="relative w-full bg-black" style={{ aspectRatio: '16 / 9' }}>
              <ReactPlayer
                ref={playerRef}
                url={`https://www.youtube.com/watch?v=${videoId}`}
                width="100%"
                height="100%"
                controls
                playing={playing}
                onReady={onReady}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                config={{ playerVars: { modestbranding: 1, rel: 0 } }}
              />
            </div>
            {active?.cueText && (
              <div className="px-3 py-3">
                <div className="font-mono text-[10px] uppercase tracking-wider text-teal-600">
                  ▶ {active.label}
                </div>
                <p className="mt-1 text-sm italic leading-relaxed text-slate-600">“{active.cueText}”</p>
              </div>
            )}
          </div>
        </div>
      )}
    </Ctx.Provider>
  )
}

/**
 * Inline ▶ mm:ss pill next to a claim. Renders only when the claim text matches
 * a real transcript cue with enough confidence — otherwise nothing.
 */
export function EvidenceLink({ text }: { text?: string | null }) {
  const ctx = useContext(Ctx)
  const resolved = useMemo(() => (ctx && text ? ctx.resolve(text) : null), [ctx, text])
  if (!ctx || !text || !resolved) return null
  return (
    <button
      onClick={() => ctx.playClip(text)}
      title={`Jump to ${resolved.label} in the recording`}
      className="ml-1.5 inline-flex translate-y-px items-center gap-1 rounded-full border border-teal-200 bg-teal-50 px-2 py-0.5 align-middle font-mono text-[11px] font-medium text-teal-700 transition-colors hover:border-teal-400 hover:bg-teal-100"
    >
      <PlayIcon className="h-2.5 w-2.5" />
      {resolved.label}
    </button>
  )
}

/** Plain "Watch recording" trigger for the hero (opens at the start). */
export function WatchRecordingLink({ className = '' }: { className?: string }) {
  const ctx = useContext(Ctx)
  if (!ctx || !ctx.hasVideoId) return null
  return (
    <button
      onClick={() => ctx.playClip('')}
      className={`flex items-center gap-1.5 font-medium text-[#1d6b5f] hover:text-[#155448] ${className}`}
    >
      <FilmIcon className="h-4 w-4" />
      Watch recording
    </button>
  )
}
