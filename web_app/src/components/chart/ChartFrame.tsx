import { useId, useState, type CSSProperties, type ReactNode } from 'react'

/**
 * One entry of a chart's colour key. `color` comes from the same palette constant the visual draws with (BOX_COLORS,
 * MEETING_GREYS, HOUSE_THEME.ramp, ...), never a copy of the hex, so the key cannot drift from the chart (#1409).
 */
export interface LegendItem {
  key: string
  /** Plain words for what this colour or shape means, in the topic's own position words where there are any. */
  label: ReactNode
  color?: string
  /** `square` (default), `dot`, `ring` (a town on record), `hatch` (proposed), `ramp` (darker = more), `line`. */
  shape?: 'square' | 'dot' | 'ring' | 'hatch' | 'ramp' | 'line'
  /** The ramp's colours, light to dark (shape `ramp`). */
  ramp?: readonly string[]
}

export interface ChartFrameProps {
  /** What the chart says, in plain words: the data's own conclusion or "Short-term rental meetings by county · Florida". */
  title: ReactNode
  /** The colour key. Required: a visual never ships without saying what its colours and shapes mean. */
  legend: readonly LegendItem[] | ReactNode
  /** One line saying what the visual shows (the description; the title is the takeaway). */
  caption?: ReactNode
  /** The numbers behind the title, on a tap or hover of the info button (never a guess). */
  titleSupport?: string | null
  /** Where the numbers come from (one short line). */
  source?: ReactNode
  children: ReactNode
  /** The title's element; the page's own heading level decides. */
  titleAs?: 'div' | 'p' | 'h2' | 'h3' | 'h4'
  className?: string
  style?: CSSProperties
  /** Key above the visual instead of below. */
  legendFirst?: boolean
  /** A picker or button beside the title (the county map's "United States" and state picker). */
  controls?: ReactNode
  /** Class names for the title row and the key, for figures that lay them out on a grid. */
  headClassName?: string
  legendClassName?: string
  titleClassName?: string
  /** Extra attributes for the root (a `data-*` hook). */
  rootProps?: Record<string, string | undefined>
}

const SW = 9

function Swatch({ item }: { item: LegendItem }) {
  const color = item.color ?? 'currentColor'
  const base: CSSProperties = { display: 'inline-block', flex: 'none', width: SW, height: SW }
  switch (item.shape) {
    case 'dot':
      return <span aria-hidden="true" style={{ ...base, borderRadius: '50%', background: color }} />
    case 'ring':
      return <span aria-hidden="true" style={{ ...base, borderRadius: '50%', border: `2px solid ${color}`, boxSizing: 'border-box' }} />
    case 'hatch':
      return (
        <span
          aria-hidden="true"
          style={{ ...base, border: `1px solid ${color}`, boxSizing: 'border-box', background: `repeating-linear-gradient(45deg, ${color} 0 1.5px, transparent 1.5px 3.5px)` }}
        />
      )
    case 'line':
      return <span aria-hidden="true" style={{ ...base, height: 0, width: 14, borderTop: `2px solid ${color}`, alignSelf: 'center' }} />
    case 'ramp': {
      const stops = item.ramp && item.ramp.length > 0 ? item.ramp : [color]
      return (
        <span aria-hidden="true" style={{ ...base, width: SW * 2.4, borderRadius: 2, background: stops.length > 1 ? `linear-gradient(90deg, ${stops.join(', ')})` : stops[0] }} />
      )
    }
    default:
      return <span aria-hidden="true" style={{ ...base, borderRadius: 2, background: color }} />
  }
}

const isItems = (l: ChartFrameProps['legend']): l is readonly LegendItem[] => Array.isArray(l)

/**
 * Every map and chart sits in this frame (#1409, owner: "we always need a colour legend ... and a title to say clearly
 * what the chart or map is saying"). `title` and `legend` are required, so a visual cannot be added without them. The key
 * is visible on phones (compact, wraps to one or two lines) and is never behind a "More" control.
 * DOM hooks for tests: `[data-chart-frame]`, `[data-chart-title]`, `[data-chart-legend]`.
 */
export default function ChartFrame({
  title,
  legend,
  source,
  caption,
  titleSupport,
  children,
  titleAs = 'div',
  className = '',
  style,
  legendFirst = false,
  controls,
  headClassName = '',
  legendClassName = '',
  titleClassName = '',
  rootProps,
}: ChartFrameProps) {
  const titleId = useId()
  const [showWhy, setShowWhy] = useState(false)
  const Title = titleAs
  const key = (
    <div data-chart-legend="" className={`chart-frame-legend mt-1 text-[11px] leading-tight text-stone-700 ${legendClassName}`.trim()}>
      {isItems(legend) ? (
        <ul aria-label="Legend" className="m-0 flex list-none flex-wrap gap-x-2.5 gap-y-0.5 p-0">
          {legend.map((it) => (
            <li key={it.key} className="inline-flex items-center gap-1">
              <Swatch item={it} />
              <span>{it.label}</span>
            </li>
          ))}
        </ul>
      ) : (
        legend
      )}
    </div>
  )
  const heading = (
    <Title id={titleId} data-chart-title="" className={`chart-frame-title m-0 text-[13px] font-semibold leading-snug text-stone-900 ${titleClassName}`.trim()}>
      {title}
      {titleSupport && (
        <button
          type="button"
          className="chart-frame-why ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-stone-400 align-middle text-[10px] leading-none text-stone-600"
          aria-expanded={showWhy}
          aria-label="Show the numbers behind this title"
          title={titleSupport}
          onClick={() => setShowWhy((v) => !v)}
        >
          i
        </button>
      )}
    </Title>
  )
  const why = titleSupport && showWhy ? <div data-chart-why="" className="m-0 mb-1 text-[11px] leading-snug text-stone-600">{titleSupport}</div> : null
  const cap = caption ? <div data-chart-caption="" className="chart-frame-caption m-0 mb-1 text-[11px] leading-snug text-stone-600">{caption}</div> : null
  return (
    <div data-chart-frame="" role="group" aria-labelledby={titleId} className={`chart-frame ${className}`.trim()} style={style} {...rootProps}>
      {controls ? (
        <div className={`chart-frame-head mb-1 flex flex-wrap items-center justify-between gap-2 ${headClassName}`.trim()}>
          {heading}
          {controls}
        </div>
      ) : (
        <div className={`chart-frame-head mb-1 ${headClassName}`.trim()}>{heading}</div>
      )}
      {why}
      {cap}
      {legendFirst && key}
      {children}
      {!legendFirst && key}
      {source && <p className="chart-frame-source m-0 mt-0.5 text-[10.5px] leading-tight text-stone-500">{source}</p>}
    </div>
  )
}
