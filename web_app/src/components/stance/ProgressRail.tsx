interface Props {
  count: number
  active: number
  /** Which rounds have a confirmed answer (the end panel has none). */
  answered: boolean[]
  onJump: (index: number) => void
}

/** A thin rail down the right edge: its fill follows the scroll (--progress on the game) and each stop is a button. */
export default function ProgressRail({ count, active, answered, onJump }: Props) {
  return (
    <nav className="stance-rail" aria-label="Rounds" style={{ ['--fallback' as string]: count > 1 ? active / (count - 1) : 0 }}>
      <span className="stance-rail-line" aria-hidden="true">
        <span className="stance-rail-fill" />
      </span>
      <ol>
        {Array.from({ length: count }, (_, i) => {
          const isEnd = i === count - 1
          return (
            <li key={i}>
              <button
                type="button"
                className={`stance-rail-stop${i === active ? ' is-active' : ''}${answered[i] ? ' is-answered' : ''}`}
                aria-label={isEnd ? 'Go to the end screen' : `Go to round ${i + 1}${answered[i] ? ' (answered)' : ''}`}
                aria-current={i === active ? 'step' : undefined}
                onClick={() => onJump(i)}
              />
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
