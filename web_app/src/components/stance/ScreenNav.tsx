import { forwardRef } from 'react'

interface Props {
  /** What comes next, in words ("Sites"). Null on the last screen of a page that has nothing after it. */
  nextLabel: string | null
  onNext: () => void
  /** Present from the second screen on. */
  onPrev?: () => void
}

/**
 * A quieter "Back" at the left (after the first screen) and the primary "Next →" at the right, like the hub's
 * "Start the story" (#964). The button reads just "Next"; where it goes stays in its accessible name and tooltip
 * ("Next: Who spoke up"), because "Next: Who spoke up" as the visible label read like a heading and confused readers.
 * Shared by the challenge and the story.
 */
const ScreenNav = forwardRef<HTMLButtonElement, Props>(function ScreenNav({ nextLabel, onNext, onPrev }, ref) {
  return (
    <div className="stance-nav stance-nav-split">
      {onPrev && (
        <button type="button" className="folio-btn stance-back" onClick={onPrev}>
          <span aria-hidden="true">←</span> Back
        </button>
      )}
      {nextLabel && (
        <button
          type="button"
          className="folio-btn stance-next stance-next-end"
          ref={ref}
          onClick={onNext}
          aria-label={`Next: ${nextLabel}`}
          title={`Next: ${nextLabel}`}
          data-primary
        >
          Next <span aria-hidden="true">→</span>
        </button>
      )}
    </div>
  )
})

export default ScreenNav
