import { toGoLabel } from '../../utils/floatingNext'

interface Props {
  /** How many screens there are. */
  count: number
  /** The screen in view (0-based). */
  active: number
  /** Screens that are done in their own right (the challenge's answered rounds). */
  done?: boolean[]
  /** One accessible name per screen (its headline or word). With `onJump`, each segment is a button to that screen. */
  labels?: string[]
  /** Jump to a screen. Given, the segments are the story's one way to see and move between screens (#1192). */
  onJump?: (index: number) => void
}

const pipClass = (i: number, active: number, done?: boolean[]) =>
  `stance-pip${i < active ? ' is-past' : ''}${i === active ? ' is-now' : ''}${done?.[i] ? ' is-done' : ''}`

/**
 * Progress at a glance (#915): one segment per screen along the lower edge of the top bar. The segment in view fills, the ones
 * behind it stay filled, an answered round pops, and what is left is said in words ("Three to go").
 *
 * With `onJump` (the data story on a wide screen, #1192) the segments are buttons: each is named for its screen ("3 of 11:
 * Sites"), the current one is `aria-current="step"`, and a click moves with the story's own screen navigation. The bar is
 * then the story's single progress indicator; there is no separate rail of numbered dots. Without `onJump` the segments are
 * a picture of the words beside them and hidden from assistive technology.
 */
export default function ProgressPips({ count, active, done, labels, onJump }: Props) {
  if (count <= 1) return null
  const left = (
    <span className="stance-pips-left" key={active}>
      {toGoLabel(count - 1 - active)}
    </span>
  )
  if (onJump) {
    return (
      <nav className="stance-pips is-jump" data-testid="stance-pips" aria-label="Story screens">
        <ol className="stance-pips-row">
          {Array.from({ length: count }, (_, i) => {
            const name = labels?.[i]
            return (
              <li key={i}>
                <button
                  type="button"
                  className="stance-pip-btn"
                  aria-label={`${i + 1} of ${count}${name ? `: ${name}` : ''}`}
                  title={name ?? `${i + 1} of ${count}`}
                  aria-current={i === active ? 'step' : undefined}
                  onClick={() => onJump(i)}
                >
                  <span className={pipClass(i, active, done)} aria-hidden="true" />
                </button>
              </li>
            )
          })}
        </ol>
        {left}
      </nav>
    )
  }
  return (
    <div className="stance-pips" data-testid="stance-pips">
      <span className="stance-pips-row" aria-hidden="true">
        {Array.from({ length: count }, (_, i) => (
          <span key={i} className={pipClass(i, active, done)} />
        ))}
      </span>
      {left}
    </div>
  )
}
