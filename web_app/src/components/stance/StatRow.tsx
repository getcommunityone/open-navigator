import type { StoryStat } from '../../utils/dataStory'
import Odometer from './Odometer'
import { useScreenActive } from './ActiveScreen'

/** A row of large, real counts (each straight from an endpoint's own totals; a missing or zero count is never passed in). */
export default function StatRow({ stats, label, roll = true, screenIndex }: { stats: StoryStat[]; label: string; roll?: boolean; screenIndex?: number }) {
  // On a story screen the count rolls while its screen is the one in view, read here so the screen need not redraw for it.
  const live = useScreenActive(screenIndex ?? -1, roll)
  const play = screenIndex == null ? roll : live
  return (
    <dl className="stance-stats" aria-label={label}>
      {stats.map((s) => (
        <div key={s.key}>
          <dt>{s.label}</dt>
          <dd>
            <Odometer text={s.value.toLocaleString('en-US')} play={play} />
          </dd>
        </div>
      ))}
    </dl>
  )
}
