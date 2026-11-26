import { toGoLabel } from '../../utils/floatingNext'

interface Props {
  /** How many screens there are. */
  count: number
  /** The screen in view (0-based). */
  active: number
  /** Screens that are done in their own right (the challenge's answered rounds). */
  done?: boolean[]
}

/**
 * Progress at a glance (#915): one segment per screen along the lower edge of the top bar. The segment in view fills, the ones
 * behind it stay filled, an answered round pops, and what is left is said in words ("Three to go"). The segments are a
 * picture of the words beside them, so they are hidden from assistive technology; the rail and the keys still move between
 * screens.
 */
export default function ProgressPips({ count, active, done }: Props) {
  if (count <= 1) return null
  return (
    <div className="stance-pips" data-testid="stance-pips">
      <span className="stance-pips-row" aria-hidden="true">
        {Array.from({ length: count }, (_, i) => (
          <span key={i} className={`stance-pip${i < active ? ' is-past' : ''}${i === active ? ' is-now' : ''}${done?.[i] ? ' is-done' : ''}`} />
        ))}
      </span>
      <span className="stance-pips-left" key={active}>
        {toGoLabel(count - 1 - active)}
      </span>
    </div>
  )
}
