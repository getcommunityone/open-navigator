interface Props {
  /** One accessible name per stop: the screen's headline or category word, never a bare number. */
  labels: string[]
  active: number
  /** Which stops are done (the challenge's answered rounds). */
  answered?: boolean[]
  onJump: (index: number) => void
  navLabel?: string
}

/** A thin rail down the right edge: its fill follows the scroll (--progress on the page) and each stop is a button. */
export default function ProgressRail({ labels, active, answered, onJump, navLabel = 'Screens' }: Props) {
  const count = labels.length
  return (
    <nav className="stance-rail" aria-label={navLabel} style={{ ['--fallback' as string]: count > 1 ? active / (count - 1) : 0 }}>
      <span className="stance-rail-line" aria-hidden="true">
        <span className="stance-rail-fill" />
      </span>
      <ol>
        {labels.map((label, i) => (
          <li key={i}>
            <button
              type="button"
              className={`stance-rail-stop${i === active ? ' is-active' : ''}${answered?.[i] ? ' is-answered' : ''}`}
              aria-label={`${label}${answered?.[i] ? ' (answered)' : ''}`}
              title={label}
              aria-current={i === active ? 'step' : undefined}
              onClick={() => onJump(i)}
            />
          </li>
        ))}
      </ol>
    </nav>
  )
}
