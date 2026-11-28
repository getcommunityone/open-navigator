import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import ChartFrame, { type LegendItem } from '../chart/ChartFrame'
import { fetchTopicHeatByYear } from '../../api/topics'
import { pickInsight } from '../../utils/chartInsight'
import { toHeatByYear } from '../chart/insightFacts'
import { boxUnit, columnBoxes } from '../../utils/storyTimeline'
import { HOUSE_STYLE } from '../../utils/houseTheme'
import './storyCharts.css'

interface Props {
  topic: string
  stateCode?: string
  city?: string | null
  scopeLabel: string
  subject: string
}

const fmt = (n: number) => n.toLocaleString('en-US')
const W = 640
const H = 220
const PAD_L = 16
const PAD_R = 16
const PAD_T = 14
const PAD_B = 52

/**
 * Heat by year (#1418): one box per speaker whose own words on the topic were rated heat 4 or 5, stacked by calendar year of
 * the meeting, with the year's average heat and rated count underneath. A year with fewer than 20 rated speakers is not
 * served, so it has no column (never a zero). Renders nothing until the server has at least one year.
 */
export default function HeatYearBoxes({ topic, stateCode, city, scopeLabel, subject }: Props) {
  const c = stateCode && city ? city : ''
  const q = useQuery({
    queryKey: ['topic-heat-by-year', topic, stateCode ?? 'national', c],
    queryFn: () => fetchTopicHeatByYear(topic, stateCode, c || undefined),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const years = useMemo(() => (q.data?.years ?? []).filter((y) => y.speakers_heated != null), [q.data])
  if (years.length === 0) return null

  const unit = boxUnit(Math.max(...years.map((y) => y.speakers_heated ?? 0)))
  const colW = (W - PAD_L - PAD_R) / years.length
  const bw = Math.min(46, colW * 0.62)
  const boxH = (H - PAD_T - PAD_B) / 12
  const insight = pickInsight({ subject, place: scopeLabel === 'National' ? 'the United States' : scopeLabel, heatByYear: toHeatByYear(q.data) })
  const caption = `Speakers whose own words on ${subject} were rated heated, by year of the meeting · ${scopeLabel}`
  const title = insight.kind === 'heat' ? insight.title : caption
  const legend: LegendItem[] = [
    { key: 'box', label: `1 box = ${fmt(unit)} ${unit === 1 ? 'heated speaker' : 'heated speakers'} (heat 4 or 5 of 5); the top box may be partial`, color: 'var(--violet)' },
  ]

  return (
    <div className="sc-block" style={HOUSE_STYLE}>
      <ChartFrame title={title} titleSupport={insight.kind === 'heat' ? insight.support : null} caption={insight.kind === 'heat' ? caption : undefined} legend={legend} source="Classifier ratings of public speakers' own words (meeting_speaker_topic_side). Years with fewer than 20 rated speakers are left out.">
        <svg className="sc-svg" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={caption}>
          {years.map((y, i) => {
            const cx = PAD_L + colW * (i + 0.5)
            const boxes = columnBoxes(y.speakers_heated ?? 0, unit)
            const label = `${y.year}: ${fmt(y.speakers_heated ?? 0)} of ${fmt(y.speakers_rated)} rated speakers heated, average heat ${y.mean.toFixed(1)} of 5`
            return (
              <g key={y.year} className="sc-col sc-focusable" tabIndex={0} role="img" aria-label={label}>
                <title>{label}</title>
                {boxes.map((b) => (
                  <rect
                    key={b.index}
                    data-box=""
                    data-group={y.year}
                    className="sc-pt sc-bx"
                    x={cx - bw / 2}
                    y={H - PAD_B - (b.index + b.fill) * boxH}
                    width={bw}
                    height={Math.max(2, boxH * b.fill - 1.5)}
                    rx={1.5}
                  />
                ))}
                <text x={cx} y={H - PAD_B + 16} textAnchor="middle" style={{ fontSize: 13, fontWeight: 600, fill: "var(--ink)" }}>{y.year}</text>
                <text x={cx} y={H - PAD_B + 32} textAnchor="middle" fontSize={11} fill="currentColor">{`avg ${y.mean.toFixed(1)}`}</text>
                <text x={cx} y={H - PAD_B + 45} textAnchor="middle" fontSize={10} fill="currentColor" opacity={0.7}>{`${fmt(y.speakers_rated)} rated`}</text>
              </g>
            )
          })}
        </svg>
      </ChartFrame>
    </div>
  )
}
