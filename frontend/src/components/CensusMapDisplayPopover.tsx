import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { PauseIcon, PlayIcon } from '@heroicons/react/24/outline'
import { CENSUS_SCALES, type CensusScaleId } from '../utils/censusMapTransforms'
import { type CensusValueMode } from '../utils/censusMapValueMode'
import type { CensusMapRailSection } from './CensusMapLeftRail'

interface CensusMapDisplayPopoverProps {
  /** Which display control to show; ``null`` closes the popover. */
  section: CensusMapRailSection | null
  /** Viewport rect of the rail button that opened it (anchors the popover). */
  anchorRect: DOMRect | null
  onClose: () => void
  viz: 'filled' | 'bubble'
  setViz: (v: 'filled' | 'bubble') => void
  scale: CensusScaleId
  setScale: (s: CensusScaleId) => void
  valueMode: CensusValueMode
  setValueMode: (m: CensusValueMode) => void
  vintages: string[]
  displayVintage: string
  onVintageChange: (year: string) => void
  yearHelp: string
  metricFullHelp: string
  playing: boolean
  setPlaying: (v: boolean) => void
}

const POPOVER_WIDTH = 232
const SECTION_TITLE: Record<CensusMapRailSection, string> = {
  year: 'Year',
  view: 'Map view',
  scale: 'Color spread',
  values: 'Numbers on map',
}

/**
 * Compact display-control popover anchored to the left rail. Replaces the old
 * full-height right drawer: each rail icon opens just its own control next to
 * the icon (the interaction the mockup specifies), keeping the map fully
 * visible. Dismissed by Escape, an outside click, or re-clicking the rail icon.
 */
export default function CensusMapDisplayPopover({
  section,
  anchorRect,
  onClose,
  viz,
  setViz,
  scale,
  setScale,
  valueMode,
  setValueMode,
  vintages,
  displayVintage,
  onVintageChange,
  yearHelp,
  metricFullHelp,
  playing,
  setPlaying,
}: CensusMapDisplayPopoverProps) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)

  useEffect(() => {
    if (!section) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [section, onClose])

  // Place the popover just right of the anchoring rail icon, clamped so it
  // never runs off the top/bottom of the viewport once its height is known.
  useLayoutEffect(() => {
    if (!section || !anchorRect) {
      setPos(null)
      return
    }
    const margin = 8
    const height = ref.current?.offsetHeight ?? 0
    const left = Math.min(anchorRect.right + margin, window.innerWidth - POPOVER_WIDTH - margin)
    const maxTop = window.innerHeight - height - margin
    const top = Math.max(margin, Math.min(anchorRect.top, maxTop > margin ? maxTop : margin))
    setPos({ left, top })
  }, [section, anchorRect])

  if (!section) return null

  return (
    <>
      <div className="fixed inset-0 z-[190]" aria-hidden onClick={onClose} />
      <div
        ref={ref}
        role="dialog"
        aria-label={SECTION_TITLE[section]}
        className="fixed z-[200] rounded-xl border border-slate-200 bg-white p-3 shadow-2xl"
        style={{
          width: POPOVER_WIDTH,
          left: pos?.left ?? (anchorRect ? anchorRect.right + 8 : 0),
          top: pos?.top ?? (anchorRect ? anchorRect.top : 0),
          visibility: pos ? 'visible' : 'hidden',
        }}
      >
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            {SECTION_TITLE[section]}
          </span>
          {section === 'year' && vintages.length >= 2 ? (
            <button
              type="button"
              onClick={() => {
                if (!playing) {
                  const oldest = vintages[0]
                  if (oldest && oldest !== displayVintage) onVintageChange(oldest)
                }
                setPlaying(!playing)
              }}
              className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-700 shadow-sm hover:bg-slate-50"
              aria-pressed={playing}
              title={playing ? 'Pause auto-advance' : 'Play years: cycle oldest to newest'}
            >
              {playing ? <PauseIcon className="h-3 w-3" /> : <PlayIcon className="h-3 w-3" />}
              {playing ? 'Pause' : 'Play'}
            </button>
          ) : null}
        </div>

        {section === 'year' ? (
          <>
            <div className="flex flex-wrap items-center gap-1" role="group" aria-label="ACS vintage">
              {vintages.map((y) => {
                const active = y === displayVintage
                return (
                  <button
                    key={y}
                    type="button"
                    onClick={() => {
                      if (playing) setPlaying(false)
                      onVintageChange(y)
                    }}
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold tabular-nums ${
                      active
                        ? 'border-[#354F52] bg-[#354F52] text-white'
                        : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-50'
                    }`}
                  >
                    {y}
                  </button>
                )
              })}
            </div>
            <p className="mt-2 text-[10px] leading-snug text-slate-500 whitespace-pre-wrap">{yearHelp}</p>
          </>
        ) : null}

        {section === 'view' ? (
          <div className="flex overflow-hidden rounded-md border border-slate-200">
            <button
              type="button"
              onClick={() => setViz('filled')}
              className={`flex-1 px-3 py-2 text-xs font-medium ${
                viz === 'filled' ? 'bg-[#354F52] text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              Filled
            </button>
            <button
              type="button"
              onClick={() => setViz('bubble')}
              className={`flex-1 border-l border-slate-200 px-3 py-2 text-xs font-medium ${
                viz === 'bubble' ? 'bg-[#354F52] text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              Bubbles
            </button>
          </div>
        ) : null}

        {section === 'scale' ? (
          <select
            className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-xs text-slate-900 shadow-sm"
            value={scale}
            onChange={(e) => setScale(e.target.value as CensusScaleId)}
          >
            {CENSUS_SCALES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        ) : null}

        {section === 'values' ? (
          <>
            <select
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-xs shadow-sm"
              value={valueMode}
              onChange={(e) => setValueMode(e.target.value as CensusValueMode)}
            >
              <option value="raw">ACS value</option>
              <option value="yoy">% change vs prior year</option>
              <option value="vs_natl">% vs national benchmark</option>
            </select>
            <p className="mt-2 text-[10px] leading-snug text-slate-500 whitespace-pre-wrap">{metricFullHelp}</p>
          </>
        ) : null}
      </div>
    </>
  )
}
