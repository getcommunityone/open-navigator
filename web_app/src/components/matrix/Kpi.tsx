import { useCountUp } from '../../hooks/useCountUp'

/** One big numeral with a mono label. The number counts up to the real value; a missing value stays "—". */
export default function Kpi({
  label,
  value,
  format,
  sub,
  reduced,
}: {
  label: string
  value: number | null
  format: (v: number) => string
  sub: string
  reduced: boolean
}) {
  const text = useCountUp(value, format, reduced)
  return (
    <div className="folio-kpi">
      <dt className="folio-kpi-label">{label}</dt>
      <dd className="m-0">
        <div className="folio-kpi-num" aria-label={value == null ? 'No data available' : format(value)}>
          <span aria-hidden="true">{text}</span>
        </div>
        <div className="folio-kpi-sub">{sub}</div>
      </dd>
    </div>
  )
}
