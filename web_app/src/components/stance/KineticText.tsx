import { Fragment, type CSSProperties } from 'react'
import { titleWords } from '../../utils/storyQuestion'

/**
 * A title whose words rise out of a mask, one after another, when its screen arrives (#915). The words stay plain inline text
 * for a screen reader. The motion itself is in stance.css: scrubbed by the scroll on a wide screen (`--title`), played on a
 * clock when the screen arrives on a phone (`data-state`), and absent under reduced motion.
 */
export default function KineticText({ text }: { text: string }) {
  const words = titleWords(text)
  const last = words.length - 1
  return (
    <>
      {words.map((w, i) => (
        <Fragment key={i}>
          <span className="stance-kw">
            <span className="stance-kw-i" style={{ '--wi': i, '--wf': last > 0 ? i / last : 0 } as CSSProperties}>
              {w}
            </span>
          </span>
          {i < last ? ' ' : ''}
        </Fragment>
      ))}
    </>
  )
}
