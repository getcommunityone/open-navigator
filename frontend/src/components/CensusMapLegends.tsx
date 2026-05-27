import { useId, useState } from 'react'
import { SwatchIcon } from '@heroicons/react/24/outline'
import {
  CENSUS_SCALES,
  bubbleFillFromT,
  bubbleRadiusPx,
  colorFromT,
  metricToDisplayT,
  type CensusScaleId,
} from '../utils/censusMapTransforms'
import type { CensusValueMode } from '../utils/censusMapValueMode'
import type { CensusChoroLegendSemantics } from '../utils/censusDataDictionary'
import { InfoHelpTrigger } from './InfoHelpTrigger'

const CHORO_LEGEND_GRADIENT_STOPS = 17

function LabelWithInfo({
  label,
  help,
  labelClassName = 'text-xs font-semibold uppercase tracking-wide text-slate-500',
}: {
  label: string
  help: string
  labelClassName?: string
}) {
  return (
    <span className="inline-flex items-center gap-1 shrink-0">
      <span className={labelClassName}>{label}</span>
      <InfoHelpTrigger help={help} topic={label} align="left" />
    </span>
  )
}

export function ChoroplethLegend({
  min,
  max,
  scale,
  format,
  valueMode = 'raw',
  extentPoolsAllVintages = false,
  metricHelp,
  semantics,
  letterGradeLegend,
}: {
  min: number
  max: number
  scale: CensusScaleId
  format: (v: number) => string
  valueMode?: CensusValueMode
  extentPoolsAllVintages?: boolean
  metricHelp?: string
  semantics?: CensusChoroLegendSemantics | null
  letterGradeLegend?: import('react').ReactNode
}) {
  const legendHelpPanelId = useId()
  const [legendHelpOpen, setLegendHelpOpen] = useState(false)
  const n = CHORO_LEGEND_GRADIENT_STOPS
  const stops = Array.from({ length: n }, (_, i) => {
    const u = n <= 1 ? 0 : i / (n - 1)
    const v = min + u * (max - min)
    const t = metricToDisplayT(v, min, max, scale) ?? 0
    return { offset: `${u * 100}%`, color: colorFromT(t), value: v }
  })
  const tickUs = [0, 0.25, 0.5, 0.75, 1] as const
  const gradId = `census-ramp-${scale}-${Math.round(min)}-${Math.round(max)}`
  const legendInfoBody = [
    'Legend maps the displayed value to color using the selected transform. When multi-year data is loaded, low/high can be pooled across years so colors stay comparable as you change year.',
    metricHelp,
  ]
    .filter(Boolean)
    .join('\n\n')
  const legendFootnote = `Stops are evenly spaced in mapped value range; shading follows the selected transform (${CENSUS_SCALES.find((x) => x.id === scale)?.label ?? scale}). ${
    valueMode === 'raw'
      ? extentPoolsAllVintages
        ? 'Percentile band (~4th–96th pct.) is computed across all years in the slider when multi-year trend data is present, so colors stay comparable as you change year.'
        : 'Extremes use percentile clipping so outliers do not wash out the map.'
      : valueMode === 'yoy'
        ? 'Legend shows percent change vs the prior year in the slider order.'
        : 'Legend shows percent difference from the national benchmark (population-weighted state composite when available).'
  }${
    extentPoolsAllVintages && valueMode !== 'raw'
      ? ' Endpoints pool all years from trend data so the scale stays fixed while you scrub the year slider.'
      : ''
  }`
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3 shadow-sm">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-600 mb-2">
        <SwatchIcon className="h-4 w-4 shrink-0" />
        {metricHelp ? (
          <LabelWithInfo label="What the colors mean" help={metricHelp} />
        ) : (
          <span>What the colors mean</span>
        )}
      </div>
      {semantics ? (
        <>
          <div className="mb-1 flex items-center justify-between gap-2 px-0.5 text-[10px] font-semibold text-slate-700">
            <span className="min-w-0 text-left leading-tight">{semantics.lowEnd}</span>
            <span className="shrink-0 text-slate-400" aria-hidden>
              ←→
            </span>
            <span className="min-w-0 text-right leading-tight">{semantics.highEnd}</span>
          </div>
          <p className="mb-2 text-[10px] leading-snug text-slate-600">{semantics.gradientHint}</p>
        </>
      ) : null}
      <svg width="100%" height="52" viewBox="0 0 260 52" preserveAspectRatio="xMidYMid meet" className="max-w-full">
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
            {stops.map((s, i) => (
              <stop key={i} offset={s.offset} stopColor={s.color} />
            ))}
          </linearGradient>
        </defs>
        <rect x="8" y="8" width="244" height="14" rx="3" fill={`url(#${gradId})`} stroke="#94a3b8" strokeWidth="0.5" />
        {tickUs.map((frac) => (
          <text key={frac} x={8 + frac * 244} y="44" fontSize="9" fill="#475569" textAnchor="middle">
            {format(min + frac * (max - min))}
          </text>
        ))}
      </svg>
      {letterGradeLegend ? (
        <div className="mt-2 border-t border-slate-200/90 pt-2">{letterGradeLegend}</div>
      ) : null}
      <div className="mt-2">
        <button
          type="button"
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-amber-200/90 bg-amber-50/60 px-2.5 py-1.5 text-xs font-medium text-amber-950/90 shadow-sm hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 sm:w-auto sm:justify-start"
          aria-expanded={legendHelpOpen}
          aria-controls={legendHelpPanelId}
          onClick={() => setLegendHelpOpen((v) => !v)}
        >
          <span>How to read this legend</span>
          <span
            className={`text-[10px] text-slate-500 transition-transform ${legendHelpOpen ? 'rotate-180' : ''}`}
            aria-hidden
          >
            ▼
          </span>
        </button>
        {legendHelpOpen ? (
          <div
            id={legendHelpPanelId}
            className="mt-2 rounded-md border border-amber-100/90 bg-amber-50/45 px-2.5 py-2 space-y-2"
            role="region"
            aria-label="How to read this legend"
          >
            <p className="text-[11px] text-slate-800 leading-snug whitespace-pre-wrap">{legendInfoBody}</p>
            <p className="text-[10px] text-slate-600 leading-snug">{legendFootnote}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function BubbleLegend({
  min,
  max,
  scale,
  format,
  metricHelp,
  letterGradeLegend,
}: {
  min: number
  max: number
  scale: CensusScaleId
  format: (v: number) => string
  metricHelp?: string
  letterGradeLegend?: import('react').ReactNode
}) {
  const legendHelpPanelId = useId()
  const [legendHelpOpen, setLegendHelpOpen] = useState(false)
  const refs = [0.15, 0.5, 0.88].map((u) => min + u * (max - min))
  const items = refs.map((v) => ({
    v,
    r: bubbleRadiusPx(v, min, max, scale, 4, 22),
    t: metricToDisplayT(v, min, max, scale),
    label: format(v),
  }))
  const bubbleInfoBody = [
    'Circle area encodes the mapped value; color follows the Deep Ocean ramp (steel blue → teal → deep emerald) as on the map.',
    metricHelp,
  ]
    .filter(Boolean)
    .join('\n\n')
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3 shadow-sm">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-600 mb-2">
        {metricHelp ? (
          <LabelWithInfo label="Bubble size scale" help={metricHelp} />
        ) : (
          <span>Bubble size scale</span>
        )}
      </div>
      <div className="flex items-end justify-around gap-2 px-2" style={{ height: 56 }}>
        {items.map((it, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div
              className="rounded-full border border-white shadow"
              style={{
                width: it.r * 2,
                height: it.r * 2,
                backgroundColor: bubbleFillFromT(it.t, 0.9),
              }}
            />
            <span className="text-[10px] text-slate-600 text-center max-w-[72px] leading-tight">{it.label}</span>
          </div>
        ))}
      </div>
      {letterGradeLegend ? (
        <div className="mt-2 border-t border-slate-200/90 pt-2">{letterGradeLegend}</div>
      ) : null}
      <div className="mt-2">
        <button
          type="button"
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-amber-200/90 bg-amber-50/60 px-2.5 py-1.5 text-xs font-medium text-amber-950/90 shadow-sm hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#354F52] focus-visible:ring-offset-2 sm:w-auto sm:justify-start"
          aria-expanded={legendHelpOpen}
          aria-controls={legendHelpPanelId}
          onClick={() => setLegendHelpOpen((v) => !v)}
        >
          <span>How to read this legend</span>
          <span
            className={`text-[10px] text-slate-500 transition-transform ${legendHelpOpen ? 'rotate-180' : ''}`}
            aria-hidden
          >
            ▼
          </span>
        </button>
        {legendHelpOpen ? (
          <div
            id={legendHelpPanelId}
            className="mt-2 rounded-md border border-amber-100/90 bg-amber-50/45 px-2.5 py-2"
            role="region"
            aria-label="How to read this legend"
          >
            <p className="text-[11px] text-slate-800 leading-snug whitespace-pre-wrap">{bubbleInfoBody}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
