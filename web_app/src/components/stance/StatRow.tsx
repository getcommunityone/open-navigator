import type { StoryStat } from '../../utils/dataStory'
import Odometer from './Odometer'

/** A row of large, real counts (each straight from an endpoint's own totals; a missing or zero count is never passed in). */
export default function StatRow({ stats, label, roll = true }: { stats: StoryStat[]; label: string; roll?: boolean }) {
  return (
    <dl className="stance-stats" aria-label={label}>
      {stats.map((s) => (
        <div key={s.key}>
          <dt>{s.label}</dt>
          <dd>
            <Odometer text={s.value.toLocaleString('en-US')} play={roll} />
          </dd>
        </div>
      ))}
    </dl>
  )
}
