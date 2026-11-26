import { forwardRef, type ReactNode } from 'react'

interface Props {
  /** What comes next, in words ("Sites"). Null on the last screen of a page that has nothing after it. */
  nextLabel: string | null
  onNext: () => void
  /** Present from the second screen on. */
  onPrev?: () => void
  /**
   * The screen's own primary action in Next's spot (#1138): the last screen's link on, or the question screen's
   * "Skip". Rendered as given; mark it `data-nav="next"` and the `stance-next stance-next-end` classes so it takes the
   * same place. Omitted, the Next button shows when there is a `nextLabel`.
   */
  primary?: ReactNode
}

/**
 * The one inline nav of every story screen (#964, #1138): a quieter "Back" at the left (from the second screen on) and the
 * primary "Next →" pill at the right, on one row under the screen text. On a wide screen the row sits at the same spot at
 * the bottom of the left column on every screen (stance.css, #1138), so the buttons never move from screen to screen; the
 * first screen keeps Next in that spot with no Back. The button reads just "Next"; where it goes stays in its accessible
 * name and tooltip ("Next: Who spoke up"). Shared by the challenge and the story.
 */
const ScreenNav = forwardRef<HTMLButtonElement, Props>(function ScreenNav({ nextLabel, onNext, onPrev, primary }, ref) {
  return (
    <div className="stance-nav stance-nav-split" data-screen-nav="">
      {onPrev && (
        <button type="button" className="folio-btn stance-back" onClick={onPrev} data-nav="back">
          <span aria-hidden="true">←</span> Back
        </button>
      )}
      {primary ??
        (nextLabel && (
          <button
            type="button"
            className="folio-btn stance-next stance-next-end"
            ref={ref}
            onClick={onNext}
            aria-label={`Next: ${nextLabel}`}
            title={`Next: ${nextLabel}`}
            data-primary
            data-nav="next"
          >
            Next <span aria-hidden="true">→</span>
          </button>
        ))}
    </div>
  )
})

export default ScreenNav
