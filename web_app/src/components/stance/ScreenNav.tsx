import { forwardRef } from 'react'

interface Props {
  /** What comes next, in words ("Sites"). Null on the last screen of a page that has nothing after it. */
  nextLabel: string | null
  onNext: () => void
  /** Present from the second screen on. */
  onPrev?: () => void
}

/** "Next: <what comes next>" and, after the first screen, a quieter "Back". Shared by the challenge and the story. */
const ScreenNav = forwardRef<HTMLButtonElement, Props>(function ScreenNav({ nextLabel, onNext, onPrev }, ref) {
  return (
    <div className="stance-nav">
      {nextLabel && (
        <button type="button" className="folio-btn stance-next" ref={ref} onClick={onNext} data-primary>
          Next: {nextLabel} <span aria-hidden="true">→</span>
        </button>
      )}
      {onPrev && (
        <button type="button" className="folio-btn stance-back" onClick={onPrev}>
          <span aria-hidden="true">←</span> Back
        </button>
      )}
    </div>
  )
})

export default ScreenNav
